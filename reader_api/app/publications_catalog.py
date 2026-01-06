import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


class CatalogError(Exception):
    """Base error raised when the publications catalog cannot be loaded."""


class UnknownPublicationError(CatalogError):
    """Raised when a publication ID is not found in the catalog."""


@dataclass(frozen=True)
class PublicationMetadata:
    identifier: str
    title: str
    author: str
    filename: str
    context_filename: str | None = None

    def resolve_path(self, base_directory: Path) -> Path:
        """Return the absolute path to the publication file within the base directory."""
        return base_directory / self.filename

    def resolve_context_path(self, base_directory: Path) -> Path | None:
        """Return the absolute path to the context file, or None if no context file is configured."""
        if self.context_filename is None:
            return None
        return base_directory / self.context_filename


@dataclass
class Catalog:
    metadata_map: dict[str, PublicationMetadata]
    catalog_path: Path
    catalog_base_path: Path


def _default_catalog_path() -> Path:
    """
    Resolve the catalog path.

    Prefers PUBLICATIONS_CATALOG_PATH if set, otherwise looks for `publications/publications.yaml`
    relative to the service root. As a final fallback, it checks the repo-level `static` directory.
    """
    env_path = os.getenv("PUBLICATIONS_CATALOG_PATH")
    if env_path:
        return Path(env_path).expanduser()

    service_root = Path(__file__).resolve().parent.parent
    candidate = service_root / "publications" / "publications.yaml"
    if candidate.exists():
        return candidate

    fallback = service_root.parent / "static" / "publications.yaml"
    if fallback.exists():
        return fallback

    raise CatalogError(
        "Unable to locate publications catalog. "
        "Set PUBLICATIONS_CATALOG_PATH or ensure publications/publications.yaml exists."
    )


def _load_catalog_from_file(path: Path) -> Catalog:
    if not path.exists():
        raise CatalogError(f"Catalog file does not exist: {path}")

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw_data is None:
        raise CatalogError("Catalog file is empty")
    if not isinstance(raw_data, list):
        raise CatalogError("Catalog must be a list of publication entries")

    metadata_map: dict[str, PublicationMetadata] = {}
    for entry in raw_data:
        if not isinstance(entry, dict):
            raise CatalogError("Catalog entries must be dictionaries")

        required_keys = {"id", "title", "author", "filename"}
        missing = required_keys - set(entry.keys())
        if missing:
            raise CatalogError(
                f"Catalog entry missing keys: {', '.join(sorted(missing))}"
            )

        identifier = str(entry["id"]).strip()
        title = str(entry["title"]).strip()
        author = str(entry["author"]).strip()
        filename = str(entry["filename"]).strip()
        context_filename = entry.get("contextFilename")
        if context_filename is not None:
            context_filename = str(context_filename).strip() or None

        if not identifier:
            raise CatalogError("Catalog entry has empty id")
        if not filename:
            raise CatalogError(
                f"Catalog entry '{identifier}' has empty filename"
            )

        metadata = PublicationMetadata(
            identifier=identifier,
            title=title,
            author=author,
            filename=filename,
            context_filename=context_filename,
        )
        metadata_map[identifier] = metadata

    return Catalog(
        metadata_map=metadata_map,
        catalog_path=path,
        catalog_base_path=path.parent,
    )


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Return the publications catalog keyed by identifier."""
    catalog_path = _default_catalog_path()
    return _load_catalog_from_file(catalog_path)


def get_publication(publication_id: str) -> PublicationMetadata:
    """Retrieve metadata for a specific publication identifier."""
    catalog = get_catalog()
    metadata_map = catalog.metadata_map
    if publication_id not in metadata_map:
        raise UnknownPublicationError(
            f"Publication not found for id '{publication_id}'"
        )
    return metadata_map[publication_id]


def get_publications_base_directory() -> Path:
    """
    Return the base directory where publication files and context files are located.
    This is the parent directory of the catalog file.
    """
    return get_catalog().catalog_base_path


def reload_catalog() -> None:
    """Clear the cached catalog to force a reload (useful in tests)."""
    get_catalog.cache_clear()
