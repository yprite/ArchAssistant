from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set

from analyzer.model import Component, Dependency, Graph
from core.use_case_utils import find_use_case_entries, is_use_case_entry
from analysis.event_readiness import (
    UseCaseEventReadinessScore,
    UseCaseEventRefactoringSuggestion,
    analyze_use_case_event_readiness,
)
from analysis.smells import ComponentSmell
from core.flow import compute_flow_path


@dataclass
class UseCaseStep:
    order: int
    source_id: str
    target_id: str
    source_name: str
    target_name: str
    source_layer: str
    target_layer: str
    dependency_kind: str
    notes: List[str]


@dataclass
class UseCaseMetrics:
    length: int
    unique_components: int
    layers_involved: Set[str]
    has_domain: bool
    has_outbound_port: bool
    has_outbound_adapter: bool
    num_repositories_touched: int
    num_aggregates: int
    rule_violations: int
    rule_violations_by_severity: Dict[str, int]


@dataclass
class UseCaseSmell:
    id: str
    severity: str
    message: str


@dataclass
class UseCaseEventSuggestion:
    name: str
    reason: str
    suggested_producer: str
    suggested_consumers: List[str]


@dataclass
class UseCaseReport:
    entry_component_id: str
    entry_name: str
    entry_layer: str
    flow_steps: List[UseCaseStep]
    metrics: UseCaseMetrics
    smells: List[UseCaseSmell]
    component_smells: List[ComponentSmell]
    event_suggestions: List[UseCaseEventSuggestion]
    event_readiness_score: UseCaseEventReadinessScore | None
    event_refactoring_suggestions: List[UseCaseEventRefactoringSuggestion]
    summary_markdown: str


    


def build_use_case_report(
    graph: Graph,
    entry_component_id: str,
    violations_index: Dict[str, List[object]] | None = None,
    smells_index: Dict[str, List[ComponentSmell]] | None = None,
) -> UseCaseReport:
    components = {component.id: component for component in graph.components}
    entry = components.get(entry_component_id)
    if not entry:
        raise ValueError(f"Unknown component: {entry_component_id}")

    flow = compute_flow_path(graph, entry_component_id)
    steps = _build_steps(graph, flow.nodes)
    metrics = _compute_metrics(flow.nodes, steps, violations_index or {})
    smells = _analyze_smells(entry, flow.nodes, steps, metrics, violations_index or {})
    suggestions = _suggest_events(entry, flow.nodes)
    component_smells = _collect_component_smells(flow.nodes, smells_index or {})
    readiness_metrics, readiness_score, readiness_suggestions = analyze_use_case_event_readiness(
        graph, entry, violations_index or {}
    )
    markdown = render_use_case_report_markdown(
        entry,
        flow.nodes,
        steps,
        metrics,
        smells,
        component_smells,
        suggestions,
        readiness_score,
        readiness_suggestions,
    )
    return UseCaseReport(
        entry_component_id=entry.id,
        entry_name=entry.name,
        entry_layer=entry.layer,
        flow_steps=steps,
        metrics=metrics,
        smells=smells,
        component_smells=component_smells,
        event_suggestions=suggestions,
        event_readiness_score=readiness_score,
        event_refactoring_suggestions=readiness_suggestions,
        summary_markdown=markdown,
    )


def _build_steps(graph: Graph, path: List[Component]) -> List[UseCaseStep]:
    steps: List[UseCaseStep] = []
    dep_map = _build_dependency_map(graph.dependencies)
    for idx in range(len(path) - 1):
        src = path[idx]
        dst = path[idx + 1]
        dep = dep_map.get((src.id, dst.id)) or dep_map.get((dst.id, src.id))
        steps.append(
            UseCaseStep(
                order=idx + 1,
                source_id=src.id,
                target_id=dst.id,
                source_name=src.name,
                target_name=dst.name,
                source_layer=src.layer,
                target_layer=dst.layer,
                dependency_kind=dep.kind if dep else "unknown",
                notes=[],
            )
        )
    return steps


