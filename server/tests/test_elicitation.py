"""Test elicitation schemas and helper logic."""
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from relay_server.elicitation import (
    WorkstreamPickerSchema,
    WorkstreamCreateSchema,
    build_picker_enum,
    parse_picker_choice,
    elicit_or_fallback,
)


def test_picker_schema_accepts_valid_workstream():
    schema = WorkstreamPickerSchema(workstream="relay")
    assert schema.workstream == "relay"


def test_picker_schema_accepts_create_new():
    schema = WorkstreamPickerSchema(workstream="+ Create new...")
    assert schema.workstream == "+ Create new..."


def test_create_schema_accepts_minimal():
    schema = WorkstreamCreateSchema(name="my-ws", description="A test workstream")
    assert schema.name == "my-ws"
    assert schema.description == "A test workstream"
    assert schema.project_dir is None
    assert schema.git_strategy is None
    assert schema.color is None


def test_create_schema_accepts_full():
    schema = WorkstreamCreateSchema(
        name="my-ws",
        description="A test workstream",
        project_dir="/home/user/project",
        git_strategy="branch",
        color="#0d1a2d",
    )
    assert schema.git_strategy == "branch"
    assert schema.color == "#0d1a2d"


def test_build_picker_enum():
    workstreams = {"relay": {"status": "active"}, "squadkeeper": {"status": "parked"}}
    enum = build_picker_enum(workstreams)
    assert "relay (active)" in enum
    assert "squadkeeper (parked)" in enum
    assert "+ Create new..." in enum


def test_build_picker_enum_empty():
    enum = build_picker_enum({})
    assert enum == ["+ Create new..."]


def test_parse_picker_choice_workstream():
    assert parse_picker_choice("relay (active)") == "relay"
    assert parse_picker_choice("my-project (parked)") == "my-project"


def test_parse_picker_choice_create_new():
    assert parse_picker_choice("+ Create new...") is None


def test_parse_picker_choice_no_parens():
    assert parse_picker_choice("bare-name") == "bare-name"


@pytest.mark.asyncio
async def test_elicit_or_fallback_returns_none_on_error():
    """If elicitation raises, fallback returns None."""
    mock_ctx = MagicMock()
    mock_ctx.elicit = AsyncMock(side_effect=Exception("Not supported"))
    result = await elicit_or_fallback(mock_ctx, "Pick one", WorkstreamPickerSchema)
    assert result is None


@pytest.mark.asyncio
async def test_elicit_or_fallback_returns_data_on_accept():
    """If user accepts, return the validated data."""
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.data = WorkstreamPickerSchema(workstream="relay (active)")
    mock_ctx = MagicMock()
    mock_ctx.elicit = AsyncMock(return_value=mock_result)
    result = await elicit_or_fallback(mock_ctx, "Pick one", WorkstreamPickerSchema)
    assert result is not None
    assert result.workstream == "relay (active)"


@pytest.mark.asyncio
async def test_elicit_or_fallback_returns_none_on_decline():
    """If user declines, return None."""
    mock_result = MagicMock()
    mock_result.action = "decline"
    mock_ctx = MagicMock()
    mock_ctx.elicit = AsyncMock(return_value=mock_result)
    result = await elicit_or_fallback(mock_ctx, "Pick one", WorkstreamPickerSchema)
    assert result is None
