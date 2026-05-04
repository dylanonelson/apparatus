package search

import (
	"context"
	"strings"
	"testing"
)

// fixtureSegments returns a small in-memory corpus used by index_test and
// cache_test. The texts are designed so every test in this file can
// describe its expectation in terms of which segment(s) should match.
func fixtureSegments() []IndexedSegment {
	pos := func(i int) *int { return &i }
	return []IndexedSegment{
		{Text: "The horse stood quietly in the first stall.", Href: "ch1", Position: pos(1)},
		{Text: "Two other horses watched from the far end of the row.", Href: "ch1", Position: pos(2)},
		{Text: "The horse race drew a crowd of several thousand.", Href: "ch2", Position: pos(3)},
		{Text: "A bay gelding said to be the finest race horse in three counties.", Href: "ch2", Position: pos(4)},
		{Text: "Margaret ran every morning before the rest of the house was awake.", Href: "ch3", Position: pos(5)},
		{Text: "She had been running this same loop for eleven years.", Href: "ch3", Position: pos(6)},
		{Text: "Some mornings the runs were easy, the air sharp and her breath even.", Href: "ch3", Position: pos(10)},
		{Text: "There was a quintessential restraint in the language.", Href: "ch4", Position: pos(7)},
		{Text: "The crowd gathered before noon.", Href: "ch5", Position: pos(8)},
		{Text: "She watched the crowd from the second-floor window. From this angle the crowd looked smaller than it had sounded.", Href: "ch5", Position: pos(9)},
	}
}

func buildFixtureIndex(t *testing.T) *PublicationIndex {
	t.Helper()
	idx, err := BuildIndex(context.Background(), fixtureSegments())
	if err != nil {
		t.Fatalf("BuildIndex: %v", err)
	}
	return idx
}

func TestIndex_StemmedSingleWord_PluralFindsSingular(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "horse", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) == 0 {
		t.Fatalf("expected hits for 'horse', got 0")
	}
	// At least one hit should come from the segment that only contains the
	// plural form ("Two other horses..."), proving stemming is active.
	foundPlural := false
	for _, h := range hits {
		if strings.Contains(h.Segment.Text, "horses") && !strings.Contains(h.Segment.Text, "horse ") {
			foundPlural = true
		}
	}
	if !foundPlural {
		t.Fatalf("expected a hit on the plural-only segment; hits: %d", len(hits))
	}
}

func TestIndex_StemmedVerbForms(t *testing.T) {
	// Porter stemming normalizes regular morphology: "running", "runs", and
	// the verb "run" share the stem "run", so any of those queries should
	// hit any of those segments. Irregular forms like "ran" are NOT
	// normalized by Porter — they stay as-is — so a query for "ran" will
	// only literal-match. We document both behaviors here.
	idx := buildFixtureIndex(t)

	t.Run("running matches runs segment", func(t *testing.T) {
		hits, err := idx.Query(context.Background(), "running", 10, 30)
		if err != nil {
			t.Fatalf("Query: %v", err)
		}
		found := false
		for _, h := range hits {
			if strings.Contains(h.Segment.Text, "runs") {
				found = true
			}
		}
		if !found {
			t.Fatalf("query 'running' should match a segment containing 'runs' via shared stem")
		}
	})

	t.Run("runs matches running segment", func(t *testing.T) {
		hits, err := idx.Query(context.Background(), "runs", 10, 30)
		if err != nil {
			t.Fatalf("Query: %v", err)
		}
		found := false
		for _, h := range hits {
			if strings.Contains(h.Segment.Text, "running") {
				found = true
			}
		}
		if !found {
			t.Fatalf("query 'runs' should match a segment containing 'running' via shared stem")
		}
	})

	t.Run("ran matches only literal ran", func(t *testing.T) {
		// Porter doesn't normalize irregular past tense; document the limit.
		hits, err := idx.Query(context.Background(), "ran", 10, 30)
		if err != nil {
			t.Fatalf("Query: %v", err)
		}
		if len(hits) == 0 {
			t.Fatalf("query 'ran' should at least find the literal segment")
		}
		for _, h := range hits {
			if !strings.Contains(h.Segment.Text, "ran") {
				t.Fatalf("query 'ran' returned a non-literal hit: %q", h.Segment.Text)
			}
		}
	})
}

