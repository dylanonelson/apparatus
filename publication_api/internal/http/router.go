package httpapi

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"github.com/readium/go-toolkit/pkg/fetcher"
	"github.com/readium/go-toolkit/pkg/mediatype"
	"github.com/readium/go-toolkit/pkg/util/url"

	"publication_server/internal/config"
	"publication_server/internal/logging"
	"publication_server/internal/publications"
	"publication_server/internal/readium"
	"publication_server/internal/search"
)

// indexCache holds Bleve full-text indexes for publications, keyed by
// publication ID. It is a package-level singleton so cached indexes survive
// across requests for the lifetime of the process. Tests construct their
// own cache via newRouterWithCache.
var indexCache = search.NewIndexCache()

type HealthResponse struct {
	Ok          bool  `json:"ok"`
	TimestampMs int64 `json:"timestamp_ms"`
}

type SearchRequest struct {
	PublicationID string `json:"publication_id"`
	Query         string `json:"query"`
	MaxResults    int    `json:"max_results"`
	ContextChars  int    `json:"context_chars"`
}

type LocatorLocations struct {
	Position         *int                   `json:"position,omitempty"`
	Progression      *float64               `json:"progression,omitempty"`
	TotalProgression *float64               `json:"totalProgression,omitempty"`
	OtherLocations   map[string]interface{} `json:"other_locations,omitempty"`
}

type LocatorText struct {
	Before    *string `json:"before,omitempty"`
	Highlight *string `json:"highlight,omitempty"`
	After     *string `json:"after,omitempty"`
}

type Locator struct {
	Href      string            `json:"href"`
	Type      string            `json:"type"`
	Title     *string           `json:"title,omitempty"`
	Locations *LocatorLocations `json:"locations,omitempty"`
	Text      *LocatorText      `json:"text,omitempty"`
}

type SearchHit struct {
	Href    string  `json:"href"`
	Locator Locator `json:"locator"`
}

type SearchResponse struct {
	Hits []SearchHit `json:"hits"`
}

type FetchContentRequest struct {
	PublicationID string   `json:"publication_id"`
	Hrefs         []string `json:"hrefs"`
}

type FileContent struct {
	Href      string `json:"href"`
	MediaType string `json:"media_type,omitempty"`
	Encoding  string `json:"encoding"` // utf-8 or base64
	Content   string `json:"content"`
}

type FetchContentResponse struct {
	Files []FileContent `json:"files"`
}

func Router() http.Handler {
	return newRouterWithCache(indexCache)
}

// newRouterWithCache builds a Router that uses the supplied search index
// cache. Tests use this to get a clean cache per test.
func newRouterWithCache(cache *search.IndexCache) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.Recoverer)
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		respondJSON(w, http.StatusOK, HealthResponse{Ok: true, TimestampMs: time.Now().UnixMilli()})
	})
	r.Post("/search", handleSearchWith(cache))
	r.Post("/content/fetch", handleFetchContent)
	return r
}

func handleSearchWith(cache *search.IndexCache) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		handleSearch(w, r, cache)
	}
}

