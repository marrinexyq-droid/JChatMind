#!/usr/bin/env python3
"""Reject forbidden secret values from tracked text files without printing them."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


FORBIDDEN = (
    re.compile(r"\$\{(?:DB_PASSWORD|MAIL_PASSWORD|DEEPSEEK_API_KEY|ZHIPUAI_API_KEY):[^}]+}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError("git ls-files failed")
    return [Path(os.fsdecode(path)) for path in result.stdout.split(b"\0") if path]


def scan_paths(paths: Iterable[Path], root: Path) -> list[str]:
    violations: list[str] = []
    for relative_path in paths:
        try:
            content = (root / relative_path).read_bytes()
        except OSError:
            continue
        if b"\0" in content:
            continue

        text = content.decode("utf-8", errors="replace")
        violations.extend(scan_text(relative_path, text))
    return violations


def scan_text(relative_path: Path, text: str) -> list[str]:
    violations: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if any(pattern.search(line) for pattern in FORBIDDEN):
            violations.append(f"{relative_path.as_posix()}:{line_number}")
    return violations


def main() -> int:
    try:
        violations = scan_paths(tracked_paths(), Path.cwd())
    except RuntimeError:
        return 2

    for violation in violations:
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
