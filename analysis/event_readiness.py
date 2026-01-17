from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List

from analyzer.model import Component, Graph
from architecture.rules import RuleViolation
from core.flow import compute_flow_path
from core.use_case_utils import find_use_case_entries


@dataclass
class UseCaseEventReadinessMetrics:
    use_case_id: str
    use_case_name: str
    entry_layer: str
    path_length: int
    num_sync_calls: int
    num_external_systems: int
    num_outbound_ports: int
    num_domain_entities_touched: int
    num_aggregates_touched: int
    num_cross_aggregate_updates: int
    num_bounded_contexts: int
    has_compensation_logic_hint: bool
    sync_chain_depth: int
    rule_violations_on_path: int
    approximate_coupling_score: float


@dataclass
class UseCaseEventReadinessScore:
    use_case_id: str
    score: int
    level: str
    summary: str


@dataclass
class UseCaseEventRefactoringSuggestion:
    use_case_id: str
    suggestion_type: str
    title: str
    description: str
    suggested_event_names: List[str]
    important_components: List[str]


@dataclass
class ProjectEventReadinessSummary:
    total_use_cases: int
    avg_score: float
    high_candidate_count: int
    medium_candidate_count: int
    low_candidate_count: int
    scores_by_use_case: List[UseCaseEventReadinessScore]
    top_candidates: List[UseCaseEventReadinessScore]


@dataclass
class EventReadinessAnalysisResult:
    per_use_case_metrics: Dict[str, UseCaseEventReadinessMetrics]
    per_use_case_scores: Dict[str, UseCaseEventReadinessScore]
    per_use_case_suggestions: Dict[str, List[UseCaseEventRefactoringSuggestion]]
    project_summary: ProjectEventReadinessSummary


def analyze_use_case_event_readiness(
    graph: Graph,
    entry: Component,
    rule_index: Dict[str, List[RuleViolation]] | None = None,
) -> tuple[UseCaseEventReadinessMetrics, UseCaseEventReadinessScore, List[UseCaseEventRefactoringSuggestion]]:
    flow = compute_flow_path(graph, entry.id)
    path = flow.nodes
    path_length = max(0, len(path) - 1)
    num_outbound_ports = sum(1 for c in path if c.layer == "outbound_port")
    num_external_systems = sum(1 for c in path if c.layer == "outbound_adapter")
    num_domain_entities = sum(1 for c in path if c.layer == "domain")
    aggregates = _estimate_aggregates(path)
    num_aggregates_touched = len(aggregates)
    num_cross_aggregate_updates = 1 if num_aggregates_touched > 1 else 0
    num_bounded_contexts = len({_package_prefix(c.package) for c in path if c.package})
    has_compensation = any(
        token in c.name.lower()
        for c in path
        for token in ("cancel", "rollback", "undo", "compensate")
    )
    sync_chain_depth = _sync_chain_depth(path)
    violations_on_path = _count_rule_violations(path, rule_index or {})
    coupling_score = _approximate_coupling(
        path_length,
        num_external_systems,
        num_bounded_contexts,
        num_cross_aggregate_updates,
    )

    metrics = UseCaseEventReadinessMetrics(
        use_case_id=entry.id,
        use_case_name=entry.name,
        entry_layer=entry.layer,
        path_length=path_length,
        num_sync_calls=path_length,
        num_external_systems=num_external_systems,
        num_outbound_ports=num_outbound_ports,
        num_domain_entities_touched=num_domain_entities,
        num_aggregates_touched=num_aggregates_touched,
        num_cross_aggregate_updates=num_cross_aggregate_updates,
        num_bounded_contexts=num_bounded_contexts,
        has_compensation_logic_hint=has_compensation,
        sync_chain_depth=sync_chain_depth,
        rule_violations_on_path=violations_on_path,
        approximate_coupling_score=coupling_score,
    )

    score = score_use_case_event_readiness(metrics)
    suggestions = suggest_event_refactorings_for_use_case(graph, metrics, score, path)
    return metrics, score, suggestions


