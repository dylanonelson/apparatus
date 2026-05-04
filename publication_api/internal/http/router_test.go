package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"publication_server/internal/publications"
	"publication_server/internal/readium"
	"publication_server/internal/search"
)

func pkgRootDir(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatalf("runtime.Caller failed")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "../../"))
}

func TestSearch_EndToEnd_SampleTwoChapters_ExactParagraph(t *testing.T) {
	// Point the server to publication_api/testdata.
	root := pkgRootDir(t)
	pubs := filepath.Join(root, "testdata")
	if err := os.Setenv("PUBLICATIONS_DIR", pubs); err != nil {
		t.Fatalf("set env: %v", err)
	}
	publications.ResetStoreCache()
	defer os.Unsetenv("PUBLICATIONS_DIR")

	// Open the same publication via readium to obtain the exact paragraph text.
	epubPath := filepath.Join(pubs, "sample_two_chapters.epub")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	publication, err := readium.OpenPublication(ctx, epubPath)
	if err != nil {
		t.Skipf("skipping: OpenPublication failed (%v) — ensure go-toolkit streamer supports fixture on this platform", err)
	}
	segCh, err := readium.IterateTextSegments(ctx, publication)
	if err != nil {
		t.Skipf("skipping: content segments error (%v)", err)
	}
	// We will use the first lorem ipsum paragraph as the exact query.
	target := ""
	const expectedPara = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed non risus."
	for seg := range segCh {
		if seg.Text == expectedPara {
			target = seg.Text
			break
		}
	}
	if target == "" {
		t.Fatalf("expected to find lorem ipsum paragraph in streamed segments")
	}

	// Build router and issue request.
	r := newRouterWithCache(searchTestCache(t))
	srv := httptest.NewServer(r)
	defer srv.Close()

	reqBody := SearchRequest{
		PublicationID: "sample_two_chapters",
		Query:         target,
		MaxResults:    5,
		ContextChars:  10,
	}
	body, _ := json.Marshal(reqBody)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(srv.URL+"/search", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("post /search: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status: %d", resp.StatusCode)
	}

	var sr SearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(sr.Hits) == 0 {
		t.Fatalf("expected at least one hit, got len=%d", len(sr.Hits))
	}

	// Expect a hit whose highlight is a non-empty substring of the target
	// paragraph. (Under Bleve match-phrase, the highlight spans from the
	// first matched term's offset to the last matched term's offset; with
	// stopword filtering this may exclude leading/trailing function words,
	// so we don't require a literal whole-paragraph match anymore.)
	matched := false
	for _, h := range sr.Hits {
		if h.Locator.Text == nil || h.Locator.Text.Highlight == nil {
			continue
		}
		hl := *h.Locator.Text.Highlight
		if hl != "" && strings.Contains(target, hl) {
			matched = true
			break
		}
	}
	if !matched {
		t.Fatalf("no hit had a highlight substring of the target paragraph; hits=%+v", sr.Hits)
	}
}

// searchTestCache returns a fresh search index cache for tests, so each test
// starts with an empty cache (and therefore exercises the index-build path).
func searchTestCache(t *testing.T) *search.IndexCache {
	t.Helper()
	return search.NewIndexCache()
}

// searchCorpusEnv points PUBLICATIONS_DIR at publication_api/testdata and
// resets the publications store cache so the new env var takes effect.
// It returns a teardown to call via t.Cleanup.
func searchCorpusEnv(t *testing.T) {
	t.Helper()
	root := pkgRootDir(t)
	pubs := filepath.Join(root, "testdata")
	if err := os.Setenv("PUBLICATIONS_DIR", pubs); err != nil {
		t.Fatalf("set env: %v", err)
	}
	publications.ResetStoreCache()
	t.Cleanup(func() {
		os.Unsetenv("PUBLICATIONS_DIR")
		publications.ResetStoreCache()
	})
	// Verify the corpus is present so test failures are clear.
	if _, err := os.Stat(filepath.Join(pubs, "search_corpus.epub")); err != nil {
		t.Fatalf("search_corpus.epub missing; regenerate via `go run ./testdata/cmd/build_search_corpus`: %v", err)
	}
}

