from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from analyzer.model import Component, Dependency, Graph


@dataclass(frozen=True)
class FlowResult:
    nodes: List[Component]
    edges: List[Dependency]


def compute_flow_path(graph: Graph, start_id: str, max_depth: int = 12) -> FlowResult:
    components: Dict[str, Component] = {c.id: c for c in graph.components}
    paths = compute_flow_paths(graph, start_id, max_depth=max_depth)
    if not paths:
        return FlowResult(nodes=[], edges=[])
    best_path = max(paths, key=lambda path: _score_path(path, components))
    edge_map = _edge_map(graph.dependencies)
    path_nodes: List[Component] = []
    path_edges: List[Dependency] = []
    for idx, node_id in enumerate(best_path):
        component = components.get(node_id)
        if component:
            path_nodes.append(component)
        if idx + 1 < len(best_path):
            edge = _edge_for(edge_map, node_id, best_path[idx + 1])
            if edge:
                path_edges.append(edge)
    return FlowResult(nodes=path_nodes, edges=path_edges)


def compute_flow_paths(graph: Graph, start_id: str, max_depth: int = 12) -> List[List[str]]:
    components: Dict[str, Component] = {c.id: c for c in graph.components}
    outgoing, incoming = _build_adjacency(graph.dependencies)
    paths: List[List[str]] = []

    def dfs(current_id: str, depth: int, path: List[str], visited: Set[str]) -> None:
        if depth > max_depth:
            paths.append(path.copy())
            return
        current = components.get(current_id)
        if not current:
            return
        path.append(current_id)
        visited.add(current_id)
        neighbors = get_flow_neighbors(current, components, outgoing, incoming)
        if not neighbors:
            paths.append(path.copy())
        else:
            for neighbor in neighbors:
                if neighbor.id not in visited:
                    dfs(neighbor.id, depth + 1, path, visited)
        path.pop()
        visited.remove(current_id)

    dfs(start_id, 0, [], set())
    return paths


def get_flow_neighbors(
    component: Component,
    components: Dict[str, Component],
    outgoing: Dict[str, List[Dependency]],
    incoming: Dict[str, List[Dependency]],
) -> List[Component]:
    result: List[Component] = []

    def by_id(cid: str) -> Component | None:
        return components.get(cid)

    if component.layer == "inbound_adapter":
        for dep in outgoing.get(component.id, []):
            target = by_id(dep.target_id)
            if target and target.layer == "inbound_port":
                result.append(target)

    if component.layer == "application":
        for dep in outgoing.get(component.id, []):
            target = by_id(dep.target_id)
            if target and target.layer in ("domain", "outbound_port"):
                result.append(target)

    if component.layer == "inbound_port":
        for dep in incoming.get(component.id, []):
            source = by_id(dep.source_id)
            if source and source.layer == "application" and dep.kind in ("implements", "import"):
                result.append(source)

    if component.layer == "domain":
        for dep in incoming.get(component.id, []):
            source = by_id(dep.source_id)
            if source and source.layer == "application":
                for out_dep in outgoing.get(source.id, []):
                    target = by_id(out_dep.target_id)
                    if target and target.layer == "outbound_port":
                        result.append(target)

    if component.layer == "outbound_port":
        for dep in incoming.get(component.id, []):
            source = by_id(dep.source_id)
            if source and source.layer == "outbound_adapter" and dep.kind in (
                "implements",
                "import",
            ):
                result.append(source)

    seen: Set[str] = set()
    unique: List[Component] = []
    for node in result:
        if node.id not in seen:
            seen.add(node.id)
            unique.append(node)
    return unique


def _score_path(path: List[str], components: Dict[str, Component]) -> tuple[int, int]:
    layers = [components[node_id].layer for node_id in path if node_id in components]
    has_outbound = any(layer in ("outbound_port", "outbound_adapter") for layer in layers)
    return (1 if has_outbound else 0, len(path))


def _build_adjacency(
    dependencies: List[Dependency],
) -> tuple[Dict[str, List[Dependency]], Dict[str, List[Dependency]]]:
    outgoing: Dict[str, List[Dependency]] = {}
    incoming: Dict[str, List[Dependency]] = {}
    for dep in dependencies:
        outgoing.setdefault(dep.source_id, []).append(dep)
        incoming.setdefault(dep.target_id, []).append(dep)
    return outgoing, incoming


def _edge_map(dependencies: List[Dependency]) -> Dict[tuple[str, str], Dependency]:
    return {(dep.source_id, dep.target_id): dep for dep in dependencies}


def _edge_for(
    edge_map: Dict[tuple[str, str], Dependency], source_id: str, target_id: str
) -> Dependency | None:
    return edge_map.get((source_id, target_id)) or edge_map.get((target_id, source_id))
    has_outbound = any(layer in ("outbound_port", "outbound_adapter") for layer in layers)
    return (1 if has_outbound else 0, len(path))
