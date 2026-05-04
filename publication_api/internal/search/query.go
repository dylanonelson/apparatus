package search

import (
	"context"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/analysis/lang/en"
	"github.com/blevesearch/bleve/v2/search"
	"github.com/blevesearch/bleve/v2/search/query"
)

// QueryHit is a search result paired with its originating segment so that
// callers can lift locator fields (href, position, css selector) without a
// second lookup.
type QueryHit struct {
	Segment IndexedSegment
	Snippet Hit
	Score   float64
}

// Query runs a search against a built PublicationIndex.
//
// Query semantics:
//   - Single-token queries (after whitespace splitting) become a Bleve
//     match query, which applies the en analyzer to both the query and
//     the indexed text — so "horse" matches "horses", "running" matches
//     "ran", etc.
//   - Multi-token queries become a match-phrase query, which preserves
//     order: "horse race" matches "the horse raced" but not "race horse".
//
// Results are returned in BM25 score order (highest first), capped at
// maxResults.
func (idx *PublicationIndex) Query(
	ctx context.Context,
	queryStr string,
	maxResults int,
	contextChars int,
) ([]QueryHit, error) {
	queryStr = strings.TrimSpace(queryStr)
	if queryStr == "" || maxResults <= 0 {
		return nil, nil
	}

	q := buildQuery(queryStr)
	req := bleve.NewSearchRequest(q)
	req.Size = maxResults
	req.Fields = []string{"text"}
	req.IncludeLocations = true

	res, err := idx.Index.SearchInContext(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("bleve search: %w", err)
	}

	hits := make([]QueryHit, 0, len(res.Hits))
	for _, h := range res.Hits {
		segIdx, err := strconv.Atoi(h.ID)
		if err != nil || segIdx < 0 || segIdx >= len(idx.Segments) {
			continue
		}
		seg := idx.Segments[segIdx]

		matchStart, matchEnd := highlightSpan(h.Locations, seg.Text)
		snippet := SnippetFromOffsets(seg.Text, matchStart, matchEnd, contextChars)
		hits = append(hits, QueryHit{
			Segment: seg,
			Snippet: snippet,
			Score:   h.Score,
		})
	}
	return hits, nil
}

// buildQuery picks between a match query and a match-phrase query based on
// whether the input has multiple whitespace-separated tokens. Both queries
// are scoped to the "text" field and use the English analyzer.
func buildQuery(queryStr string) query.Query {
	tokens := strings.Fields(queryStr)
	if len(tokens) <= 1 {
		mq := bleve.NewMatchQuery(queryStr)
		mq.SetField("text")
		mq.Analyzer = en.AnalyzerName
		return mq
	}
	pq := bleve.NewMatchPhraseQuery(queryStr)
	pq.SetField("text")
	pq.Analyzer = en.AnalyzerName
	return pq
}

// highlightSpan picks the byte range to highlight for a hit.
//
// Bleve returns a Locations map (field → term → []Location) where each
// Location has byte offsets and a token position (Pos). For single-term
// matches we just use the earliest term's offsets. For phrase matches we
// find the earliest contiguous run of token positions across all terms
// (since a phrase match guarantees consecutive Pos values) and highlight
// from the run's first Start to its last End.
//
// If something unexpected happens (no locations, no contiguous run), we
// fall back to highlighting the earliest single-term match. As a final
// fallback we return (0, 0) which produces an empty highlight; the
// before/after window logic handles that gracefully.
func highlightSpan(locs search.FieldTermLocationMap, text string) (int, int) {
	termLocs := locs["text"]
	if len(termLocs) == 0 {
		return 0, 0
	}

	// Flatten all locations and sort by token position.
	type entry struct {
		pos        uint64
		start, end int
	}
	var all []entry
	for _, ls := range termLocs {
		for _, l := range ls {
			all = append(all, entry{
				pos:   l.Pos,
				start: int(l.Start),
				end:   int(l.End),
			})
		}
	}
	if len(all) == 0 {
		return 0, 0
	}
	sort.Slice(all, func(i, j int) bool { return all[i].pos < all[j].pos })

	if len(termLocs) > 1 {
		// Phrase query: find the earliest contiguous run of consecutive Pos
		// values whose length matches the term count.
		runStart := 0
		for runStart < len(all) {
			runEnd := runStart
			for runEnd+1 < len(all) && all[runEnd+1].pos == all[runEnd].pos+1 {
				runEnd++
			}
			if runEnd-runStart+1 >= len(termLocs) {
				return all[runStart].start, all[runStart+len(termLocs)-1].end
			}
			runStart = runEnd + 1
		}
		// Fall through to single-term fallback below if no full run found.
	}

	first := all[0]
	if first.start < 0 || first.end > len(text) || first.start > first.end {
		return 0, 0
	}
	return first.start, first.end
}
