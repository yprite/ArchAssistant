from __future__ import annotations

import json
from pathlib import Path

from analyzer.model import Component, Dependency, Graph


def load_graph(path: Path) -> Graph:
    data = json.loads(path.read_text(encoding="utf-8"))
    components = [
        Component(
            id=item["id"],
            name=item["name"],
            path=item.get("path", ""),
            package=item.get("package", ""),
            layer=item.get("layer", "unknown"),
            annotations=item.get("annotations", []),
            imports=item.get("imports", []),
            metrics=item.get("metrics", {}),
        )
        for item in data.get("components", [])
    ]
    dependencies = [
        Dependency(
            source_id=item["source_id"],
            target_id=item["target_id"],
            kind=item.get("kind", "import"),
        )
        for item in data.get("dependencies", [])
    ]
    return Graph(components=components, dependencies=dependencies)
