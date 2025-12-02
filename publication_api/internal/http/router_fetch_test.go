package httpapi

import (
	"bytes"
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
)

func fetchTestdataDir(t *testing.T) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatalf("runtime.Caller failed")
	}
	return filepath.Clean(filepath.Join(filepath.Dir(file), "../../testdata"))
}

func TestFetchContent_ReturnsFiles(t *testing.T) {
	pubs := fetchTestdataDir(t)
	if err := os.Setenv("PUBLICATIONS_DIR", pubs); err != nil {
		t.Fatalf("set env: %v", err)
	}
	publications.ResetStoreCache()
	defer os.Unsetenv("PUBLICATIONS_DIR")

	r := Router()
	srv := httptest.NewServer(r)
	defer srv.Close()

	req := FetchContentRequest{
		PublicationID: "sample_two_chapters",
		Hrefs:         []string{"OEBPS/chapter1.xhtml"},
	}
	body, _ := json.Marshal(req)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(srv.URL+"/content/fetch", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("post /content/fetch: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status: %d", resp.StatusCode)
	}

	var fcResp FetchContentResponse
	if err := json.NewDecoder(resp.Body).Decode(&fcResp); err != nil {
		t.Fatalf("decode: %v", err)
	}
	if len(fcResp.Files) != 1 {
		t.Fatalf("expected 1 file, got %d", len(fcResp.Files))
	}
	file := fcResp.Files[0]
	if file.Href != "OEBPS/chapter1.xhtml" {
		t.Fatalf("unexpected href: %s", file.Href)
	}
	if file.Encoding != "utf-8" {
		t.Fatalf("expected utf-8 encoding, got %s", file.Encoding)
	}
	if file.Content == "" || file.MediaType == "" {
		t.Fatalf("expected content and media type to be populated")
	}
	if want := "Lorem ipsum dolor sit amet"; !strings.Contains(file.Content, want) {
		t.Fatalf("expected content to include %q", want)
	}
}

func TestFetchContent_LimitsHrefCount(t *testing.T) {
	pubs := fetchTestdataDir(t)
	if err := os.Setenv("PUBLICATIONS_DIR", pubs); err != nil {
		t.Fatalf("set env: %v", err)
	}
	publications.ResetStoreCache()
	defer os.Unsetenv("PUBLICATIONS_DIR")

	r := Router()
	srv := httptest.NewServer(r)
	defer srv.Close()

	req := FetchContentRequest{
		PublicationID: "sample_two_chapters",
		Hrefs:         []string{"a.xhtml", "b.xhtml", "c.xhtml"},
	}
	body, _ := json.Marshal(req)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Post(srv.URL+"/content/fetch", "application/json", bytes.NewReader(body))
	if err != nil {
		t.Fatalf("post /content/fetch: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 for too many hrefs, got %d", resp.StatusCode)
	}
}
