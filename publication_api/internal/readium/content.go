package readium

import (
	"context"
	"fmt"

	"github.com/readium/go-toolkit/pkg/content/element"
	"github.com/readium/go-toolkit/pkg/manifest"
	"github.com/readium/go-toolkit/pkg/pub"
)

// Segment represents a textual content segment with an associated locator.
type Segment struct {
	Text    string
	Locator manifest.Locator
}

// LoadAllSegments materializes every text segment in publication into a
// slice. Use it when you need to consume the whole publication (e.g. when
// building a search index); for streaming use IterateTextSegments.
func LoadAllSegments(ctx context.Context, publication *pub.Publication) ([]Segment, error) {
	ch, err := IterateTextSegments(ctx, publication)
	if err != nil {
		return nil, err
	}
	var segs []Segment
	for s := range ch {
		segs = append(segs, s)
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	return segs, nil
}

// IterateTextSegments returns a channel that lazily yields text segments.
// The iteration stops when the context is cancelled or all elements are consumed.
func IterateTextSegments(ctx context.Context, publication *pub.Publication) (<-chan Segment, error) {
	if publication == nil {
		return nil, fmt.Errorf("publication is nil")
	}
	svc := publication.FindService(pub.ContentService_Name)
	if svc == nil {
		return nil, fmt.Errorf("content service unavailable")
	}
	iter := svc.(pub.ContentService).Content(nil).Iterator()

	out := make(chan Segment, 1)

	go func() {
		defer close(out)
		for {
			ok, err := iter.HasNext(ctx)
			if !ok || err != nil {
				return
			}
			el := iter.Next()
			if te, ok := el.(element.TextualElement); ok {
				txt := te.Text()
				if txt == "" {
					continue
				}
				seg := Segment{Text: txt, Locator: te.Locator()}
				select {
				case <-ctx.Done():
					return
				case out <- seg:
				}
			}
		}
	}()

	return out, nil
}
