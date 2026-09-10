"""Conservative, dependency-free checks for files tracked by Git."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PARTS = {
    ".venv",
    ".deps",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "coverage",
    "test-results",
    "artifacts",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}
SECRET_PATTERNS = (
    (
        "GitHub credential",
        re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    ),
    ("Bearer credential", re.compile(r"(?i)Bearer[ \t]+[A-Za-z0-9._~-]{24,}")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?im)^[ \t]*(GITHUB_TOKEN|GH_TOKEN|JWT_SECRET|SECRET_KEY|VERIFICATION_SECRET|"
    r"VERIFICATION_CODE_SECRET|SMTP_PASSWORD|SMTP_AUTH_CODE|EMAIL_PASSWORD)"
    r"[ \t]*=[ \t]*([^\r\n]*)$"
)
PLACEHOLDER_PREFIXES = ("<", "${", "$", "your", "change", "replace", "example", "test", "dummy")
LOCAL_PATH_PATTERNS = (
    ("Windows user path", re.compile(r"(?i)[A-Z]:\\(?:Users|Documents and Settings)\\[^\\\s]+\\")),
    ("POSIX user path", re.compile(r"/(?:Users|home)/[^/\s]+/")),
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False
    )
    if result.returncode != 0:
        print("FAIL: unable to read Git tracked files")
        sys.exit(2)
    return [item.decode("utf-8", errors="surrogateescape") for item in result.stdout.split(b"\0") if item]


def forbidden_reason(path: str) -> str | None:
    normalized = PurePosixPath(path.replace("\\", "/"))
    parts = set(normalized.parts)
    name = normalized.name.lower()
    if (
        (name == ".env" or name.startswith(".env."))
        and name != ".env.example"
    ) or name in {".ds_store", "thumbs.db"}:
        return "environment or operating-system file"
    if name.endswith(
        (
            ".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".pyc",
            ".log", ".tsbuildinfo", ".bak", ".backup",
        )
    ):
        return "generated or sensitive file type"
    if parts & FORBIDDEN_PARTS:
        return "generated/dependency directory"
    if parts & {"backup", "backups"}:
        return "database backup"
    return None


def text_content(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > 2_000_000 or b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def main() -> int:
    files = tracked_files()
    failures: list[tuple[str, str, str]] = []
    if not files:
        print("FAIL: repository has no tracked files or baseline commit")
        print("Action: review the working tree and create the first real commit before release")
        return 1

    for relative in files:
        reason = forbidden_reason(relative)
        if reason:
            failures.append((relative, "forbidden tracked path", reason))
        content = text_content(ROOT / relative)
        if content is None:
            continue
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                failures.append((relative, "potential secret", category))
        path = PurePosixPath(relative.replace("\\", "/"))
        is_test_source = "tests" in path.parts or path.name.endswith((".test.ts", ".test.tsx"))
        assignment_document = path.name.startswith(".env") or path.suffix.lower() in {
            ".cfg", ".conf", ".ini", ".md", ".rst", ".toml", ".yaml", ".yml",
        }
        if not is_test_source:
            for match in SENSITIVE_ASSIGNMENT.finditer(content):
                value = match.group(2).strip().strip('"\'')
                raw_value = match.group(2).strip()
                source_literal = raw_value.startswith(('"', "'"))
                if (
                    (assignment_document or source_literal)
                    and value
                    and not value.lower().startswith(PLACEHOLDER_PREFIXES)
                ):
                    failures.append((relative, "non-placeholder secret assignment", match.group(1)))
        for category, pattern in LOCAL_PATH_PATTERNS:
            if pattern.search(content):
                failures.append((relative, "local absolute path", category))

    if failures:
        for path, category, detail in sorted(set(failures)):
            print(f"FAIL: path={path} category={category} detail={detail}")
        print(f"Release hygiene failed with {len(set(failures))} finding(s).")
        return 1
    print(f"PASS: checked {len(files)} Git tracked file(s); no release hygiene findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
