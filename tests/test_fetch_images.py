"""Regression test for issue #1: an issue with a title but an empty body
crashed fetch_images with TypeError: expected string or bytes-like object."""

import triage


def test_fetch_images_accepts_none_body():
    images, notes = triage.fetch_images(None)
    assert images == []
    assert notes == []


def test_fetch_images_accepts_empty_body():
    images, notes = triage.fetch_images("")
    assert images == []
    assert notes == []


def test_fetch_images_still_finds_markdown_images(monkeypatch):
    from email.message import Message

    class FakeResponse:
        headers = Message()
        headers["Content-Type"] = "image/png"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit):
            return b"\x89PNG fake bytes"
    monkeypatch.setattr(
        triage.urllib.request, "urlopen", lambda req, timeout: FakeResponse()
    )
    images, notes = triage.fetch_images("![shot](https://example.com/a.png)")
    assert len(images) == 1 and images[0]["mime"] == "image/png"
    assert notes == []