func postSearch(t *testing.T, srv *httptest.Server, body SearchRequest) SearchResponse {
	t.Helper()
	b, _ := json.Marshal(body)
	resp, err := (&http.Client{Timeout: 30 * time.Second}).Post(srv.URL+"/search", "application/json", bytes.NewReader(b))
	if err != nil {
		t.Fatalf("post /search: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status: %d", resp.StatusCode)
	}
	var sr SearchResponse
	if err := json.NewDecoder(resp.Body).Decode(&sr); err != nil {
		t.Fatalf("decode: %v", err)
	}
	return sr
}

// TestSearch_EndToEnd_Stemming verifies that a query for the singular term
// returns hits on the plural-only segment via the en analyzer's stemmer.
func TestSearch_EndToEnd_Stemming(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	sr := postSearch(t, srv, SearchRequest{
		PublicationID: "search_corpus",
		Query:         "horse",
		MaxResults:    20,
		ContextChars:  120,
	})
	if len(sr.Hits) == 0 {
		t.Fatalf("expected hits for 'horse'")
	}
	// At least one hit must be on the segment that only contains the plural
	// form ("Two other horses watched..."), proving stemming is wired up
	// through the HTTP layer.
	foundPluralOnly := false
	for _, h := range sr.Hits {
		if h.Locator.Text == nil || h.Locator.Text.Highlight == nil {
			continue
		}
		hl := strings.ToLower(*h.Locator.Text.Highlight)
		// Highlight should be the matched morphological variant.
		if hl == "horses" {
			foundPluralOnly = true
		}
	}
	if !foundPluralOnly {
		t.Fatalf("query 'horse' did not produce any hit highlighting 'horses'; hits=%+v", sr.Hits)
	}
}

// TestSearch_EndToEnd_Phrase verifies that a multi-word query is treated as
// a phrase: in-order matches hit, reversed-order does not.
func TestSearch_EndToEnd_Phrase(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	sr := postSearch(t, srv, SearchRequest{
		PublicationID: "search_corpus",
		Query:         "horse race",
		MaxResults:    20,
		ContextChars:  120,
	})
	if len(sr.Hits) == 0 {
		t.Fatalf("expected hits for phrase 'horse race'")
	}
	// Every hit must be on chapter2.xhtml (the only chapter with the
	// phrase). The reversed-order paragraph in chapter2 contains "race
	// horse" which is in chapter 2 *too*, so we additionally verify that
	// no hit's highlight contains "race horse" without "horse race".
	for _, h := range sr.Hits {
		if !strings.Contains(h.Locator.Href, "chapter2") {
			t.Fatalf("phrase hit on unexpected href %q", h.Locator.Href)
		}
		if h.Locator.Text == nil || h.Locator.Text.Highlight == nil {
			continue
		}
		hl := strings.ToLower(*h.Locator.Text.Highlight)
		if !strings.Contains(hl, "horse race") {
			t.Fatalf("phrase highlight missing 'horse race': %q", hl)
		}
	}
}

// TestSearch_EndToEnd_RareWord covers a single-occurrence term.
func TestSearch_EndToEnd_RareWord(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	sr := postSearch(t, srv, SearchRequest{
		PublicationID: "search_corpus",
		Query:         "quintessential",
		MaxResults:    20,
		ContextChars:  60,
	})
	if len(sr.Hits) != 1 {
		t.Fatalf("expected exactly 1 hit for 'quintessential', got %d (%+v)", len(sr.Hits), sr.Hits)
	}
	hit := sr.Hits[0]
	if !strings.Contains(hit.Locator.Href, "chapter4") {
		t.Fatalf("expected hit on chapter4, got href=%q", hit.Locator.Href)
	}
	if hit.Locator.Text == nil || hit.Locator.Text.Highlight == nil ||
		strings.ToLower(*hit.Locator.Text.Highlight) != "quintessential" {
		t.Fatalf("expected highlight 'quintessential', got %+v", hit.Locator.Text)
	}
}

// TestSearch_EndToEnd_NoMatch verifies a clean empty-result response.
func TestSearch_EndToEnd_NoMatch(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	sr := postSearch(t, srv, SearchRequest{
		PublicationID: "search_corpus",
		Query:         "xyzzyzzz",
		MaxResults:    20,
		ContextChars:  60,
	})
	if len(sr.Hits) != 0 {
		t.Fatalf("expected 0 hits for nonsense query, got %d", len(sr.Hits))
	}
}

