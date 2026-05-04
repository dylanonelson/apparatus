package search

import (
	"context"
	"sync"
	"time"

	"golang.org/x/sync/singleflight"
)

// IndexCache holds per-publication Bleve indexes in memory. Lookups are
// keyed by publication ID and validated against the source EPUB's mtime;
// if the file has been replaced (e.g. during local development), the next
// lookup rebuilds.
//
// Concurrent first-callers for the same publication are coalesced through
// a singleflight group so we never run the (relatively expensive) build
// twice in parallel.
type IndexCache struct {
	mu    sync.RWMutex
	items map[string]*PublicationIndex // key: publication_id
	sf    singleflight.Group
}

// NewIndexCache returns a fresh, empty cache.
func NewIndexCache() *IndexCache {
	return &IndexCache{items: make(map[string]*PublicationIndex)}
}

// SegmentLoader produces the segment slice for a publication. It is called
// at most once per (publication, mtime) pair across all concurrent callers.
type SegmentLoader func(ctx context.Context) ([]IndexedSegment, error)

// Get returns the cached index for publicationID, building it if absent or
// if the cached entry's recorded mtime differs from epubMtime.
func (c *IndexCache) Get(
	ctx context.Context,
	publicationID string,
	epubMtime time.Time,
	load SegmentLoader,
) (*PublicationIndex, error) {
	if cached := c.lookup(publicationID, epubMtime); cached != nil {
		return cached, nil
	}

	v, err, _ := c.sf.Do(publicationID, func() (any, error) {
		// Re-check under singleflight: a sibling caller may have just built it.
		if cached := c.lookup(publicationID, epubMtime); cached != nil {
			return cached, nil
		}
		segments, err := load(ctx)
		if err != nil {
			return nil, err
		}
		idx, err := BuildIndex(ctx, segments)
		if err != nil {
			return nil, err
		}
		idx.Mtime = epubMtime
		c.store(publicationID, idx)
		return idx, nil
	})
	if err != nil {
		return nil, err
	}
	return v.(*PublicationIndex), nil
}

// Reset clears all cached indexes. Useful for tests.
func (c *IndexCache) Reset() {
	c.mu.Lock()
	c.items = make(map[string]*PublicationIndex)
	c.mu.Unlock()
}

func (c *IndexCache) lookup(publicationID string, epubMtime time.Time) *PublicationIndex {
	c.mu.RLock()
	defer c.mu.RUnlock()
	existing, ok := c.items[publicationID]
	if !ok {
		return nil
	}
	if !existing.Mtime.Equal(epubMtime) {
		return nil
	}
	return existing
}

func (c *IndexCache) store(publicationID string, idx *PublicationIndex) {
	c.mu.Lock()
	c.items[publicationID] = idx
	c.mu.Unlock()
}