def score_use_case_event_readiness(metrics: UseCaseEventReadinessMetrics) -> UseCaseEventReadinessScore:
    score = 0
    if metrics.path_length >= 4:
        score += 10
    if metrics.num_external_systems >= 2:
        score += 20
    if metrics.num_outbound_ports >= 2:
        score += 10
    if metrics.num_bounded_contexts >= 2:
        score += 20
    if metrics.num_cross_aggregate_updates >= 1:
        score += 15
    if metrics.has_compensation_logic_hint:
        score += 10
    score += round(metrics.approximate_coupling_score * 25)
    if metrics.rule_violations_on_path == 0:
        score -= 10
    score = max(0, min(100, score))
    level = "low"
    if score >= 70:
        level = "high"
    elif score >= 40:
        level = "medium"
    summary = (
        f"Length={metrics.path_length}, externals={metrics.num_external_systems}, "
        f"aggregates={metrics.num_aggregates_touched}, BCs={metrics.num_bounded_contexts}, "
        f"coupling={metrics.approximate_coupling_score:.2f}"
    )
    return UseCaseEventReadinessScore(
        use_case_id=metrics.use_case_id, score=score, level=level, summary=summary
    )


def suggest_event_refactorings_for_use_case(
    graph: Graph,
    metrics: UseCaseEventReadinessMetrics,
    score: UseCaseEventReadinessScore,
    path: List[Component],
) -> List[UseCaseEventRefactoringSuggestion]:
    suggestions: List[UseCaseEventRefactoringSuggestion] = []
    domain_entities = [c for c in path if c.layer == "domain"]
    outbound = [c for c in path if c.layer == "outbound_adapter"]

    if metrics.num_domain_entities_touched and metrics.num_external_systems >= 1:
        domain_name = domain_entities[0].name if domain_entities else "DomainEntity"
        event_name = f"{domain_name}Changed"
        suggestions.append(
            UseCaseEventRefactoringSuggestion(
                use_case_id=metrics.use_case_id,
                suggestion_type="introduce_domain_event",
                title=f"Introduce domain event for {domain_name}",
                description=(
                    f"도메인 '{domain_name}' 변경 이후 외부 시스템 호출이 있습니다. "
                    f"'{event_name}' 이벤트 발행을 고려하세요."
                ),
                suggested_event_names=[event_name, f"{metrics.use_case_name}Completed"],
                important_components=[c.id for c in domain_entities[:2]]
                + [c.id for c in outbound[:2]],
            )
        )

    if metrics.num_external_systems >= 2 and metrics.num_bounded_contexts >= 2:
        suggestions.append(
            UseCaseEventRefactoringSuggestion(
                use_case_id=metrics.use_case_id,
                suggestion_type="introduce_integration_event",
                title="Introduce integration events across bounded contexts",
                description=(
                    "여러 외부 시스템/BC와 동기 호출이 얽혀 있습니다. "
                    "통합 이벤트로 결합도를 낮출 수 있습니다."
                ),
                suggested_event_names=[f"{metrics.use_case_name}Integrated"],
                important_components=[c.id for c in outbound[:3]],
            )
        )

    if metrics.num_external_systems >= 2 and metrics.num_cross_aggregate_updates >= 1 and (
        metrics.has_compensation_logic_hint or score.score >= 80
    ):
        suggestions.append(
            UseCaseEventRefactoringSuggestion(
                use_case_id=metrics.use_case_id,
                suggestion_type="introduce_saga",
                title="Introduce Saga / Process Manager",
                description=(
                    "여러 외부 시스템과 aggregate가 연쇄적으로 등장합니다. "
                    "Saga/Process Manager 도입을 검토하세요."
                ),
                suggested_event_names=[
                    f"{metrics.use_case_name}Started",
                    f"{metrics.use_case_name}Completed",
                    f"{metrics.use_case_name}Failed",
                ],
                important_components=[c.id for c in outbound[:4]],
            )
        )

    if metrics.path_length >= 8 and metrics.num_external_systems >= 2:
        suggestions.append(
            UseCaseEventRefactoringSuggestion(
                use_case_id=metrics.use_case_id,
                suggestion_type="split_use_case",
                title="Split use case into commands + event handlers",
                description=(
                    "호출 체인이 길고 외부 시스템이 다수입니다. "
                    "커맨드 + 이벤트 핸들러로 분리하는 리팩토링을 제안합니다."
                ),
                suggested_event_names=[f"{metrics.use_case_name}Split"],
                important_components=[c.id for c in path[:4]],
            )
        )

    return suggestions[:3]


