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
    re.compile(r"\b(?:AIza[A-Za-z0-9_-]{30,}|gsk_[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b[0-9a-fA-F]{32}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(
        r"""
        \bos\.getenv\(
            \s*(?P<name_quote>["'])
            [A-Z0-9_]*(?:PASSWORD|API_KEY|TOKEN|SECRET)[A-Z0-9_]*
            (?P=name_quote)\s*,\s*
            (?:
                (?P<default_quote>["'])[^"']+(?P=default_quote)
                |
                (?!None\b)[^,\s)]+
            )
            \s*,?\s*\)
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
    re.compile(
        r"""
        \b(?:api[_-]?key|access[_-]?token|secret|password)\b
        \s*[:=]\s*["'][A-Za-z0-9_.-]{12,}["']
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
)


def repository_root(cwd: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RuntimeError("repository root lookup failed")
    return Path(os.fsdecode(result.stdout).strip())


def tracked_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
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
            violations.append(f"{relative_path.as_posix()}:read-error")
            continue
        if b"\0" in content:
            continue

        text = content.decode("utf-8", errors="replace")
        violations.extend(scan_text(relative_path, text))
    return violations


def scan_text(relative_path: Path, text: str) -> list[str]:
    line_numbers = {
        text.count("\n", 0, match.start()) + 1
        for pattern in FORBIDDEN
        for match in pattern.finditer(text)
    }
    return [f"{relative_path.as_posix()}:{line_number}" for line_number in sorted(line_numbers)]


def main() -> int:
    try:
        root = repository_root(Path.cwd())
    except RuntimeError:
        print(".:repository-root-error")
        return 2

    try:
        paths = tracked_paths(root)
    except RuntimeError:
        print(".:tracked-enumeration-error")
        return 2

    violations = scan_paths(paths, root)

    for violation in violations:
        print(violation)
    if any(violation.endswith(":read-error") for violation in violations):
        return 2
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
