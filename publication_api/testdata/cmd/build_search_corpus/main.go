// Command build_search_corpus generates the search_corpus.epub test fixture.
//
// Run from publication_api/:
//
//	go run ./testdata/cmd/build_search_corpus
//
// The generated EPUB is checked into the repo so tests don't depend on this
// program at run time. Re-run when you want to change the fixture content.
//
// The fixture is intentionally synthetic prose with planted test seeds. Each
// chapter is structured to exercise a specific aspect of the search behavior:
//
//	chapter1.xhtml — Stemming: "horse" / "horses" / "horse's" / "ridden"
//	chapter2.xhtml — Phrase order: "horse race" (in-order) vs. "race horse"
//	chapter3.xhtml — Verb stemming: ran / running / runs / run
//	chapter4.xhtml — Rare-term uniqueness: "quintessential" appears exactly once
//	chapter5.xhtml — Ranking: "crowd" appears repeatedly across paragraphs of
//	                 varying length, so BM25 ranking is observable
//	chapter6.xhtml — Stopword behavior: heavy "the"/"is" usage
package main

import (
	"archive/zip"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"runtime"
)

const (
	containerXML = `<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
`

	contentOPF = `<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">search-corpus-001</dc:identifier>
    <dc:title>Search Corpus</dc:title>
    <dc:language>en</dc:language>
    <dc:creator>Apparatus Test Fixture</dc:creator>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter2" href="chapter2.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter3" href="chapter3.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter4" href="chapter4.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter5" href="chapter5.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter6" href="chapter6.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter1"/>
    <itemref idref="chapter2"/>
    <itemref idref="chapter3"/>
    <itemref idref="chapter4"/>
    <itemref idref="chapter5"/>
    <itemref idref="chapter6"/>
  </spine>
</package>
`

	navXHTML = `<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Navigation</title></head>
  <body>
    <nav epub:type="toc" id="toc">
      <h1>Table of Contents</h1>
      <ol>
        <li><a href="chapter1.xhtml">The Stable</a></li>
        <li><a href="chapter2.xhtml">The Race</a></li>
        <li><a href="chapter3.xhtml">The Runner</a></li>
        <li><a href="chapter4.xhtml">The Letter</a></li>
        <li><a href="chapter5.xhtml">The Crowd</a></li>
        <li><a href="chapter6.xhtml">Coda</a></li>
      </ol>
    </nav>
  </body>
</html>
`

	// Chapter 1 — Stemming seeds: horse, horses, horse's, ridden.
	chapter1 = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>The Stable</title></head>
  <body>
    <h1>The Stable</h1>
    <p>Morning light filtered through the gaps in the stable wall, falling in narrow ribbons across the straw. The horse stood quietly in the first stall, its breath rising in faint clouds. Two other horses watched from the far end of the row, their dark eyes patient and unblinking.</p>
    <p>The stableman walked the length of the building, checking each animal in turn. He paused at the first stall and ran a hand along the horse's neck. The coat was warm and dusty from sleep. He had ridden this one many times in his younger days, before his back gave out.</p>
    <p>A bucket scraped on stone. One of the horses shook its head, and a small cloud of hay drifted to the floor. Outside, a magpie called twice, then fell silent. The stableman moved on. He preferred the stable in the morning, when the horses were still drowsy and the world was small.</p>
  </body>
</html>
`

	// Chapter 2 — Phrase order seeds: "horse race" (twice, in order) vs. "race
	// horse" (once, reversed). A phrase query for "horse race" should match the
	// first two paragraphs but not the third's "race horse".
	chapter2 = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>The Race</title></head>
  <body>
    <h1>The Race</h1>
    <p>By midafternoon the stands were full. The horse race drew a crowd of several thousand, and the rumor of a new champion had spread quickly through the surrounding towns. Vendors moved between the rows, calling their wares over the murmur of conversation.</p>
    <p>The animals were brought out one by one to a chorus of cheers. Among them was a bay gelding said to be the finest race horse in three counties, though no one could remember who had first made the claim. The owner stood by the rail in a long brown coat, watching the animal step into position.</p>
    <p>When the bell rang, the horse race began with a single sharp report. For a few seconds nothing seemed to move. Then the field lurched forward as one body, hooves drumming against the track. The crowd surged to its feet. By the first turn the bay gelding had pulled clear, and the cry that went up shook dust from the rafters.</p>
  </body>
</html>
`

	// Chapter 3 — Verb-form seeds: ran, running, runs, run.
	chapter3 = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>The Runner</title></head>
  <body>
    <h1>The Runner</h1>
    <p>Margaret ran every morning before the rest of the house was awake. The path she preferred ran along the river, and in the early light the water was the color of pewter. She had been running this same loop for eleven years, and she could no longer remember a time when she had not run.</p>
    <p>Some mornings the runs were easy, the air sharp and her breath even. Other mornings her legs felt heavy from the start, and she had to argue with herself for the first mile to keep going. She had learned not to trust the early signs. A bad first mile sometimes gave way to the best run of the week.</p>
    <p>What kept her at it was not the running itself but the way it framed the day. To run before breakfast was to claim the morning for one's own life. By the time others were stirring, she had already done the thing she had set out to do. The rest of the day became a different kind of country, more forgiving than it might otherwise have been.</p>
  </body>
</html>
`

	// Chapter 4 — Rare-term uniqueness: "quintessential" appears exactly once.
	chapter4 = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>The Letter</title></head>
  <body>
    <h1>The Letter</h1>
    <p>He took the letter from the tray and weighed it in his hand for a moment before opening it. The paper was thicker than he expected, and the seal was one he had not seen in many years.</p>
    <p>The handwriting was small and even. He read the first paragraph twice, the second only once, and the third he set aside until he could think more clearly. There was a quintessential restraint in the language, the kind he associated with people who had learned early in life that nothing important was ever said directly. The writer described a journey, a quarrel, and a reconciliation, all in the same patient cadence, as if none of it had cost much.</p>
    <p>He folded the letter back along its original creases and placed it in the drawer of his desk. There would be time later to consider what to make of it. For now there was light through the window and tea growing cold in a cup, and a cat asleep on the chair across from him.</p>
  </body>
</html>
`

	// Chapter 5 — Ranking seeds: "crowd" appears many times across paragraphs of
	// very different lengths. BM25 should rank short, term-dense paragraphs above
	// long ones, regardless of document order.
	chapter5 = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>The Crowd</title></head>
  <body>
    <h1>The Crowd</h1>
    <p>The crowd gathered before noon.</p>
    <p>A crowd, thought the speaker, was never the sum of the people in it.</p>
    <p>She watched the crowd from the second-floor window. From this angle the crowd looked smaller than it had sounded from the street, but the murmur that rose from it was unmistakable, and any speaker who took the platform would have to contend with that murmur before saying a single word.</p>
    <p>The crowd shifted as the music began.</p>
    <p>Children moved through the crowd at knee height, holding the hands of adults who did not seem to be paying attention to them. The crowd parted for them and closed again. From above, the pattern was almost orderly.</p>
    <p>A crowd is patient until it isn't.</p>
    <p>By the time the speaker reached the platform, the crowd had grown by perhaps another five hundred. He looked out at it and felt the familiar small fear, the one he had never quite outgrown despite decades of practice. The crowd watched him in return, and he could not say whether it was a friendly crowd or a hostile one, only that it was attentive.</p>
    <p>He cleared his throat. The crowd quieted.</p>
    <p>The crowd was still.</p>
    <p>When he was finished, the crowd did not cheer at first. There was a long pause, of the kind that has shape and weight, and then the applause came, slowly at the edges and then everywhere at once.</p>
  </body>
</html>
`

	// Chapter 6 — Stopword behavior: heavy use of "the" and "is". A query of
	// "the" should return zero hits when the en analyzer's stopword filter is
	// active.
	chapter6 = `<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Coda</title></head>
  <body>
    <h1>Coda</h1>
    <p>The hour is late. The fire is low. The cat is asleep in the chair the boy has long since left empty. The clock on the mantel is the same clock that was there when the boy's grandfather was a boy, and it is still the most reliable thing in the room.</p>
    <p>The book is closed. The lamp is dim. The window is dark. Outside, the world is doing what the world has always done, and inside, nothing is doing very much at all. The quiet is not the absence of sound but a particular sort of presence, and anyone who has known a long evening alone in a small room is familiar with it.</p>
    <p>The page is blank. The pen is uncapped. The hand that holds the pen is older than it used to be, and it is in no special hurry. There is time. The day is over and the night is here, and what one writes in such a moment is rarely what one set out to write.</p>
  </body>
</html>
`
)

type entry struct {
	name    string
	content string
	store   bool // true => no compression (required for mimetype)
}

func main() {
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		log.Fatal("runtime.Caller failed")
	}
	// .../publication_api/testdata/cmd/build_search_corpus/main.go
	// → .../publication_api/testdata
	testdataDir := filepath.Clean(filepath.Join(filepath.Dir(file), "../.."))
	out := filepath.Join(testdataDir, "search_corpus.epub")

	entries := []entry{
		{name: "mimetype", content: "application/epub+zip", store: true},
		{name: "META-INF/container.xml", content: containerXML},
		{name: "OEBPS/content.opf", content: contentOPF},
		{name: "OEBPS/nav.xhtml", content: navXHTML},
		{name: "OEBPS/chapter1.xhtml", content: chapter1},
		{name: "OEBPS/chapter2.xhtml", content: chapter2},
		{name: "OEBPS/chapter3.xhtml", content: chapter3},
		{name: "OEBPS/chapter4.xhtml", content: chapter4},
		{name: "OEBPS/chapter5.xhtml", content: chapter5},
		{name: "OEBPS/chapter6.xhtml", content: chapter6},
	}

	if err := writeEPUB(out, entries); err != nil {
		log.Fatalf("write epub: %v", err)
	}
	fmt.Printf("wrote %s\n", out)
}

func writeEPUB(path string, entries []entry) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()

	zw := zip.NewWriter(f)
	for _, e := range entries {
		method := zip.Deflate
		if e.store {
			method = zip.Store
		}
		hdr := &zip.FileHeader{
			Name:   e.name,
			Method: method,
		}
		w, err := zw.CreateHeader(hdr)
		if err != nil {
			return fmt.Errorf("create %s: %w", e.name, err)
		}
		if _, err := io.WriteString(w, e.content); err != nil {
			return fmt.Errorf("write %s: %w", e.name, err)
		}
	}
	return zw.Close()
}
