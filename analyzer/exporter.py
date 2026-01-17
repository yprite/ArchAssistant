from __future__ import annotations

import json
from pathlib import Path

from analyzer.model import Graph


def export_graph(graph: Graph, output_path: Path) -> None:
    payload = {
        "components": [
            {
                "id": component.id,
                "name": component.name,
                "path": component.path,
                "package": component.package,
                "layer": component.layer,
                "annotations": component.annotations,
                "imports": component.imports,
                "metrics": component.metrics,
            }
            for component in graph.components
        ],
        "dependencies": [
            {
                "source_id": dep.source_id,
                "target_id": dep.target_id,
                "kind": dep.kind,
            }
            for dep in graph.dependencies
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
