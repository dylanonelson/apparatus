from __future__ import annotations

import asyncio

import pytest
from fastmcp.server.auth import AccessToken

from tests.conftest import TestApp


def test_download_publication_files_tool_returns_files(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        helper = test_app
        helper.set_claims({"sub": "auth0|mcp-download"})

        from app.mcp import mcp_server as mcp_module
        from app import main as main_module

        monkeypatch.setattr(
            mcp_module,
            "get_access_token",
            lambda: AccessToken(
                token="token",
                client_id="client",
                scopes=["openid"],
                claims={"sub": "auth0|mcp-download"},
            ),
        )

        sample_files: dict[str, object] = {
            "files": [
                {
                    "href": "chapter1.xhtml",
                    "media_type": "application/xhtml+xml",
                    "encoding": "utf-8",
                    "content": "<html>...</html>",
                }
            ]
        }

        async def _fetch_files(
            publication_id: str, hrefs: list[str]
        ) -> dict[str, object]:
            return sample_files

        monkeypatch.setattr(mcp_module, "fetch_publication_files", _fetch_files)

        result = await main_module.download_publication_files_tool.fn(
            publication_id="sample_two_chapters",
            hrefs=["chapter1.xhtml"],
        )

        assert result["files"][0]["href"] == "chapter1.xhtml"
        assert result["files"][0]["encoding"] == "utf-8"

    asyncio.run(scenario())


def test_download_publication_files_tool_validates_hrefs(
    test_app: TestApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        from app.mcp import mcp_server as mcp_module
        from app import main as main_module

        monkeypatch.setattr(
            mcp_module,
            "get_access_token",
            lambda: AccessToken(
                token="token",
                client_id="client",
                scopes=["openid"],
                claims={"sub": "auth0|mcp-download"},
            ),
        )

        with pytest.raises(ValueError):
            await main_module.download_publication_files_tool.fn(
                publication_id="pub",
                hrefs=[],
            )

        with pytest.raises(ValueError):
            await main_module.download_publication_files_tool.fn(
                publication_id="pub",
                hrefs=["a", "b", "c"],
            )

    asyncio.run(scenario())
