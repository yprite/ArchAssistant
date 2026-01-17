from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Protocol

from analyzer.model import Component, Dependency, Graph


class SmellType(str, Enum):
    ANEMIC_DOMAIN = "anemic_domain"
    GOD_SERVICE = "god_service"
    REPOSITORY_LEAK = "repository_leak"
    CROSS_AGGREGATE_COUPLING = "cross_aggregate_coupling"
    OTHER = "other"


class SmellSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ComponentSmell:
    smell_type: SmellType
    severity: SmellSeverity
    component_id: str
    component_name: str
    layer: str
    description: str
    hints: List[str]
    metrics: Dict[str, float]


@dataclass
class ProjectSmellSummary:
    smells: List[ComponentSmell]
    smells_by_type: Dict[SmellType, int]
    smells_by_layer: Dict[str, int]
    anemic_domain_ratio: float
    god_service_ratio: float
    repository_leak_ratio: float
    cross_aggregate_coupling_ratio: float


class CodeMetricsProvider(Protocol):
    def get_method_count(self, component_id: str) -> int: ...

    def get_field_count(self, component_id: str) -> int: ...

    def get_line_count(self, component_id: str) -> int: ...

    def get_public_method_names(self, component_id: str) -> List[str]: ...


class ComponentMetricsProvider(CodeMetricsProvider):
    def __init__(self, components: Dict[str, Component]) -> None:
        self._components = components

    def get_method_count(self, component_id: str) -> int:
        return int(self._metric(component_id, "method_count", "methods", default=0))

    def get_field_count(self, component_id: str) -> int:
        return int(self._metric(component_id, "field_count", "fields", default=0))

    def get_line_count(self, component_id: str) -> int:
        return int(self._metric(component_id, "line_count", "lines", default=0))

    def get_public_method_names(self, component_id: str) -> List[str]:
        component = self._components.get(component_id)
        if not component:
            return []
        names = component.metrics.get("public_methods")
        if isinstance(names, list):
            return [str(name) for name in names]
        return []

    def _metric(self, component_id: str, *keys: str, default: int) -> int:
        component = self._components.get(component_id)
        if not component:
            return default
        for key in keys:
            value = component.metrics.get(key)
            if isinstance(value, (int, float)):
                return int(value)
        return default


def analyze_project_smells(graph: Graph, metrics: CodeMetricsProvider) -> ProjectSmellSummary:
    smells: List[ComponentSmell] = []
    smells.extend(detect_anemic_domain(graph, metrics))
    smells.extend(detect_god_service(graph, metrics))
    smells.extend(detect_repository_leaks(graph))
    smells.extend(detect_cross_aggregate_coupling(graph, metrics))

    smells_by_type: Dict[SmellType, int] = {}
    smells_by_layer: Dict[str, int] = {}
    for smell in smells:
        smells_by_type[smell.smell_type] = smells_by_type.get(smell.smell_type, 0) + 1
        smells_by_layer[smell.layer] = smells_by_layer.get(smell.layer, 0) + 1

    domain_components = [c for c in graph.components if c.layer == "domain"]
    app_components = [c for c in graph.components if c.layer == "application"]

    anemic_count = sum(1 for s in smells if s.smell_type == SmellType.ANEMIC_DOMAIN)
    god_service_count = sum(1 for s in smells if s.smell_type == SmellType.GOD_SERVICE)
    repo_leak_count = sum(1 for s in smells if s.smell_type == SmellType.REPOSITORY_LEAK)
    cross_agg_count = sum(
        1 for s in smells if s.smell_type == SmellType.CROSS_AGGREGATE_COUPLING
    )

    return ProjectSmellSummary(
        smells=smells,
        smells_by_type=smells_by_type,
        smells_by_layer=smells_by_layer,
        anemic_domain_ratio=anemic_count / max(1, len(domain_components)),
        god_service_ratio=god_service_count / max(1, len(app_components)),
        repository_leak_ratio=repo_leak_count / max(1, len(graph.components)),
        cross_aggregate_coupling_ratio=cross_agg_count / max(1, len(app_components)),
    )


