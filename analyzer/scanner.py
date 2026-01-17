from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


DEFAULT_SOURCE_ROOTS = [Path("src/main/java")]


def find_java_files(project_root: Path) -> List[Path]:
    roots = [project_root / root for root in DEFAULT_SOURCE_ROOTS]
    candidates = [root for root in roots if root.exists()]
    if not candidates:
        candidates = [project_root]

    java_files: List[Path] = []
    for root in candidates:
        java_files.extend(root.rglob("*.java"))
    return java_files


def iter_source_roots(project_root: Path) -> Iterable[Path]:
    for root in DEFAULT_SOURCE_ROOTS:
        full = project_root / root
        if full.exists():
            yield full
