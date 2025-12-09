from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponseModel(BaseModel):
    ok: bool
    timestamp_ms: int


class LocationsModel(BaseModel):
    """
    Locations object within a Locator
    https://readium.org/architecture/models/locators/
    """

    fragments: list[str] | None = Field(
        None,
        description="Fragments (e.g., epubcfi) pointing into the resource.",
        examples=[["epubcfi(/6/4!/2)"]],
    )
    position: int | None = Field(
        None,
        description="Position within the publication spine (e.g., page number).",
        examples=[12],
    )
    progression: float | None = Field(
        None,
        description="Progression within the resource (0.0-1.0).",
        examples=[0.42],
    )
    totalProgression: float | None = Field(
        None,
        description="Progression within the entire publication (0.0-1.0).",
        examples=[0.27],
    )


class TextModel(BaseModel):
    """
    Text context object within a Locator
    https://readium.org/architecture/models/locators/
    """

    before: str | None = Field(
        None,
        description="Text immediately preceding the locator.",
        examples=["He opened the door and"],
    )
    highlight: str | None = Field(
        None,
        description="Text highlighted at the locator.",
        examples=["stepped into the bright sunlight"],
    )
    after: str | None = Field(
        None,
        description="Text immediately after the locator.",
        examples=["not knowing what he'd find next."],
    )


class LocatorModel(BaseModel):
    """
    Readium Web Publication Manifest Locator
    https://readium.org/architecture/models/locators/#the-locator-object
    """

    href: str = Field(
        ...,
        description="Spine item href for the current location.",
        examples=["/text/chapter1.xhtml"],
    )
    type: str = Field(
        ...,
        description="Media type of the resource.",
        examples=["application/xhtml+xml"],
    )
    title: str | None = Field(
        None,
        description="Optional title for the chapter/section.",
        examples=["Chapter 1"],
    )

    # Locations object - one or more ways to locate a position
    locations: LocationsModel | None = Field(
        None,
        description="Ways to locate a position within the resource.",
    )
    text: TextModel | None = Field(
        None,
        description="Optional text context around the locator.",
    )


class ViewportPayloadModel(BaseModel):
    positions: list[int] = Field(
        ...,
        description=(
            "Ordered character offsets in the current spine item that are visible "
            "in the viewport."
        ),
        examples=[[0, 120]],
    )
    text: str = Field(
        ...,
        description="Visible text snippet for the user's current viewport.",
        examples=[
            "It was a bright cold day in April, and the clocks were striking thirteen."
        ],
    )
    selection_text: str | None = Field(
        None,
        description=(
            "The text that the user currently has selected from their current viewport"
        ),
        examples=["thirteen"],
    )


class StoreReadingStateRequestModel(BaseModel):
    publication_id: str = Field(
        ...,
        description="Publication identifier associated with the reading state.",
    )
    locator: LocatorModel = Field(
        ...,
        description="Locator describing the user's current position.",
    )
    recorded_at: datetime | None = Field(
        None,
        description="Timestamp when the reading state was captured.",
    )
    viewport: ViewportPayloadModel | None = Field(
        None,
        description="Optional viewport text and positions snapshot.",
    )


class ReadingLocationResponseModel(BaseModel):
    id: UUID
    publication_id: str = Field(
        ...,
        description="Publication identifier for this reading location.",
    )
    locator: LocatorModel = Field(
        ...,
        description="Locator describing the user's latest known position.",
    )
    recorded_at: datetime | None = Field(
        None,
        description="Timestamp when the reading location was captured.",
    )
    created_at: datetime | None = Field(
        None,
        description="Timestamp when the reading location was stored.",
    )

    model_config = {
        "from_attributes": True,
    }


class ViewportResponseModel(BaseModel):
    id: UUID
    publication_id: str = Field(
        ...,
        description="Publication identifier for the viewport snapshot.",
    )
    positions: list[int] = Field(
        ...,
        description="Ordered character offsets visible in the viewport.",
        examples=[[0, 120]],
    )
    text: str = Field(
        ...,
        description="Visible text snippet captured from the viewport.",
        examples=[
            "It was a bright cold day in April, and the clocks were striking thirteen."
        ],
    )
    selection_text: str | None = Field(
        None,
        description=(
            "The text that the user currently has selected from their current viewport"
        ),
        examples=["thirteen"],
    )
    recorded_at: datetime | None = Field(
        None,
        description="Timestamp when the viewport was captured.",
    )
    updated_at: datetime | None = Field(
        None,
        description="Timestamp when the viewport was last updated.",
    )


class ReadingStateResponseModel(BaseModel):
    reading_location: ReadingLocationResponseModel = Field(
        ...,
        description="Latest known reading location for the user.",
    )
    viewport: ViewportResponseModel | None = Field(
        None,
        description="Viewport text and offsets associated with the location, if available.",
    )


class ReadingStatePayload(BaseModel):
    reading_location: ReadingLocationResponseModel | None = Field(
        None,
        description="Latest known reading location; null if none is saved for the user.",
    )
    viewport: ViewportResponseModel | None = Field(
        None,
        description="Viewport text and offsets linked to the reading location, if available.",
    )


class AskRequestModel(BaseModel):
    question: str
    locator: LocatorModel
    publication_id: str


class AskResponseModel(BaseModel):
    answer: str


class UserResponseModel(BaseModel):
    email: str | None = None
    display_name: str | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
