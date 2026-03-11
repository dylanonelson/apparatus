# Static publication files

EPUB files and their associated metadata, used by both `publication_api` (for content processing) and `reader_api` (for the publication catalog and LLM context).

## publications.yaml

The publication catalog. Each entry maps a publication ID to its metadata and files.

## EPUB files

Each publication exists in two forms:

- **Packed** (`.epub`): standard ZIP-based EPUB archive, used by `publication_api` for content processing
- **Unpacked** (directory): unzipped EPUB structure, useful for development inspection

The Readium toolkit accepts both formats. Note that internal EPUB structures vary: David Copperfield has content at the root level (`text/`, `css/`, `images/`), while Anna Karenina nests content under an `epub/` subdirectory (`epub/text/`, `epub/css/`, etc.).

## How services access this directory

| Context                     | Path                                                                 |
| --------------------------- | -------------------------------------------------------------------- |
| Local dev (reader_api)      | `reader_api/publications/` -> symlink to `../static`                 |
| Local dev (publication_api) | `publication_api/publications/` -> symlink to `../static`            |
| Docker (publication_api)    | `/data/publications/` (full directory copied at build time)          |
| Docker (reader_api)         | `publications/publications.yaml` (catalog only copied at build time) |
