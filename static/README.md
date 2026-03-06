# Static publication files

EPUB files and their associated metadata, used by both `publication_api` (for content processing) and `reader_api` (for the publication catalog and LLM context). Both services access this directory via a `publications` symlink in their own directories.

## Contents

```
static/
├── publications.yaml                # Publication catalog
├── anna-karenina.epub               # Packed EPUB
├── anna-karenina/                   # Unpacked EPUB directory
├── anna-karenina-context.yaml       # LLM context (placeholder)
├── david-copperfield.epub           # Packed EPUB
├── david-copperfield/               # Unpacked EPUB directory
└── david-copperfield-context.yaml   # LLM context (chapter summaries)
```

## publications.yaml

The publication catalog. Each entry maps a publication ID to its metadata and files:

```yaml
- id: "david-copperfield_std-ebks-2025"    # Unique identifier used by API endpoints
  title: "David Copperfield"               # Display title
  urlSlug: "david-copperfield"             # URL slug for frontend routing
  author: "Charles Dickens"                # Author name
  filename: "david-copperfield.epub"       # EPUB filename (relative to this directory)
  contextFilename: "david-copperfield-context.yaml"  # Optional LLM context file
```

All fields except `contextFilename` are required. The `id` is used in API requests (`publication_id` parameter). The `urlSlug` is used in frontend URLs (`/read/{urlSlug}`).

## Context files

Per-publication YAML files that give the LLM chapter-level summaries and position metadata. These improve answer quality for AI-powered Q&A by letting the model understand book structure without reading the full text.

Each entry describes a section of the book:

```yaml
- href: epub/text/chapter-1.xhtml    # Path within the EPUB
  title: "Chapter 1"                 # Human-readable section name
  start_position: 9                  # Starting position in reading order
  last_position: 15                  # Ending position
  summary: |                         # AI-generated summary of the section
    Chapter 1 introduces...
```

Entries can be nested using a `children` key for hierarchical structure (e.g., parts containing chapters).

Context files are optional. If omitted, the LLM works with book content only (fetched via `publication_api` search and content endpoints).

## EPUB files

Each publication exists in two forms:

- **Packed** (`.epub`): standard ZIP-based EPUB archive, used by `publication_api` for content processing
- **Unpacked** (directory): unzipped EPUB structure, useful for development inspection

The Readium toolkit accepts both formats. Note that internal EPUB structures vary: David Copperfield has content at the root level (`text/`, `css/`, `images/`), while Anna Karenina nests content under an `epub/` subdirectory (`epub/text/`, `epub/css/`, etc.).

## Adding a new book

1. **Get the EPUB file** (e.g., from [Standard Ebooks](https://standardebooks.org/)) and place it in this directory:

   ```bash
   cp my-book.epub static/
   ```

2. **Add a catalog entry** in `publications.yaml`:

   ```yaml
   - id: "my-book_std-ebks-2025"
     title: "My Book"
     urlSlug: "my-book"
     author: "Author Name"
     filename: "my-book.epub"
     contextFilename: "my-book-context.yaml"  # optional
   ```

3. **Create a context file** (optional but recommended for better AI answers):

   ```bash
   # Generate summaries for each chapter
   touch static/my-book-context.yaml
   ```

   Populate it with entries following the format above. The `href`, `start_position`, and `last_position` values must match the EPUB's internal structure.

4. **Update the frontend** library page to include the new book (in `frontend/src/app/page.tsx`) and add a cover image to `frontend/public/covers/`.

5. **Test** that the publication is accessible:

   ```bash
   curl -X POST http://127.0.0.1:8091/search \
     -H "Content-Type: application/json" \
     -d '{"publication_id": "my-book_std-ebks-2025", "query": "test", "max_results": 5}'
   ```

Changes are picked up automatically in local development (services read from the symlink). Docker containers require a rebuild.

## How services access this directory

| Context | Path |
|---------|------|
| Local dev (reader_api) | `reader_api/publications/` -> symlink to `../static` |
| Local dev (publication_api) | `publication_api/publications/` -> symlink to `../static` |
| Docker (publication_api) | `/data/publications/` (full directory copied at build time) |
| Docker (reader_api) | `publications/publications.yaml` (catalog only copied at build time) |
