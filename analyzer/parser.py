from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


PACKAGE_RE = re.compile(r"^\s*package\s+([\w\.]+)\s*;")
IMPORT_RE = re.compile(r"^\s*import\s+([\w\.\*]+)\s*;")
ANNOTATION_RE = re.compile(r"^\s*@([A-Za-z_][A-Za-z0-9_]*)")
CLASS_RE = re.compile(r"\b(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)")
EXTENDS_RE = re.compile(r"\bextends\s+([A-Za-z0-9_\.]+)")
IMPLEMENTS_RE = re.compile(r"\bimplements\s+([^\{]+)")


@dataclass
class ParsedClass:
    name: str
    package: str
    annotations: List[str]
    imports: List[str]
    extends: List[str]
    implements: List[str]
    kind: str


def parse_java_file(path: Path) -> ParsedClass | None:
    package = ""
    imports: List[str] = []
    annotations: List[str] = []
    class_name = ""
    class_kind = "class"
    extends: List[str] = []
    implements: List[str] = []

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    for line in text.splitlines():
        if not package:
            match = PACKAGE_RE.match(line)
            if match:
                package = match.group(1)
                continue

        match = IMPORT_RE.match(line)
        if match:
            imports.append(match.group(1))
            continue

        match = ANNOTATION_RE.match(line)
        if match and not class_name:
            annotations.append(match.group(1))
            continue

        if not class_name:
            match = CLASS_RE.search(line)
            if match:
                class_name = match.group(2)
                class_kind = match.group(1)
                extends_match = EXTENDS_RE.search(line)
                if extends_match:
                    extends.append(extends_match.group(1))
                implements_match = IMPLEMENTS_RE.search(line)
                if implements_match:
                    for item in implements_match.group(1).split(","):
                        item = item.strip()
                        if item:
                            implements.append(item)
                break

    if not class_name:
        return None

    return ParsedClass(
        name=class_name,
        package=package,
        annotations=annotations,
        imports=imports,
        extends=extends,
        implements=implements,
        kind=class_kind,
    )
