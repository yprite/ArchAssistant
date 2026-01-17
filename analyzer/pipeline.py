from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from analyzer.classifier import classify_component
from analyzer.exporter import export_graph
from analyzer.model import Component, Dependency, Graph
from analyzer.parser import ParsedClass, parse_java_file
from analyzer.scanner import find_java_files
from core.utils import safe_relative, unique


def analyze_project(project_root: Path, output_path: Path | None = None) -> Graph:
    java_files = find_java_files(project_root)
    parsed_items: Dict[str, ParsedClass] = {}
    components: List[Component] = []

    for java_path in java_files:
        parsed = parse_java_file(java_path)
        if not parsed:
            continue
        component_id = f"{parsed.package}.{parsed.name}" if parsed.package else parsed.name
        layer = classify_component(
            parsed.package,
            parsed.annotations,
            parsed.imports,
            parsed.name,
            parsed.kind == "interface",
        )
        component = Component(
            id=component_id,
            name=parsed.name,
            path=safe_relative(java_path, project_root),
            package=parsed.package,
            layer=layer,
            annotations=unique(parsed.annotations),
            imports=unique(parsed.imports),
        )
        components.append(component)
        parsed_items[component_id] = parsed

    dependencies: List[Dependency] = []
    id_set = {component.id for component in components}
    name_to_ids: Dict[str, List[str]] = {}
    for component in components:
        name_to_ids.setdefault(component.name, []).append(component.id)

    def resolve_target(name: str, package: str) -> str | None:
        name = name.strip()
        if not name:
            return None
        if "." in name:
            return name if name in id_set else None
        package_id = f"{package}.{name}" if package else name
        if package_id in id_set:
            return package_id
        ids = name_to_ids.get(name, [])
        if len(ids) == 1:
            return ids[0]
        return None

    for component in components:
        parsed = parsed_items.get(component.id)
        if not parsed:
            continue
        for imp in parsed.imports:
            if imp.endswith(".*"):
                continue
            if imp in id_set:
                dependencies.append(
                    Dependency(source_id=component.id, target_id=imp, kind="import")
                )
        for base in parsed.extends:
            target = resolve_target(base, component.package)
            if target:
                dependencies.append(
                    Dependency(source_id=component.id, target_id=target, kind="extends")
                )
        for iface in parsed.implements:
            target = resolve_target(iface, component.package)
            if target:
                dependencies.append(
                    Dependency(source_id=component.id, target_id=target, kind="implements")
                )

    graph = Graph(components=components, dependencies=dependencies)
    if output_path:
        export_graph(graph, output_path)
    return graph
