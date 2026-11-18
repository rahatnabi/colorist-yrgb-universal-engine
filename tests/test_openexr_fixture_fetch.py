import hashlib

import pytest

from scripts.fetch_openexr_fixture import FIXTURES, fetch_fixture, git_blob_sha1


def test_git_blob_sha1_uses_git_object_header():
    payload = b"hello"
    expected = hashlib.sha1(b"blob 5\\0hello").hexdigest()
    assert git_blob_sha1(payload) == expected


def test_fetch_fixture_rejects_unknown_name(tmp_path):
    with pytest.raises(ValueError, match="Unknown fixture"):
        fetch_fixture("not-a-fixture", tmp_path / "out.exr")


def test_fixture_allowlist_is_immutable_and_bounded():
    assert set(FIXTURES) == {"line-order-increasing", "line-order-decreasing"}
    for spec in FIXTURES.values():
        assert len(spec["git_blob_sha1"]) == 40
        assert spec["size"] == 144543
        assert "49a84f33e675ad4457c8487293eee35622a0c9fd" in spec["url"]


def test_fetch_fixture_verifies_before_writing(tmp_path, monkeypatch):
    payload = b"tiny fixture"
    name = "line-order-increasing"
    spec = dict(FIXTURES[name], size=len(payload), git_blob_sha1=git_blob_sha1(payload))
    monkeypatch.setitem(FIXTURES, name, spec)

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return payload

    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    destination = tmp_path / "nested" / "fixture.exr"
    assert fetch_fixture(name, destination) == destination
    assert destination.read_bytes() == payload


def test_fetch_fixture_does_not_write_checksum_mismatch(tmp_path, monkeypatch):
    payload = b"not the pinned fixture"
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def read(self, _limit):
            return payload
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    destination = tmp_path / "bad.exr"
    with pytest.raises(RuntimeError, match="Unexpected fixture size"):
        fetch_fixture("line-order-increasing", destination)
    assert not destination.exists()
