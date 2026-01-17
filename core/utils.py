from __future__ import annotations

from pathlib import Path
from typing import Iterable


def normalize_annotation(name: str) -> str:
    return name.strip().lstrip("@").strip()


def safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def unique(seq: Iterable[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
