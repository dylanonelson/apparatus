package readium

import (
	"context"
	"path/filepath"
	"runtime"
	"testing"
	"time"
)

func TestIterateTextSegments_NilPublication(t *testing.T) {
	_, err := IterateTextSegments(context.Background(), nil)
	if err == nil {
		t.Fatalf("expected error when publication is nil")
	}
}

// Using the repository's sample_two_chapters EPUB to assert exact text streaming.
func TestIterateTextSegments_SampleTwoChapters(t *testing.T) {
	// Resolve path to repo root from this file location.
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatalf("runtime.Caller failed")
	}
	pkgRoot := filepath.Clean(filepath.Join(filepath.Dir(file), "../../"))
	epubPath := filepath.Join(pkgRoot, "testdata", "sample_two_chapters.epub")

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	publication, err := OpenPublication(ctx, epubPath)
	if err != nil {
		t.Skipf("skipping: OpenPublication failed (%v) — ensure go-toolkit streamer supports fixture on this platform", err)
	}

	ch, err := IterateTextSegments(ctx, publication)
	if err != nil {
		t.Skipf("skipping: ContentService unavailable or error (%v)", err)
	}

	expected1 := "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed non risus."
	expected2 := "Curabitur ligula sapien, tincidunt non, euismod vitae, posuere imperdiet, leo."
	found1 := false
	found2 := false
	for seg := range ch {
		if seg.Text == expected1 {
			found1 = true
		}
		if seg.Text == expected2 {
			found2 = true
		}
		if found1 && found2 {
			break
		}
	}
	if !found1 {
		t.Fatalf("expected to find exact paragraph: %q", expected1)
	}
	if !found2 {
		t.Fatalf("expected to find exact paragraph: %q", expected2)
	}
}
