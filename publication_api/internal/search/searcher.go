// Package search builds and queries per-publication full-text indexes over
// EPUB content. The index is a Bleve in-memory inverted index that supports
// English stemming, phrase queries, and BM25 ranking. Snippet construction
// (the before/highlight/after triple returned to callers) lives alongside
// the index in this package and is reused by both the Bleve query path and
// the legacy literal-substring path retained for backward compatibility.
package search

import (
	"strings"
)

// Hit is a snippet-level result: the matched substring of an input text plus
// the surrounding context windows. Locator information is added by callers
// that know about EPUB structure.
type Hit struct {
	Href   string `json:"href"`
	Before string `json:"before"`
	Match  string `json:"highlight"`
	After  string `json:"after"`
}

// FindMatches returns up to maxResults case-insensitive substring matches of
// query within text, with a context window of contextChars characters around
// each match. Retained so callers (and tests) that want literal substring
// matching keep working; the Bleve-backed path calls SnippetFromOffsets.
func FindMatches(text string, query string, maxResults int, contextChars int) []Hit {
	if query == "" || text == "" || maxResults <= 0 {
		return nil
	}
	lowerText := strings.ToLower(text)
	lowerQuery := strings.ToLower(query)
	results := make([]Hit, 0, maxResults)
	start := 0
	for len(results) < maxResults {
		idx := strings.Index(lowerText[start:], lowerQuery)
		if idx < 0 {
			break
		}
		idx += start
		matchEnd := idx + len(query)
		results = append(results, SnippetFromOffsets(text, idx, matchEnd, contextChars))
		start = matchEnd
	}
	return results
}

// SnippetFromOffsets builds a Hit from a known [matchStart, matchEnd) byte
// range within text. Out-of-range offsets are clamped to text boundaries
// so callers don't need to validate token positions reported by an external
// tokenizer.
func SnippetFromOffsets(text string, matchStart, matchEnd, contextChars int) Hit {
	if matchStart < 0 {
		matchStart = 0
	}
	if matchEnd > len(text) {
		matchEnd = len(text)
	}
	if matchStart > matchEnd {
		matchStart = matchEnd
	}

	beforeStart := matchStart - contextChars
	if beforeStart < 0 {
		beforeStart = 0
	}
	afterEnd := matchEnd + contextChars
	if afterEnd > len(text) {
		afterEnd = len(text)
	}

	return Hit{
		Before: strings.TrimSpace(text[beforeStart:matchStart]),
		Match:  text[matchStart:matchEnd],
		After:  strings.TrimSpace(text[matchEnd:afterEnd]),
	}
}