func handleSearch(w http.ResponseWriter, r *http.Request, cache *search.IndexCache) {
	var req SearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	if req.PublicationID == "" || req.Query == "" {
		http.Error(w, "publication_id and query are required", http.StatusBadRequest)
		return
	}
	if req.MaxResults <= 0 {
		req.MaxResults = 20
	}
	if req.ContextChars <= 0 {
		req.ContextChars = 120
	}

	baseDir := config.PublicationsDir()
	store, err := publications.GetStore(baseDir)
	if err != nil {
		logging.L.Printf("load catalog error: %v", err)
		http.Error(w, "failed to load catalog", http.StatusInternalServerError)
		return
	}
	path, err := store.ResolvePublicationPath(req.PublicationID)
	if err != nil {
		http.Error(w, "publication not found", http.StatusNotFound)
		return
	}

	stat, err := os.Stat(path)
	if err != nil {
		logging.L.Printf("stat publication error: %v", err)
		http.Error(w, "failed to stat publication", http.StatusInternalServerError)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()

	idx, err := cache.Get(ctx, req.PublicationID, stat.ModTime(), func(ctx context.Context) ([]search.IndexedSegment, error) {
		publication, err := readium.OpenPublication(ctx, path)
		if err != nil {
			return nil, fmt.Errorf("open publication: %w", err)
		}
		segs, err := readium.LoadAllSegments(ctx, publication)
		if err != nil {
			return nil, fmt.Errorf("load segments: %w", err)
		}
		return readiumSegmentsToIndexed(segs), nil
	})
	if err != nil {
		logging.L.Printf("build index error: %v", err)
		http.Error(w, "failed to build search index", http.StatusInternalServerError)
		return
	}

	queryHits, err := idx.Query(ctx, req.Query, req.MaxResults, req.ContextChars)
	if err != nil {
		logging.L.Printf("search error: %v", err)
		http.Error(w, "search failed", http.StatusInternalServerError)
		return
	}

	resp := SearchResponse{Hits: make([]SearchHit, 0, len(queryHits))}
	for _, qh := range queryHits {
		resp.Hits = append(resp.Hits, queryHitToSearchHit(qh))
	}
	respondJSON(w, http.StatusOK, resp)
}

// readiumSegmentsToIndexed flattens Readium's Segment shape into the
// IndexedSegment shape the search package consumes. The CSS selector lives
// in the locator's OtherLocations map under the key "cssSelector".
func readiumSegmentsToIndexed(segs []readium.Segment) []search.IndexedSegment {
	out := make([]search.IndexedSegment, 0, len(segs))
	for _, s := range segs {
		seg := search.IndexedSegment{
			Text:      s.Text,
			Href:      s.Locator.Href.String(),
			MediaType: s.Locator.MediaType.String(),
		}
		if s.Locator.Locations.Position != nil {
			pos := int(*s.Locator.Locations.Position)
			seg.Position = &pos
		}
		if css, ok := s.Locator.Locations.OtherLocations["cssSelector"].(string); ok {
			seg.CSSSelector = css
		}
		out = append(out, seg)
	}
	return out
}

// queryHitToSearchHit lifts a search.QueryHit into the wire-format
// SearchHit/Locator structure expected by the existing API contract.
func queryHitToSearchHit(qh search.QueryHit) SearchHit {
	before := qh.Snippet.Before
	highlight := qh.Snippet.Match
	after := qh.Snippet.After
	locText := &LocatorText{Before: &before, Highlight: &highlight, After: &after}

	loc := Locator{
		Href: qh.Segment.Href,
		Type: qh.Segment.MediaType,
		Text: locText,
	}

	locatorLocations := &LocatorLocations{}
	if qh.Segment.Position != nil {
		p := *qh.Segment.Position
		locatorLocations.Position = &p
	}
	if qh.Segment.CSSSelector != "" {
		locatorLocations.OtherLocations = map[string]interface{}{
			"cssSelector": qh.Segment.CSSSelector,
		}
	}
	loc.Locations = locatorLocations
	return SearchHit{Href: qh.Segment.Href, Locator: loc}
}

func respondJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func handleFetchContent(w http.ResponseWriter, r *http.Request) {
	var req FetchContentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid JSON", http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(req.PublicationID) == "" {
		http.Error(w, "publication_id is required", http.StatusBadRequest)
		return
	}
	if len(req.Hrefs) == 0 {
		http.Error(w, "at least one href is required", http.StatusBadRequest)
		return
	}
	if len(req.Hrefs) > 2 {
		http.Error(w, "hrefs cannot exceed 2 items", http.StatusBadRequest)
		return
	}

	hrefs := make([]string, 0, len(req.Hrefs))
	for _, h := range req.Hrefs {
		trimmed := strings.TrimSpace(h)
		if trimmed == "" {
			http.Error(w, "hrefs must be non-empty strings", http.StatusBadRequest)
			return
		}
		hrefs = append(hrefs, trimmed)
	}

	baseDir := config.PublicationsDir()
	store, err := publications.GetStore(baseDir)
	if err != nil {
		logging.L.Printf("load catalog error: %v", err)
		http.Error(w, "failed to load catalog", http.StatusInternalServerError)
		return
	}
	path, err := store.ResolvePublicationPath(req.PublicationID)
	if err != nil {
		http.Error(w, "publication not found", http.StatusNotFound)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()
	publication, err := readium.OpenPublication(ctx, path)
	if err != nil {
		logging.L.Printf("open pub error: %v", err)
		http.Error(w, "failed to open publication", http.StatusInternalServerError)
		return
	}
	defer publication.Close()

	resp := FetchContentResponse{Files: make([]FileContent, 0, len(hrefs))}
	for _, rawHref := range hrefs {
		u, err := url.URLFromString(rawHref)
		if err != nil {
			u, err = url.URLFromDecodedPath(rawHref)
			if err != nil {
				http.Error(w, fmt.Sprintf("invalid href: %s", rawHref), http.StatusBadRequest)
				return
			}
		}

		link := publication.Manifest.LinkWithHref(u)
		if link == nil {
			http.Error(w, fmt.Sprintf("href not found in publication: %s", rawHref), http.StatusNotFound)
			return
		}

		resource := publication.Get(ctx, *link)
		if resource == nil {
			http.Error(w, fmt.Sprintf("resource unavailable for href: %s", rawHref), http.StatusNotFound)
			return
		}
		defer resource.Close()

		mt := link.MediaType
		if resource.Link().MediaType != nil {
			mt = resource.Link().MediaType
		}
		mediaTypeStr := ""
		if mt != nil {
			mediaTypeStr = mt.String()
		}

		if isTextMediaType(mt) {
			text, ex := fetcher.ReadResourceAsString(ctx, resource)
			if ex != nil {
				http.Error(w, ex.Error(), ex.HTTPStatus())
				return
			}
			resp.Files = append(resp.Files, FileContent{
				Href:      rawHref,
				MediaType: mediaTypeStr,
				Encoding:  "utf-8",
				Content:   text,
			})
		} else {
			data, ex := resource.Read(ctx, 0, 0)
			if ex != nil {
				http.Error(w, ex.Error(), ex.HTTPStatus())
				return
			}
			resp.Files = append(resp.Files, FileContent{
				Href:      rawHref,
				MediaType: mediaTypeStr,
				Encoding:  "base64",
				Content:   base64.StdEncoding.EncodeToString(data),
			})
		}
	}

	respondJSON(w, http.StatusOK, resp)
}

func isTextMediaType(mt *mediatype.MediaType) bool {
	if mt == nil {
		return false
	}

	if strings.EqualFold(mt.Type, "text") {
		return true
	}

	sub := strings.ToLower(mt.SubType)
	switch {
	case strings.Contains(sub, "json"):
		return true
	case strings.Contains(sub, "xml"):
		return true
	case strings.Contains(sub, "html"):
		return true
	case strings.Contains(sub, "xhtml"):
		return true
	}
	return false
}