func TestIndex_PhraseOrderMatters(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "horse race", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) == 0 {
		t.Fatalf("expected at least one phrase hit")
	}
	// Top hit must be the in-order "horse race" segment, never the reversed
	// "race horse" segment.
	top := hits[0]
	if !strings.Contains(top.Segment.Text, "horse race") {
		t.Fatalf("top hit does not contain in-order phrase: %q", top.Segment.Text)
	}
	for _, h := range hits {
		if strings.Contains(h.Segment.Text, "race horse") && !strings.Contains(h.Segment.Text, "horse race") {
			t.Fatalf("phrase query should not match reversed-order segment: %q", h.Segment.Text)
		}
	}
}

func TestIndex_RankingByScore(t *testing.T) {
	// The two ch5 segments differ in length; both contain "crowd". BM25
	// should prefer the shorter, term-dense paragraph.
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "crowd", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) < 2 {
		t.Fatalf("expected ≥2 hits, got %d", len(hits))
	}
	// Hits should be in non-increasing score order.
	for i := 1; i < len(hits); i++ {
		if hits[i].Score > hits[i-1].Score {
			t.Fatalf("hits not score-sorted at index %d: %f > %f", i, hits[i].Score, hits[i-1].Score)
		}
	}
	// The short paragraph ("The crowd gathered before noon.") must outrank
	// the long one.
	short := "The crowd gathered before noon."
	long := "She watched the crowd from the second-floor window."
	var shortRank, longRank int = -1, -1
	for i, h := range hits {
		if strings.HasPrefix(h.Segment.Text, short) {
			shortRank = i
		}
		if strings.HasPrefix(h.Segment.Text, long) {
			longRank = i
		}
	}
	if shortRank < 0 || longRank < 0 {
		t.Fatalf("expected both crowd segments in results; shortRank=%d longRank=%d", shortRank, longRank)
	}
	if shortRank >= longRank {
		t.Fatalf("short paragraph (rank %d) should outrank long paragraph (rank %d)", shortRank, longRank)
	}
}

func TestIndex_MaxResults(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "the", 100, 30)
	if err != nil {
		// "the" is a stopword under the en analyzer; either zero hits or
		// an error is acceptable. We test the explicit zero-hit case below.
		_ = err
	}
	hits, err = idx.Query(context.Background(), "horse", 1, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) != 1 {
		t.Fatalf("max_results=1 should yield 1 hit, got %d", len(hits))
	}
}

func TestIndex_RareTermUniqueness(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "quintessential", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) != 1 {
		t.Fatalf("expected exactly 1 hit for 'quintessential', got %d", len(hits))
	}
	if !strings.Contains(hits[0].Segment.Text, "quintessential") {
		t.Fatalf("hit text missing term: %q", hits[0].Segment.Text)
	}
}

func TestIndex_NoMatch(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "xyzzyzzz", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) != 0 {
		t.Fatalf("expected 0 hits for nonsense query, got %d", len(hits))
	}
}

func TestIndex_StopwordQuery(t *testing.T) {
	// "the" is filtered by the en analyzer's stop-token filter. A query of
	// only stopwords should return zero hits — we document the behavior here
	// so future analyzer changes don't silently break it.
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "the", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) != 0 {
		t.Fatalf("stopword query should yield 0 hits, got %d", len(hits))
	}
}

func TestIndex_SnippetReconstruction(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "quintessential", 10, 20)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) != 1 {
		t.Fatalf("expected 1 hit, got %d", len(hits))
	}
	h := hits[0]
	// Highlight should be the original-case token from the source text.
	if !strings.Contains(strings.ToLower(h.Snippet.Match), "quintessential") {
		t.Fatalf("highlight should contain the matched token, got %q", h.Snippet.Match)
	}
	// before/after should be substrings of the segment text.
	if h.Snippet.Before != "" && !strings.Contains(h.Segment.Text, h.Snippet.Before) {
		t.Fatalf("before %q not in segment", h.Snippet.Before)
	}
	if h.Snippet.After != "" && !strings.Contains(h.Segment.Text, h.Snippet.After) {
		t.Fatalf("after %q not in segment", h.Snippet.After)
	}
}

func TestIndex_PhraseHighlightSpansFullPhrase(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "horse race", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if len(hits) == 0 {
		t.Fatalf("expected hits")
	}
	top := hits[0]
	hl := strings.ToLower(top.Snippet.Match)
	if !strings.Contains(hl, "horse race") {
		t.Fatalf("phrase highlight should span both terms, got %q", top.Snippet.Match)
	}
}

func TestIndex_EmptyQueryReturnsNothing(t *testing.T) {
	idx := buildFixtureIndex(t)
	hits, err := idx.Query(context.Background(), "  ", 10, 30)
	if err != nil {
		t.Fatalf("Query: %v", err)
	}
	if hits != nil && len(hits) != 0 {
		t.Fatalf("empty query should yield no hits, got %d", len(hits))
	}
}
