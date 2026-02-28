"""Tests for server-level validation helpers."""

from relay_server.server import _clamp_limit, _validate_tags, MAX_LIMIT, MAX_TAGS


def test_clamp_limit_normal():
    assert _clamp_limit(10) == 10
    assert _clamp_limit(1) == 1
    assert _clamp_limit(500) == 500


def test_clamp_limit_too_high():
    assert _clamp_limit(999999) == MAX_LIMIT


def test_clamp_limit_too_low():
    assert _clamp_limit(0) == 1
    assert _clamp_limit(-5) == 1


def test_validate_tags_ok():
    assert _validate_tags(["review:ux", "important"]) is None


def test_validate_tags_too_many():
    tags = [f"tag-{i}" for i in range(MAX_TAGS + 1)]
    err = _validate_tags(tags)
    assert err is not None
    assert "Too many" in err


def test_validate_tags_too_long():
    err = _validate_tags(["x" * 300])
    assert err is not None
    assert "too long" in err.lower()