def _collect_component_smells(
    path: List[Component], smells_index: Dict[str, List[ComponentSmell]]
) -> List[ComponentSmell]:
    seen: set[str] = set()
    results: List[ComponentSmell] = []
    for component in path:
        for smell in smells_index.get(component.id, []):
            key = f"{smell.component_id}:{smell.smell_type.value}"
            if key in seen:
                continue
            seen.add(key)
            results.append(smell)
    return results


def _compute_metrics(
    path: List[Component], steps: List[UseCaseStep], violations_index: Dict[str, List[object]]
) -> UseCaseMetrics:
    layers = {component.layer for component in path}
    repos = [
        component
        for component in path
        if component.layer == "outbound_adapter"
        and any(token in component.name.lower() for token in ("repository", "dao"))
    ]
    aggregates = [
        component
        for component in path
        if component.layer == "domain"
        and (
            any(token in component.name.lower() for token in ("aggregate", "root", "entity"))
            or any(token in component.annotations for token in ("Entity", "AggregateRoot"))
        )
    ]
    violation_counts = {"info": 0, "warning": 0, "error": 0}
    for component in path:
        for violation in violations_index.get(component.id, []):
            severity = getattr(violation, "severity", "info")
            violation_counts[severity] = violation_counts.get(severity, 0) + 1

    return UseCaseMetrics(
        length=len(steps),
        unique_components=len({component.id for component in path}),
        layers_involved=layers,
        has_domain="domain" in layers,
        has_outbound_port="outbound_port" in layers,
        has_outbound_adapter="outbound_adapter" in layers,
        num_repositories_touched=len(repos),
        num_aggregates=len({component.name for component in aggregates}),
        rule_violations=sum(violation_counts.values()),
        rule_violations_by_severity=violation_counts,
    )


def _analyze_smells(
    entry: Component,
    path: List[Component],
    steps: List[UseCaseStep],
    metrics: UseCaseMetrics,
    violations_index: Dict[str, List[object]],
) -> List[UseCaseSmell]:
    smells: List[UseCaseSmell] = []
    if not metrics.has_domain:
        smells.append(
            UseCaseSmell(
                id="NoDomainInFlow",
                severity="warning",
                message=(
                    "이 유스케이스는 domain layer 를 거치지 않습니다. "
                    "Transaction Script 성격일 수 있습니다."
                ),
            )
        )
    if metrics.length >= 10:
        smells.append(
            UseCaseSmell(
                id="TooManyLayers",
                severity="info",
                message=(
                    "호출 체인이 길어 복잡도가 높습니다. "
                    "단계 분리 또는 도메인 이벤트 도입을 고려하세요."
                ),
            )
        )
    if metrics.num_aggregates >= 2:
        smells.append(
            UseCaseSmell(
                id="MultiAggregateUpdate",
                severity="warning",
                message=(
                    "여러 Aggregate가 한 유스케이스에서 동시에 변경되는 것으로 보입니다. "
                    "트랜잭션 경계를 검토하세요."
                ),
            )
        )
    if any(
        step.source_layer.endswith("adapter") and step.target_layer == "domain"
        for step in steps
    ):
        smells.append(
            UseCaseSmell(
                id="AdapterTouchesDomainDirectly",
                severity="warning",
                message="Adapter 가 domain 을 직접 다루고 있습니다. Port/UseCase 도입을 고려하세요.",
            )
        )
    if not metrics.has_outbound_adapter and _looks_side_effecty(entry.name):
        smells.append(
            UseCaseSmell(
                id="NoOutboundButSideEffectyName",
                severity="info",
                message=(
                    "유스케이스 이름에 비해 외부 I/O가 보이지 않습니다. "
                    "구현 누락 여부를 점검하세요."
                ),
            )
        )
    return smells


def _suggest_events(entry: Component, path: List[Component]) -> List[UseCaseEventSuggestion]:
    suggestions: List[UseCaseEventSuggestion] = []
    domain_entities = [c for c in path if c.layer == "domain"]
    outbound = [c for c in path if c.layer == "outbound_adapter"]
    if domain_entities and outbound:
        entity = domain_entities[0].name
        event_name = f"{entity}Changed"
        suggestions.append(
            UseCaseEventSuggestion(
                name=event_name,
                reason=(
                    f"Domain '{entity}' 변경 이후 외부 시스템 호출이 보입니다. "
                    f"'{event_name}' 도메인 이벤트 발행을 고려해보세요."
                ),
                suggested_producer=entity,
                suggested_consumers=[item.name for item in outbound[:3]],
            )
        )
    if len(outbound) >= 2:
        suggestions.append(
            UseCaseEventSuggestion(
                name=f"{entry.name}Completed",
                reason=(
                    "여러 외부 시스템 호출이 연쇄적으로 등장합니다. "
                    "Saga/프로세스 매니저 도입을 고려하세요."
                ),
                suggested_producer=entry.name,
                suggested_consumers=[item.name for item in outbound[:5]],
            )
        )
    return suggestions


