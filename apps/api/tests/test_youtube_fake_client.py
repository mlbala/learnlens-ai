"""Direct fake YouTube client tests (multi-page + cap)."""

from __future__ import annotations

import pytest
from app.youtube.fake import FakeYoutubeMetadataClient


@pytest.mark.asyncio
async def test_fake_playlist_page_size_and_max_items() -> None:
    client = FakeYoutubeMetadataClient()
    # page_size 3 forces chunking across the first fixture page (5 items).
    meta = await client.get_playlist("PLfixtureCourse01", page_size=3, max_items=6)
    assert len(meta.items) == 6
    assert meta.truncated is True
    assert [i.playlist_position for i in meta.items] == list(range(6))
    assert meta.items[2].availability == "private"
    assert meta.fixture_data is True


@pytest.mark.asyncio
async def test_fake_video_fixture_marked() -> None:
    client = FakeYoutubeMetadataClient()
    video = await client.get_video("vidPublic01")
    assert video.fixture_data is True
    assert video.availability == "public"
