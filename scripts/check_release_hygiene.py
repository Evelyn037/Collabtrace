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
}
SECRET_PATTERNS = (
    ("GitHub credential", re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?im)^[ \t]*(SMTP_PASSWORD|JWT_SECRET|VERIFICATION_CODE_SECRET|GITHUB_TOKEN)"
    r"[ \t]*=[ \t]*([^\r\n]*)$"
)
PLACEHOLDER_PREFIXES = ("<", "${", "$", "your", "change", "replace", "example", "test", "dummy")


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
    if name in {".env", ".env.local", ".ds_store", "thumbs.db"}:
        return "environment or operating-system file"
    if name.endswith((".db", ".sqlite", ".sqlite3", ".pyc", ".log", ".tsbuildinfo")):
        return "generated or sensitive file type"
    if parts & FORBIDDEN_PARTS:
        return "generated/dependency directory"
    if "data" in parts and "backups" in parts:
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
        assignment_config = path.name.startswith(".env") or path.suffix.lower() in {
            ".cfg", ".conf", ".ini", ".toml", ".yaml", ".yml",
        }
        if assignment_config:
            for match in SENSITIVE_ASSIGNMENT.finditer(content):
                value = match.group(2).strip().strip('"\'')
                if value and not value.lower().startswith(PLACEHOLDER_PREFIXES):
                    failures.append((relative, "non-placeholder secret assignment", match.group(1)))

    if failures:
        for path, category, detail in sorted(set(failures)):
            print(f"FAIL: path={path} category={category} detail={detail}")
        print(f"Release hygiene failed with {len(set(failures))} finding(s).")
        return 1
    print(f"PASS: checked {len(files)} Git tracked file(s); no release hygiene findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
