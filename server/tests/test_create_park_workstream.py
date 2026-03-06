"""Tests for create_workstream, update_workstream, and park_workstream."""

import json
import tempfile
from pathlib import Path

from relay_server.db import ensure_schema, get_connection
from relay_server.workstreams import read_registry


def _setup(tmpdir):
    db_path = Path(tmpdir) / "test.db"
    data_dir = Path(tmpdir) / "data"
    data_dir.mkdir()
    ensure_schema(db_path)
    (data_dir / "workstreams.json").write_text('{"version": 1, "workstreams": {}}')
    conn = get_connection(db_path)
    return db_path, data_dir, conn


def test_create_workstream():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import create_workstream
            result = create_workstream(
                data_dir=data_dir,
                name="my-project",
                description="A cool project",
                project_dir="/home/test/my-project",
            )
            assert result["status"] == "created"

            reg = read_registry(data_dir)
            assert "my-project" in reg["workstreams"]
            assert reg["workstreams"]["my-project"]["status"] == "active"

            state = (data_dir / "workstreams" / "my-project" / "state.md").read_text()
            assert "my-project" in state
            assert "A cool project" in state
        finally:
            conn.close()


def test_create_duplicate_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import create_workstream
            create_workstream(data_dir=data_dir, name="ws1", description="First")
            result = create_workstream(data_dir=data_dir, name="ws1", description="Dupe")
            assert result["status"] == "error"
        finally:
            conn.close()


def test_create_workstream_with_color():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import create_workstream
            result = create_workstream(
                data_dir=data_dir,
                name="colorful",
                description="Has a color",
                color="#0d1a2d",
            )
            assert result["status"] == "created"
            reg = read_registry(data_dir)
            assert reg["workstreams"]["colorful"]["color"] == "#0d1a2d"
        finally:
            conn.close()


def test_update_workstream():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import create_workstream, update_workstream
            create_workstream(data_dir=data_dir, name="ws1", description="Original")

            result = update_workstream(
                data_dir=data_dir, name="ws1", description="Updated", color="#1a0d2d"
            )
            assert result["status"] == "updated"
            assert "description" in result["fields"]
            assert "color" in result["fields"]

            reg = read_registry(data_dir)
            assert reg["workstreams"]["ws1"]["description"] == "Updated"
            assert reg["workstreams"]["ws1"]["color"] == "#1a0d2d"
        finally:
            conn.close()


def test_update_workstream_remove_color():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import create_workstream, update_workstream
            create_workstream(data_dir=data_dir, name="ws1", description="Test", color="#aabbcc")

            result = update_workstream(data_dir=data_dir, name="ws1", color="")
            assert result["status"] == "updated"

            reg = read_registry(data_dir)
            assert "color" not in reg["workstreams"]["ws1"]
        finally:
            conn.close()


def test_update_nonexistent_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import update_workstream
            result = update_workstream(data_dir=data_dir, name="nope", color="#aaa")
            assert result["status"] == "error"
        finally:
            conn.close()


def test_park_workstream():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path, data_dir, conn = _setup(tmpdir)
        from relay_server.workstreams import create_workstream, park_workstream
        create_workstream(data_dir=data_dir, name="ws1", description="Test")
        conn.execute(
            """INSERT INTO sessions (session_id, project_dir, first_timestamp, last_timestamp, message_count)
               VALUES ('aabbccdd-1122-3344-5566-778899aabbcc', '/test', '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z', 10)"""
        )
        conn.commit()
        try:
            result = park_workstream(
                data_dir=data_dir,
                conn=conn,
                name="ws1",
                state_content="# Parked State",
                session_id="aabbccdd-1122-3344-5566-778899aabbcc",
                hint_summary=["Did stuff"],
            )
            assert result["status"] == "parked"

            reg = read_registry(data_dir)
            assert reg["workstreams"]["ws1"]["status"] == "parked"

            state = (data_dir / "workstreams" / "ws1" / "state.md").read_text()
            assert "Parked State" in state
        finally:
            conn.close()


def test_park_nonexistent_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        _, data_dir, conn = _setup(tmpdir)
        try:
            from relay_server.workstreams import park_workstream
            result = park_workstream(
                data_dir=data_dir, conn=conn, name="nope", state_content="x"
            )
            assert result["status"] == "error"
        finally:
            conn.close()
