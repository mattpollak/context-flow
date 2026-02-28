"""Tests for db module."""

import sqlite3
import tempfile
from pathlib import Path

from relay_server.db import decode_project_dir, ensure_schema, get_connection


def test_decode_standard_path():
    assert decode_project_dir("-home-matt-src-personal-squadkeeper") == "/home/matt/src/personal/squadkeeper"


def test_decode_non_encoded_path():
    """Paths that don't start with '-' are returned as-is."""
    assert decode_project_dir("some-local-dir") == "some-local-dir"


def test_decode_single_segment():
    assert decode_project_dir("-tmp") == "/tmp"


def test_ensure_schema_creates_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        conn = get_connection(db_path)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "sessions" in tables
            assert "messages" in tables
            assert "message_tags" in tables
            assert "session_tags" in tables
            assert "indexed_files" in tables
            assert "messages_fts" in tables
        finally:
            conn.close()


def test_ensure_schema_idempotent():
    """Running ensure_schema twice should not fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        ensure_schema(db_path)
        ensure_schema(db_path)  # Should not raise


def test_connection_has_wal_and_fk():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = get_connection(db_path)
        try:
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert journal == "wal"
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1
        finally:
            conn.close()