def detect_anemic_domain(graph: Graph, metrics: CodeMetricsProvider) -> List[ComponentSmell]:
    smells: List[ComponentSmell] = []
    components = {c.id: c for c in graph.components}
    for comp in graph.components:
        if comp.layer != "domain":
            continue
        m_count = metrics.get_method_count(comp.id)
        f_count = metrics.get_field_count(comp.id)
        l_count = metrics.get_line_count(comp.id)
        method_names = [name.lower() for name in metrics.get_public_method_names(comp.id)]
        is_accessor_only = bool(method_names) and all(
            name.startswith(("get", "set", "is", "to", "with")) or name in ("__init__", "__str__")
            for name in method_names
        )

        conditions_true = 0
        if m_count <= 2 and f_count >= 3:
            conditions_true += 1
        if is_accessor_only:
            conditions_true += 1
        if l_count >= 50 and m_count <= 3:
            conditions_true += 1

        if conditions_true >= 2:
            smells.append(
                ComponentSmell(
                    smell_type=SmellType.ANEMIC_DOMAIN,
                    severity=SmellSeverity.WARNING,
                    component_id=comp.id,
                    component_name=comp.name,
                    layer=comp.layer,
                    description=(
                        f"Domain entity '{comp.name}' has {m_count} methods and {f_count} fields. "
                        "Most methods look like accessors. This is likely an Anemic Domain Model."
                    ),
                    hints=[
                        "Move business rules/behaviors from application services into this entity.",
                        "Introduce intention-revealing methods that enforce invariants.",
                    ],
                    metrics={
                        "method_count": float(m_count),
                        "field_count": float(f_count),
                        "line_count": float(l_count),
                        "conditions_true": float(conditions_true),
                    },
                )
            )

    return smells


def detect_god_service(graph: Graph, metrics: CodeMetricsProvider) -> List[ComponentSmell]:
    smells: List[ComponentSmell] = []
    outgoing = _build_adjacency(graph.dependencies)
    components = {c.id: c for c in graph.components}
    for comp in graph.components:
        if comp.layer != "application":
            continue
        m_count = metrics.get_method_count(comp.id)
        l_count = metrics.get_line_count(comp.id)

        deps = _outgoing_components(outgoing, components, comp.id)
        dep_ids = {d.id for d in deps}
        domain_deps = {d.name for d in deps if d.layer == "domain"}

        conditions_true = 0
        if m_count >= 10 and l_count >= 200:
            conditions_true += 1
        if len(dep_ids) >= 5:
            conditions_true += 1
        if len(domain_deps) >= 3:
            conditions_true += 1

        if conditions_true >= 2:
            smells.append(
                ComponentSmell(
                    smell_type=SmellType.GOD_SERVICE,
                    severity=SmellSeverity.WARNING,
                    component_id=comp.id,
                    component_name=comp.name,
                    layer=comp.layer,
                    description=(
                        f"Application service '{comp.name}' is large and highly coupled "
                        f"(methods={m_count}, lines={l_count}, deps={len(dep_ids)}, "
                        f"domain_deps={len(domain_deps)}). "
                        "This looks like a God Service / Transaction Script."
                    ),
                    hints=[
                        "Split use cases into separate application services.",
                        "Move domain rules into aggregates or domain services.",
                        "Reduce direct dependencies by introducing ports or domain events.",
                    ],
                    metrics={
                        "method_count": float(m_count),
                        "line_count": float(l_count),
                        "dependency_count": float(len(dep_ids)),
                        "domain_dependency_count": float(len(domain_deps)),
                        "conditions_true": float(conditions_true),
                    },
                )
            )

    return smells


