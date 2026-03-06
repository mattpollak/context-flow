"""Tests for manage_idea."""

import json
import tempfile
from pathlib import Path


def test_add_idea():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        from relay_server.workstreams import manage_idea
        result = manage_idea(data_dir=data_dir, action="add", text="try websockets")
        assert result["status"] == "added"
        assert result["id"] == 1

        ideas = json.loads((data_dir / "ideas.json").read_text())
        assert len(ideas) == 1
        assert ideas[0]["text"] == "try websockets"


def test_add_idea_increments_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        from relay_server.workstreams import manage_idea
        manage_idea(data_dir=data_dir, action="add", text="idea 1")
        result = manage_idea(data_dir=data_dir, action="add", text="idea 2")
        assert result["id"] == 2


def test_remove_idea():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        from relay_server.workstreams import manage_idea
        manage_idea(data_dir=data_dir, action="add", text="idea 1")
        manage_idea(data_dir=data_dir, action="add", text="idea 2")
        result = manage_idea(data_dir=data_dir, action="remove", idea_id=1)
        assert result["status"] == "removed"

        ideas = json.loads((data_dir / "ideas.json").read_text())
        assert len(ideas) == 1
        assert ideas[0]["id"] == 2


def test_remove_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        from relay_server.workstreams import manage_idea
        result = manage_idea(data_dir=data_dir, action="remove", idea_id=99)
        assert result["status"] == "error"


def test_list_ideas():
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        from relay_server.workstreams import manage_idea
        manage_idea(data_dir=data_dir, action="add", text="idea 1")
        manage_idea(data_dir=data_dir, action="add", text="idea 2")
        result = manage_idea(data_dir=data_dir, action="list")
        assert len(result["ideas"]) == 2
