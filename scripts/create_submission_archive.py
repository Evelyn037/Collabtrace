"""Create a reviewed submission ZIP from the committed Git tree only."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

from check_release_hygiene import ROOT, forbidden_reason


DEFAULT_OUTPUT = ROOT / "submission" / "collabtrace-submission.zip"


def run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, cwd=ROOT, capture_output=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a source-only ZIP from the clean committed HEAD."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    hygiene = run([sys.executable, str(ROOT / "scripts" / "check_release_hygiene.py")])
    sys.stdout.buffer.write(hygiene.stdout)
    if hygiene.returncode != 0:
        print("Archive not created: release hygiene failed.")
        return 1

    if run(["git", "rev-parse", "--verify", "HEAD"]).returncode != 0:
        print("Archive not created: Git HEAD does not exist.")
        return 1

    status = run(["git", "status", "--porcelain", "--untracked-files=all"])
    if status.returncode != 0 or status.stdout:
        print("Archive not created: commit or remove all non-ignored working-tree changes first.")
        return 1

    output = args.output.resolve()
    if output.exists():
        print(f"Archive not created: output already exists: {output}")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)

    archive = run(["git", "archive", "--format=zip", f"--output={output}", "HEAD"])
    if archive.returncode != 0:
        print("Archive not created: git archive failed.")
        return 1

    with zipfile.ZipFile(output) as bundle:
        names = [entry.filename.rstrip("/") for entry in bundle.infolist() if not entry.is_dir()]
    findings = [(name, forbidden_reason(name)) for name in names if forbidden_reason(name)]
    if findings:
        output.unlink(missing_ok=True)
        for name, reason in findings:
            print(f"FAIL: archive path={name} reason={reason}")
        print("Archive removed because forbidden content was found.")
        return 1

    print(f"PASS: created {output} from {len(names)} committed source file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
