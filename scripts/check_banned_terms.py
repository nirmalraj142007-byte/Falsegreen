"""Fails if the repo ships a model-assigned score under any of the banned names."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BANNED_TERMS = ("severity", "priority_score", "impact_score", "criticality")
EXCLUDED_DIRS = {".git", "tests/fixtures"}
THIS_SCRIPT = Path(__file__).resolve()

PATTERN = re.compile("|".join(re.escape(term) for term in BANNED_TERMS), re.IGNORECASE)


def _is_excluded(path: Path, repo_root: Path) -> bool:
    if path.resolve() == THIS_SCRIPT:
        return True
    relative = path.relative_to(repo_root).as_posix()
    return any(
        relative == excluded or relative.startswith(f"{excluded}/")
        for excluded in EXCLUDED_DIRS
    )


def _repo_files(repo_root: Path) -> list[Path]:
    """Git-tracked (and untracked-but-not-ignored) files only.

    Scanning the whole filesystem tree would also walk .venv and other
    vendored/build output that is never part of the repo a judge reads;
    "the repo" means what git considers the repo.
    """
    try:
        output = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=repo_root, capture_output=True, text=True, timeout=10, check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired):
        return [p for p in repo_root.rglob("*") if p.is_file() and ".venv" not in p.parts]
    return [repo_root / line for line in output.splitlines() if line]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    hits: list[str] = []

    for path in _repo_files(repo_root):
        if not path.is_file() or _is_excluded(path, repo_root):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if PATTERN.search(line):
                hits.append(f"{path.relative_to(repo_root)}:{lineno}: {line.strip()}")

    if hits:
        print("Banned terms found:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        return 1

    print("No banned terms found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
