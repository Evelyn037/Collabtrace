import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from check_release_hygiene import forbidden_reason  # noqa: E402


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "frontend/.env.production",
        "backend/data/collabtrace.sqlite3",
        "backend/data/collabtrace.db-wal",
        "backend/backups/collabtrace-copy",
        "frontend/node_modules/package/index.js",
        "frontend/dist/index.html",
        "backend/.venv/Scripts/python.exe",
        "backend/.pytest_cache/state",
        "notes/credentials.backup",
    ],
)
def test_release_hygiene_rejects_local_or_sensitive_paths(path):
    assert forbidden_reason(path) is not None


def test_release_hygiene_allows_committed_environment_examples():
    assert forbidden_reason("collabtrace-backend/.env.example") is None
    assert forbidden_reason("collabtrace-frontend/.env.example") is None