def analyze_project_event_readiness(
    graph: Graph, rule_index: Dict[str, List[RuleViolation]] | None = None
) -> EventReadinessAnalysisResult:
    entries = find_use_case_entries(graph)
    metrics_map: Dict[str, UseCaseEventReadinessMetrics] = {}
    scores_map: Dict[str, UseCaseEventReadinessScore] = {}
    suggestions_map: Dict[str, List[UseCaseEventRefactoringSuggestion]] = {}

    for entry in entries:
        metrics, score, suggestions = analyze_use_case_event_readiness(
            graph, entry, rule_index
        )
        metrics_map[entry.id] = metrics
        scores_map[entry.id] = score
        suggestions_map[entry.id] = suggestions

    scores = list(scores_map.values())
    avg_score = mean([score.score for score in scores]) if scores else 0.0
    high = len([score for score in scores if score.level == "high"])
    medium = len([score for score in scores if score.level == "medium"])
    low = len([score for score in scores if score.level == "low"])
    top = sorted(scores, key=lambda s: s.score, reverse=True)[:5]

    summary = ProjectEventReadinessSummary(
        total_use_cases=len(entries),
        avg_score=avg_score,
        high_candidate_count=high,
        medium_candidate_count=medium,
        low_candidate_count=low,
        scores_by_use_case=scores,
        top_candidates=top,
    )
    return EventReadinessAnalysisResult(
        per_use_case_metrics=metrics_map,
        per_use_case_scores=scores_map,
        per_use_case_suggestions=suggestions_map,
        project_summary=summary,
    )


def _estimate_aggregates(path: List[Component]) -> List[str]:
    aggregates = []
    for component in path:
        if component.layer != "domain":
            continue
        name = component.name
        lower = name.lower()
        if "aggregate" in lower or "root" in lower or "entity" in lower:
            aggregates.append(name)
        if any(token in component.annotations for token in ("Entity", "AggregateRoot")):
            aggregates.append(name)
    if not aggregates:
        aggregates = [component.name for component in path if component.layer == "domain"]
    return list(dict.fromkeys(aggregates))


def _sync_chain_depth(path: List[Component]) -> int:
    max_depth = 0
    current = 0
    for component in path:
        if component.layer in ("domain", "outbound_port", "outbound_adapter"):
            current += 1
            max_depth = max(max_depth, current)
        else:
            current = 0
    return max_depth


def _count_rule_violations(path: List[Component], rule_index: Dict[str, List[RuleViolation]]) -> int:
    count = 0
    for component in path:
        count += len(rule_index.get(component.id, []))
    return count


def _approximate_coupling(
    path_length: int,
    num_external_systems: int,
    num_bounded_contexts: int,
    num_cross_aggregate_updates: int,
) -> float:
    score = 0.0
    score += min(path_length / 8.0, 1.0) * 0.3
    score += min(num_external_systems / 3.0, 1.0) * 0.3
    score += min(num_bounded_contexts / 3.0, 1.0) * 0.2
    score += min(num_cross_aggregate_updates / 2.0, 1.0) * 0.2
    return min(1.0, score)


def _package_prefix(package: str) -> str:
    parts = package.split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else package