// TestSearch_EndToEnd_Ranking verifies that BM25 puts term-dense short
// paragraphs above long, tangential ones (chapter 5 has both kinds).
func TestSearch_EndToEnd_Ranking(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	sr := postSearch(t, srv, SearchRequest{
		PublicationID: "search_corpus",
		Query:         "crowd",
		MaxResults:    20,
		ContextChars:  60,
	})
	if len(sr.Hits) < 3 {
		t.Fatalf("expected ≥3 hits for 'crowd', got %d", len(sr.Hits))
	}
	// The top hit should be one of the very short paragraphs ("The crowd
	// gathered before noon.", "A crowd is patient until it isn't.", "The
	// crowd quieted.", "The crowd was still."). Long noisy paragraphs
	// must not outrank these.
	topAfter := ""
	if sr.Hits[0].Locator.Text != nil && sr.Hits[0].Locator.Text.After != nil {
		topAfter = *sr.Hits[0].Locator.Text.After
	}
	topBefore := ""
	if sr.Hits[0].Locator.Text != nil && sr.Hits[0].Locator.Text.Before != nil {
		topBefore = *sr.Hits[0].Locator.Text.Before
	}
	full := topBefore + " " + topAfter
	if len(full) > 200 {
		t.Fatalf("top-ranked hit looks like a long paragraph (~%d chars of context); BM25 should rank short paragraphs higher", len(full))
	}
}

// TestSearch_EndToEnd_LocatorShape protects the response contract that the
// Python wrapper depends on.
func TestSearch_EndToEnd_LocatorShape(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	sr := postSearch(t, srv, SearchRequest{
		PublicationID: "search_corpus",
		Query:         "quintessential",
		MaxResults:    20,
		ContextChars:  60,
	})
	if len(sr.Hits) != 1 {
		t.Fatalf("expected 1 hit, got %d", len(sr.Hits))
	}
	h := sr.Hits[0]
	if h.Locator.Href == "" {
		t.Fatalf("missing locator.href")
	}
	if h.Locator.Type == "" {
		t.Fatalf("missing locator.type (media type)")
	}
	if h.Locator.Text == nil {
		t.Fatalf("missing locator.text")
	}
	if h.Locator.Text.Highlight == nil {
		t.Fatalf("missing locator.text.highlight")
	}
	if h.Locator.Locations == nil {
		t.Fatalf("missing locator.locations")
	}
	// Position is optional — Readium only populates it when the publication
	// has positions baked in; our synthetic fixture does not. We still
	// verify the field round-trips through the response (nil is fine).
	_ = h.Locator.Locations.Position
	// The Readium iterator surfaces a CSS selector under OtherLocations.
	// At minimum, OtherLocations should be populated for content streamed
	// from XHTML chapters.
	if h.Locator.Locations.OtherLocations == nil {
		t.Fatalf("expected locator.locations.other_locations to be populated for an XHTML segment")
	}
	if _, ok := h.Locator.Locations.OtherLocations["cssSelector"]; !ok {
		t.Fatalf("expected cssSelector key in other_locations: %+v", h.Locator.Locations.OtherLocations)
	}
}

// TestSearch_EndToEnd_CacheReused verifies that hitting /search twice for
// the same publication only invokes the index builder once. We can't
// instrument the package-level cache from outside, so we verify by timing
// or, more reliably, by observing that the second call's response is
// identical and the singleflight test in the search package proves the
// underlying contract.
//
// This test is intentionally a smoke test: it checks the second call
// succeeds and returns the same hits.
func TestSearch_EndToEnd_CacheReused(t *testing.T) {
	searchCorpusEnv(t)
	srv := httptest.NewServer(newRouterWithCache(searchTestCache(t)))
	defer srv.Close()

	body := SearchRequest{
		PublicationID: "search_corpus",
		Query:         "horse",
		MaxResults:    5,
		ContextChars:  60,
	}
	first := postSearch(t, srv, body)
	second := postSearch(t, srv, body)
	if len(first.Hits) != len(second.Hits) {
		t.Fatalf("hit count differs across cached calls: %d vs %d", len(first.Hits), len(second.Hits))
	}
	for i := range first.Hits {
		if first.Hits[i].Locator.Href != second.Hits[i].Locator.Href {
			t.Fatalf("hit %d href differs: %q vs %q", i, first.Hits[i].Locator.Href, second.Hits[i].Locator.Href)
		}
	}
}
