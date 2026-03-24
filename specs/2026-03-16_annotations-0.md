# Annotations: Backend API Support

Add API support for user annotations (highlights and notes) in the reader API. This is backend-only; no frontend changes are included.

## Background

Annotations are a core e-reading feature (cf. Kindle highlights/notes). Users should be able to highlight passages in multiple colors and optionally attach notes.

## Data model

### New table: `annotations`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | NO | Primary key (uuid4) |
| `user_id` | `UUID` (FK → `users.id`) | NO | Owning user |
| `publication_id` | `VARCHAR(255)` | NO | Publication identifier |
| `locator` | `JSON` | NO | Readium locator object pinpointing the annotated passage. Uses the same `LocatorModel` schema as reading locations — `href`, `type`, `locations` (with `fragments`, `position`, `progression`), and `text` (with `before`, `highlight`, `after`). The `text.highlight` field captures the highlighted passage text. |
| `color` | `VARCHAR(32)`, Enum | NO | Highlight color. One of: `yellow`, `blue`, `green`, `pink`, `purple` |
| `user_note` | `TEXT` | YES | User-authored note attached to the highlight |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NO | Server default `now()` |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NO | Server default `now()`, auto-updates on change |

### Indexes

- `ix_annotations_user_pub` — (`user_id`, `publication_id`) — primary query path: list annotations for a book
- `ix_annotations_user_pub_created` — (`user_id`, `publication_id`, `created_at`) — paginated listing ordered by creation time
- `ix_annotations_user_created` — (`user_id`, `created_at`) — cross-publication listing

### Enum types (Postgres)

- `annotation_color`: `yellow`, `blue`, `green`, `pink`, `purple`

## API endpoints

All endpoints are under `/api` and require Auth0 JWT authentication (same pattern as existing routes).

### `POST /api/annotations`

Create a new annotation.

**Request body** (`CreateAnnotationRequestModel`):
```json
{
  "publication_id": "string",
  "locator": { /* LocatorModel — reuse existing model */ },
  "color": "yellow",
  "user_note": "Optional note text"
}
```

**Response** (`AnnotationResponseModel`): 201 Created with the full annotation object.

### `GET /api/annotations`

List annotations for the authenticated user.

**Query parameters**:
- `publication_id` (required) — filter by publication
- `color` (optional) — filter by highlight color
- `limit` (optional, default 100, max 500) — page size
- `offset` (optional, default 0) — pagination offset

**Response**: `list[AnnotationResponseModel]`, ordered by `created_at` ascending.

### `GET /api/annotations/{annotation_id}`

Get a single annotation by ID. Returns 404 if not found or not owned by the authenticated user.

**Response**: `AnnotationResponseModel`

### `PATCH /api/annotations/{annotation_id}`

Update an annotation's mutable fields.

**Request body** (`UpdateAnnotationRequestModel`):
```json
{
  "locator": { /* LocatorModel — optional, to reposition the highlight */ },
  "color": "blue",
  "user_note": "Updated note text"
}
```

All fields are optional. `locator`, `color`, and `user_note` can be updated — `publication_id` is immutable after creation.

**Response**: `AnnotationResponseModel`

### `DELETE /api/annotations/{annotation_id}`

Delete an annotation. Returns 204 No Content. Returns 404 if not found or not owned by the authenticated user.

## Pydantic models (`api_models.py`)

### `AnnotationColor(str, Enum)`
Values: `yellow`, `blue`, `green`, `pink`, `purple`

### `CreateAnnotationRequestModel(BaseModel)`
Fields: `publication_id`, `locator: LocatorModel`, `color: AnnotationColor`, `user_note: str | None = None`

### `UpdateAnnotationRequestModel(BaseModel)`
Fields: `locator: LocatorModel | None = None`, `color: AnnotationColor | None = None`, `user_note: str | None = None`

### `AnnotationResponseModel(BaseModel)`
Fields: `id: UUID`, `publication_id`, `locator: LocatorModel`, `color: AnnotationColor`, `user_note: str | None`, `created_at: datetime`, `updated_at: datetime`

Config: `from_attributes = True`

## Design decisions

1. **Single locator per annotation**: Each annotation stores one Readium locator. This keeps the model simple and matches how other e-readers work — a highlight is a contiguous passage within a single spine item. The `text.highlight` field in the locator captures the highlighted text, while `locations.fragments` (e.g., epubcfi) pins the exact range.

2. **Color as an enum, not freeform**: Starting with 5 fixed colors keeps the UI consistent. Adding colors later is a schema migration but a small one (add enum value). The 5 colors (`yellow`, `blue`, `green`, `pink`, `purple`) are standard across e-readers.

3. **Locator is mutable**: Users can update the locator to reposition a highlight (e.g., to adjust the selection range). Publication ID remains immutable since moving an annotation across books doesn't make sense.

4. **Ownership enforcement**: All endpoints scope queries to the authenticated user's ID. There is no admin or shared-annotations concept yet.

## Out of scope

- Frontend UI for annotations
- AI-generated annotations (future consideration)
- Annotation export (e.g., Markdown, CSV)
- Shared/social annotations
- Annotations spanning multiple spine items (cross-chapter highlights)
- Full-text search within annotations
