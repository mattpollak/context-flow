"""Tests for write_session_hint."""

import tempfile
from pathlib import Path

from relay_server.db import ensure_schema, get_connection
from relay_server.workstreams import write_session_hint


def test_write_session_hint():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)
        try:
            result = write_session_hint(
                conn=conn,
                session_id="aabbccdd-1122-3344-5566-778899aabbcc",
                workstream="test-ws",
                summary=["Did thing A", "Fixed thing B"],
                decisions=["Chose approach X"],
            )
            assert result["status"] == "written"
            assert result["session_id"] == "aabbccdd-1122-3344-5566-778899aabbcc"
            assert result["workstream"] == "test-ws"

            row = conn.execute(
                "SELECT * FROM session_hints WHERE session_id = 'aabbccdd-1122-3344-5566-778899aabbcc'"
            ).fetchone()
            assert row is not None
            assert row["workstream"] == "test-ws"
            assert "Did thing A" in row["summary"]
            assert "Chose approach X" in row["decisions"]
        finally:
            conn.close()


def test_write_session_hint_no_decisions():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)
        try:
            result = write_session_hint(
                conn=conn,
                session_id="aabbccdd-1122-3344-5566-778899aabbcc",
                workstream="test-ws",
                summary=["Did something"],
            )
            assert result["status"] == "written"

            row = conn.execute(
                "SELECT * FROM session_hints WHERE session_id = 'aabbccdd-1122-3344-5566-778899aabbcc'"
            ).fetchone()
            assert row["decisions"] is None
        finally:
            conn.close()