def detect_repository_leaks(graph: Graph) -> List[ComponentSmell]:
    smells: List[ComponentSmell] = []
    repo_patterns = (
        "javax.persistence",
        "jakarta.persistence",
        "org.springframework.data.jpa",
        "entitymanager",
        "jparepository",
        "hibernate",
    )
    for comp in graph.components:
        imports_lower = [imp.lower() for imp in comp.imports]
        annotations_lower = [ann.lower() for ann in comp.annotations]
        has_repo_import = any(
            any(pattern in value for pattern in repo_patterns)
            for value in imports_lower + annotations_lower
        )

        if comp.layer == "domain" and has_repo_import:
            smells.append(
                ComponentSmell(
                    smell_type=SmellType.REPOSITORY_LEAK,
                    severity=SmellSeverity.WARNING,
                    component_id=comp.id,
                    component_name=comp.name,
                    layer=comp.layer,
                    description=(
                        f"Domain component '{comp.name}' imports persistence/ORM APIs. "
                        "Domain layer should not depend on repository/ORM details."
                    ),
                    hints=[
                        "Move persistence annotations and ORM-specific logic to outbound adapters.",
                        "Keep domain entities as pure as possible.",
                    ],
                    metrics={"repo_imports": 1.0},
                )
            )

        if comp.layer in ("application", "inbound_adapter") and has_repo_import:
            smells.append(
                ComponentSmell(
                    smell_type=SmellType.REPOSITORY_LEAK,
                    severity=SmellSeverity.INFO,
                    component_id=comp.id,
                    component_name=comp.name,
                    layer=comp.layer,
                    description=(
                        f"Component '{comp.name}' uses repository/ORM-specific APIs directly. "
                        "Consider wrapping them behind ports or repository interfaces."
                    ),
                    hints=[
                        "Introduce an outbound port or repository interface in the domain/application layer.",
                        "Let outbound adapters handle ORM-specific code.",
                    ],
                    metrics={"repo_imports": 1.0},
                )
            )

    return smells


def detect_cross_aggregate_coupling(
    graph: Graph, metrics: CodeMetricsProvider
) -> List[ComponentSmell]:
    smells: List[ComponentSmell] = []
    outgoing = _build_adjacency(graph.dependencies)
    components = {c.id: c for c in graph.components}
    for comp in graph.components:
        if comp.layer not in ("application", "domain"):
            continue
        deps = _outgoing_components(outgoing, components, comp.id)
        domain_deps = [d for d in deps if d.layer == "domain"]
        if not domain_deps:
            continue
        groups = {guess_aggregate_group(d) for d in domain_deps}
        if len(groups) >= 2:
            m_count = metrics.get_method_count(comp.id)
            l_count = metrics.get_line_count(comp.id)
            smells.append(
                ComponentSmell(
                    smell_type=SmellType.CROSS_AGGREGATE_COUPLING,
                    severity=SmellSeverity.WARNING,
                    component_id=comp.id,
                    component_name=comp.name,
                    layer=comp.layer,
                    description=(
                        f"Component '{comp.name}' touches domain entities from multiple aggregate groups: "
                        f"{', '.join(sorted(groups))}. This may violate aggregate boundaries."
                    ),
                    hints=[
                        "Consider splitting responsibilities by aggregate.",
                        "Introduce domain events or application services per aggregate to decouple them.",
                    ],
                    metrics={
                        "aggregate_group_count": float(len(groups)),
                        "domain_dependency_count": float(len(domain_deps)),
                        "method_count": float(m_count),
                        "line_count": float(l_count),
                    },
                )
            )

    return smells


def guess_aggregate_group(component: Component) -> str:
    pkg = component.package or ""
    parts = pkg.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])
    if len(parts) >= 2:
        return ".".join(parts[:2])
    return pkg or component.name


def _build_adjacency(dependencies: List[Dependency]) -> Dict[str, List[Dependency]]:
    outgoing: Dict[str, List[Dependency]] = {}
    for dep in dependencies:
        outgoing.setdefault(dep.source_id, []).append(dep)
    return outgoing


def _outgoing_components(
    outgoing: Dict[str, List[Dependency]],
    components: Dict[str, Component],
    component_id: str,
) -> List[Component]:
    result: List[Component] = []
    for dep in outgoing.get(component_id, []):
        target = components.get(dep.target_id)
        if target:
            result.append(target)
    return result
