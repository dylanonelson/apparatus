package search

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/analysis/lang/en"
	"github.com/blevesearch/bleve/v2/mapping"
)

// IndexedSegment is the unit of indexing: a textual segment from a publication
// paired with the locator information needed to reconstruct a search hit.
//
// One IndexedSegment becomes one Bleve document. The document ID is the
// segment's index in the Segments slice on PublicationIndex; given a query
// hit, we look up the segment by that index rather than re-deserializing
// fields from Bleve. This keeps the segment struct as the source of truth
// for snippet extraction and locator reconstruction.
type IndexedSegment struct {
	Text        string
	Href        string
	MediaType   string
	Position    *int
	CSSSelector string
}

// PublicationIndex is a built-and-ready inverted index for a single
// publication, plus the original segments (so we can rebuild snippets
// from byte offsets returned by Bleve).
type PublicationIndex struct {
	Index    bleve.Index
	Segments []IndexedSegment
	BuiltAt  time.Time
	Mtime    time.Time // mtime of the source EPUB at build time, for invalidation
}

// segmentDocument is the shape we hand to Bleve. Only Text is analyzed;
// everything else is stored only and surfaced via the segment-id lookup.
// We don't actually depend on Bleve to give us back href/position/etc;
// the doc ID does that. Storing them is belt-and-suspenders for debugging
// (you can dump the index and see what's in it).
type segmentDocument struct {
	Text        string  `json:"text"`
	Href        string  `json:"href"`
	MediaType   string  `json:"media_type"`
	CSSSelector string  `json:"css_selector"`
	Position    float64 `json:"position"`
}

// buildIndexMapping constructs the Bleve index mapping. The text field uses
// the English analyzer (Porter stemmer + lowercase + English stop words);
// other fields are stored-only.
func buildIndexMapping() *mapping.IndexMappingImpl {
	textFM := bleve.NewTextFieldMapping()
	textFM.Analyzer = en.AnalyzerName
	textFM.Store = true
	textFM.IncludeTermVectors = true // required for IncludeLocations to return offsets

	storedFM := bleve.NewTextFieldMapping()
	storedFM.Index = false
	storedFM.Store = true
	storedFM.IncludeTermVectors = false
	storedFM.IncludeInAll = false

	numFM := bleve.NewNumericFieldMapping()
	numFM.Index = false
	numFM.Store = true
	numFM.IncludeInAll = false

	docMapping := bleve.NewDocumentMapping()
	docMapping.AddFieldMappingsAt("text", textFM)
	docMapping.AddFieldMappingsAt("href", storedFM)
	docMapping.AddFieldMappingsAt("media_type", storedFM)
	docMapping.AddFieldMappingsAt("css_selector", storedFM)
	docMapping.AddFieldMappingsAt("position", numFM)

	m := bleve.NewIndexMapping()
	m.DefaultMapping = docMapping
	m.DefaultAnalyzer = en.AnalyzerName
	return m
}

// BuildIndex constructs an in-memory Bleve index over the given segments.
// The caller retains ownership of segments; they are referenced by the
// returned PublicationIndex and used to rebuild snippets at query time.
func BuildIndex(ctx context.Context, segments []IndexedSegment) (*PublicationIndex, error) {
	idx, err := bleve.NewMemOnly(buildIndexMapping())
	if err != nil {
		return nil, fmt.Errorf("build mem index: %w", err)
	}

	batch := idx.NewBatch()
	for i, seg := range segments {
		if err := ctx.Err(); err != nil {
			return nil, err
		}
		var pos float64
		if seg.Position != nil {
			pos = float64(*seg.Position)
		}
		doc := segmentDocument{
			Text:        seg.Text,
			Href:        seg.Href,
			MediaType:   seg.MediaType,
			CSSSelector: seg.CSSSelector,
			Position:    pos,
		}
		if err := batch.Index(strconv.Itoa(i), doc); err != nil {
			return nil, fmt.Errorf("index doc %d: %w", i, err)
		}
	}
	if err := idx.Batch(batch); err != nil {
		return nil, fmt.Errorf("commit batch: %w", err)
	}

	return &PublicationIndex{
		Index:    idx,
		Segments: segments,
		BuiltAt:  time.Now(),
	}, nil
}
