from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set

from analyzer.model import Component, Dependency, Graph
from architecture.rules import run_rule_analysis


class BcRelationType(str, Enum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    PARTNERSHIP = "partnership"
    SHARED_KERNEL = "shared_kernel"
    CUSTOMER_SUPPLIER = "customer_supplier"
    GENERIC_SUBDOMAIN = "generic_subdomain"
    UNKNOWN = "unknown"


@dataclass
class BoundedContext:
    id: str
    name: str
    package_prefixes: List[str]
    component_ids: List[str]
    layers_present: Set[str]
    is_pure_hexagon: bool
    hexagon_score: float


@dataclass
class BcRelation:
    source_bc_id: str
    target_bc_id: str
    relation_type: BcRelationType
    dependency_count: int
    bidirectional: bool
    notes: str


@dataclass
class BoundedContextAnalysisResult:
    contexts: Dict[str, BoundedContext]
    relations: List[BcRelation]


def analyze_bounded_contexts(graph: Graph) -> BoundedContextAnalysisResult:
    prefix_to_components: Dict[str, List[Component]] = {}
    for component in graph.components:
        prefix = extract_bc_prefix(component.package or "")
        prefix_to_components.setdefault(prefix, []).append(component)

    contexts: Dict[str, BoundedContext] = {}
    for idx, (prefix, components) in enumerate(sorted(prefix_to_components.items())):
        comp_ids = [component.id for component in components]
        layers_present = {component.layer for component in components}
        score = _compute_hexagon_score(graph, comp_ids)
        context_id = f"bc_{idx}"
        contexts[context_id] = BoundedContext(
            id=context_id,
            name=prefix or "unknown",
            package_prefixes=[prefix],
            component_ids=comp_ids,
            layers_present=layers_present,
            is_pure_hexagon=score >= 0.8,
            hexagon_score=score,
        )

    component_to_bc: Dict[str, str] = {}
    for bc in contexts.values():
        for component_id in bc.component_ids:
            component_to_bc[component_id] = bc.id

    edge_count: Dict[tuple[str, str], int] = {}
    for dep in graph.dependencies:
        src_bc = component_to_bc.get(dep.source_id)
        tgt_bc = component_to_bc.get(dep.target_id)
        if not src_bc or not tgt_bc or src_bc == tgt_bc:
            continue
        key = (src_bc, tgt_bc)
        edge_count[key] = edge_count.get(key, 0) + 1

    relations: List[BcRelation] = []
    seen_pairs: Set[tuple[str, str]] = set()
    for (src, tgt), count in edge_count.items():
        if (src, tgt) in seen_pairs:
            continue
        reverse_count = edge_count.get((tgt, src), 0)
        bidir = reverse_count > 0
        relation_type = infer_relation_type(
            contexts[src], contexts[tgt], count, reverse_count
        )
        notes = f"{contexts[src].name} -> {contexts[tgt].name}: {count} deps"
        if bidir:
            notes += f", reverse: {reverse_count}"
        relations.append(
            BcRelation(
                source_bc_id=src,
                target_bc_id=tgt,
                relation_type=relation_type,
                dependency_count=count,
                bidirectional=bidir,
                notes=notes,
            )
        )
        seen_pairs.add((src, tgt))
        seen_pairs.add((tgt, src))

    return BoundedContextAnalysisResult(contexts=contexts, relations=relations)


def extract_bc_prefix(package: str) -> str:
    parts = package.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return package


def infer_relation_type(
    src_context: BoundedContext,
    tgt_context: BoundedContext,
    forward_count: int,
    backward_count: int,
) -> BcRelationType:
    if forward_count > 0 and backward_count == 0:
        return BcRelationType.DOWNSTREAM
    if forward_count > 0 and backward_count > 0:
        return BcRelationType.PARTNERSHIP
    return BcRelationType.UNKNOWN


def _compute_hexagon_score(graph: Graph, component_ids: List[str]) -> float:
    component_set = set(component_ids)
    components = [c for c in graph.components if c.id in component_set]
    dependencies = [
        dep
        for dep in graph.dependencies
        if dep.source_id in component_set and dep.target_id in component_set
    ]
    sub_graph = Graph(components=components, dependencies=dependencies)
    _, summary = run_rule_analysis(sub_graph)
    return summary.score / 100.0 if summary.total_components else 0.0