def render_use_case_report_markdown(
    entry: Component,
    path: List[Component],
    steps: List[UseCaseStep],
    metrics: UseCaseMetrics,
    smells: List[UseCaseSmell],
    component_smells: List[ComponentSmell],
    suggestions: List[UseCaseEventSuggestion],
    readiness: UseCaseEventReadinessScore | None = None,
    refactorings: List[UseCaseEventRefactoringSuggestion] | None = None,
) -> str:
    lines = [f"# Use Case Report: {entry.name}", ""]
    lines.append(f"- Entry: `{entry.name}` ({entry.layer})")
    lines.append("")
    lines.append("## Flow Steps")
    for step in steps:
        lines.append(
            f"- {step.order}. `{step.source_name}` ({step.source_layer}) → "
            f"`{step.target_name}` ({step.target_layer})"
        )
    lines.append("")
    lines.append("## Metrics")
    lines.append(f"- Steps: {metrics.length}")
    lines.append(f"- Unique Components: {metrics.unique_components}")
    lines.append(f"- Layers: {', '.join(sorted(metrics.layers_involved))}")
    lines.append(f"- Has Domain: {'Yes' if metrics.has_domain else 'No'}")
    lines.append(
        "- Has Outbound Port/Adapter: "
        f"{'Yes' if metrics.has_outbound_port else 'No'} / "
        f"{'Yes' if metrics.has_outbound_adapter else 'No'}"
    )
    lines.append(f"- Repositories Touched: {metrics.num_repositories_touched}")
    lines.append(f"- Aggregates (estimated): {metrics.num_aggregates}")
    lines.append(
        f"- Rule Violations: {metrics.rule_violations} "
        f"(errors {metrics.rule_violations_by_severity.get('error', 0)}, "
        f"warnings {metrics.rule_violations_by_severity.get('warning', 0)})"
    )
    lines.append("")
    lines.append("## DDD Smells")
    if not smells:
        lines.append("- None")
    else:
        for smell in smells:
            lines.append(f"- [{smell.severity}] {smell.id}: {smell.message}")
    lines.append("")
    lines.append("## Component Smells")
    if not component_smells:
        lines.append("- None")
    else:
        for smell in component_smells:
            lines.append(
                f"- [{smell.severity.value}] {smell.smell_type.value}: {smell.component_name}"
            )
    lines.append("")
    lines.append("## Event Suggestions")
    if not suggestions:
        lines.append("- None")
    else:
        for suggestion in suggestions:
            lines.append(f"- {suggestion.name}")
            lines.append(f"  - Reason: {suggestion.reason}")
            if suggestion.suggested_consumers:
                lines.append(
                    f"  - Consumers: {', '.join(suggestion.suggested_consumers)}"
                )
    if readiness:
        lines.append("")
        lines.append("## Event-Driven Readiness")
        lines.append(f"- Score: {readiness.score} ({readiness.level})")
        lines.append(f"- Summary: {readiness.summary}")
    if refactorings:
        lines.append("")
        lines.append("## Refactoring Suggestions")
        for suggestion in refactorings:
            lines.append(f"- {suggestion.title}")
            lines.append(f"  - {suggestion.description}")
    return "\n".join(lines)


def _build_dependency_map(dependencies: List[Dependency]) -> Dict[tuple[str, str], Dependency]:
    return {(dep.source_id, dep.target_id): dep for dep in dependencies}


def _looks_side_effecty(name: str) -> bool:
    tokens = ("place", "complete", "create", "update", "submit", "charge", "pay")
    lower = name.lower()
    return any(token in lower for token in tokens)
