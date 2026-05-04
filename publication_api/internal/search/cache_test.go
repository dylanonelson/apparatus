package search

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestCache_HitReturnsSamePointer(t *testing.T) {
	c := NewIndexCache()
	mtime := time.Unix(1000, 0)
	loader := func(ctx context.Context) ([]IndexedSegment, error) {
		return fixtureSegments(), nil
	}

	first, err := c.Get(context.Background(), "p1", mtime, loader)
	if err != nil {
		t.Fatalf("first Get: %v", err)
	}
	second, err := c.Get(context.Background(), "p1", mtime, loader)
	if err != nil {
		t.Fatalf("second Get: %v", err)
	}
	if first != second {
		t.Fatalf("expected same *PublicationIndex on cache hit; got distinct pointers")
	}
}

func TestCache_MtimeChangeRebuilds(t *testing.T) {
	c := NewIndexCache()
	loader := func(ctx context.Context) ([]IndexedSegment, error) {
		return fixtureSegments(), nil
	}

	mtime1 := time.Unix(1000, 0)
	first, err := c.Get(context.Background(), "p1", mtime1, loader)
	if err != nil {
		t.Fatalf("first Get: %v", err)
	}

	mtime2 := time.Unix(2000, 0)
	second, err := c.Get(context.Background(), "p1", mtime2, loader)
	if err != nil {
		t.Fatalf("second Get: %v", err)
	}
	if first == second {
		t.Fatalf("expected rebuild on mtime change; got same pointer")
	}
	if !second.Mtime.Equal(mtime2) {
		t.Fatalf("rebuilt index has wrong mtime: got %v want %v", second.Mtime, mtime2)
	}
}

func TestCache_DifferentPublicationsAreSeparate(t *testing.T) {
	c := NewIndexCache()
	mtime := time.Unix(1000, 0)
	loader := func(ctx context.Context) ([]IndexedSegment, error) {
		return fixtureSegments(), nil
	}

	a, err := c.Get(context.Background(), "p1", mtime, loader)
	if err != nil {
		t.Fatalf("p1: %v", err)
	}
	b, err := c.Get(context.Background(), "p2", mtime, loader)
	if err != nil {
		t.Fatalf("p2: %v", err)
	}
	if a == b {
		t.Fatalf("expected separate indexes for different publication ids")
	}
}

func TestCache_ConcurrentBuildSingleflight(t *testing.T) {
	c := NewIndexCache()
	mtime := time.Unix(1000, 0)
	var calls int64
	gate := make(chan struct{})
	loader := func(ctx context.Context) ([]IndexedSegment, error) {
		// Block until released so all goroutines pile up at the singleflight
		// barrier; only one of them should reach the loader.
		<-gate
		atomic.AddInt64(&calls, 1)
		return fixtureSegments(), nil
	}

	const N = 50
	var wg sync.WaitGroup
	results := make([]*PublicationIndex, N)
	errs := make([]error, N)
	for i := 0; i < N; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			results[i], errs[i] = c.Get(context.Background(), "p1", mtime, loader)
		}(i)
	}

	// Give all goroutines a chance to enter Get and queue at the singleflight.
	time.Sleep(20 * time.Millisecond)
	close(gate)
	wg.Wait()

	for i, err := range errs {
		if err != nil {
			t.Fatalf("goroutine %d: %v", i, err)
		}
	}
	for i := 1; i < N; i++ {
		if results[i] != results[0] {
			t.Fatalf("goroutines %d and 0 got distinct *PublicationIndex pointers", i)
		}
	}
	if got := atomic.LoadInt64(&calls); got != 1 {
		t.Fatalf("expected exactly 1 loader invocation under singleflight, got %d", got)
	}
}

func TestCache_Reset(t *testing.T) {
	c := NewIndexCache()
	mtime := time.Unix(1000, 0)
	var calls int64
	loader := func(ctx context.Context) ([]IndexedSegment, error) {
		atomic.AddInt64(&calls, 1)
		return fixtureSegments(), nil
	}

	if _, err := c.Get(context.Background(), "p1", mtime, loader); err != nil {
		t.Fatalf("Get: %v", err)
	}
	c.Reset()
	if _, err := c.Get(context.Background(), "p1", mtime, loader); err != nil {
		t.Fatalf("Get after reset: %v", err)
	}
	if got := atomic.LoadInt64(&calls); got != 2 {
		t.Fatalf("expected loader called twice across Reset, got %d", got)
	}
}
