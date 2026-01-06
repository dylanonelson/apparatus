package httpapi

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/http"
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
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.Recoverer)
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		respondJSON(w, http.StatusOK, HealthResponse{Ok: true, TimestampMs: time.Now().UnixMilli()})
	})
	r.Post("/search", handleSearch)
	r.Post("/content/fetch", handleFetchContent)
	return r
}

func handleSearch(w http.ResponseWriter, r *http.Request) {
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

	ctx, cancel := context.WithTimeout(r.Context(), 15*time.Second)
	defer cancel()
	publication, err := readium.OpenPublication(ctx, path)
	if err != nil {
		logging.L.Printf("open pub error: %v", err)
		http.Error(w, "failed to open publication", http.StatusInternalServerError)
		return
	}

	segCh, err := readium.IterateTextSegments(ctx, publication)
	if err != nil {
		logging.L.Printf("content segments error: %v", err)
		http.Error(w, "failed to read content", http.StatusInternalServerError)
		return
	}

	resp := SearchResponse{Hits: make([]SearchHit, 0)}
	for seg := range segCh {
		matches := search.FindMatches(seg.Text, req.Query, req.MaxResults-len(resp.Hits), req.ContextChars)
		for _, m := range matches {
			before := m.Before
			highlight := m.Match
			after := m.After
			locText := &LocatorText{Before: &before, Highlight: &highlight, After: &after}
			href := seg.Locator.Href.String()

			loc := Locator{Href: href, Text: locText, Type: seg.Locator.MediaType.String()}

			locatorLocations := &LocatorLocations{}
			if seg.Locator.Locations.Position != nil {
				uintPosition := *seg.Locator.Locations.Position
				position := int(uintPosition)
				locatorLocations.Position = &position
			}
			// The Readium iterator populates the CSS selector in the OtherLocations map.
			if seg.Locator.Locations.OtherLocations != nil {
				locatorLocations.OtherLocations = seg.Locator.Locations.OtherLocations
			}
			loc.Locations = locatorLocations

			searchHit := SearchHit{Href: href, Locator: loc}
			fmt.Printf("searchHit: %+v\n", searchHit)
			fmt.Printf("locator.text.before: %+v\n", *loc.Text.Before)
			fmt.Printf("locator.text.highlight: %+v\n", *loc.Text.Highlight)
			fmt.Printf("locator.text.after: %+v\n", *loc.Text.After)
			fmt.Printf("\n")
			resp.Hits = append(resp.Hits, searchHit)
			if len(resp.Hits) >= req.MaxResults {
				// Enough results; cancel context to stop the iterator.
				cancel()
				break
			}
		}
		if len(resp.Hits) >= req.MaxResults {
			break
		}
	}

	respondJSON(w, http.StatusOK, resp)
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
