from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from analyzer.model import Component, Graph
from analysis.bounded_context import BoundedContextAnalysisResult
from analysis.event_readiness import EventReadinessAnalysisResult, UseCaseEventRefactoringSuggestion
from analysis.smells import ComponentSmell, SmellType, ProjectSmellSummary
from architecture.rules import RuleViolation
from core.flow import compute_flow_path
from core.use_case_utils import find_use_case_entries


@dataclass
class UseCaseFlowStep:
    index: int
    component_id: str
    component_name: str
    layer: str
    package: str


@dataclass
class DddEvaluationSummary:
    hexagon_rule_violations: int
    hexagon_rule_ids: List[str]
    smells: List[ComponentSmell]
    hexagon_score: float
    has_anemic_domain: bool
    has_god_service: bool
    has_cross_aggregate: bool


@dataclass
class EventEvaluationSummary:
    readiness_score: int
    readiness_level: str
    sync_coupling_strength: float
    main_suggestions: List[UseCaseEventRefactoringSuggestion]


@dataclass
class BoundedContextSummary:
    entry_bc_id: str
    entry_bc_name: str
    bc_ids_on_path: List[str]
    has_cross_bc_flow: bool
    notes: str


@dataclass
class RefactoringSuggestion:
    id: str
    category: str
    title: str
    description: str
    related_components: List[str]


@dataclass
class UseCaseReport:
    use_case_id: str
    use_case_name: str
    entry_component_id: str
    entry_layer: str
    flow_steps: List[UseCaseFlowStep]
    ddd_summary: DddEvaluationSummary
    event_summary: EventEvaluationSummary
    bc_summary: BoundedContextSummary
    refactoring_suggestions: List[RefactoringSuggestion]


@dataclass
class UseCaseReportSet:
    reports: Dict[str, UseCaseReport]


def build_use_case_reports(
    graph: Graph,
    rules_index: Dict[str, List[RuleViolation]],
    smells_summary: ProjectSmellSummary,
    event_readiness: EventReadinessAnalysisResult,
    bc_result: BoundedContextAnalysisResult,
) -> UseCaseReportSet:
    component_map = {component.id: component for component in graph.components}
    component_to_bc = _component_to_bc(bc_result)
    reports: Dict[str, UseCaseReport] = {}

    for entry in find_use_case_entries(graph):
        flow = compute_flow_path(graph, entry.id)
        flow_steps = build_flow_steps(flow.nodes)
        ddd_summary = build_ddd_summary(flow_steps, rules_index, smells_summary)
        event_summary = build_event_summary(entry.id, event_readiness)
        bc_summary = build_bc_summary(entry, flow_steps, bc_result, component_to_bc)
        suggestions = build_refactoring_suggestions(
            entry.id, flow_steps, ddd_summary, event_summary, bc_summary
        )
        reports[entry.id] = UseCaseReport(
            use_case_id=entry.id,
            use_case_name=entry.name,
            entry_component_id=entry.id,
            entry_layer=entry.layer,
            flow_steps=flow_steps,
            ddd_summary=ddd_summary,
            event_summary=event_summary,
            bc_summary=bc_summary,
            refactoring_suggestions=suggestions,
        )

    return UseCaseReportSet(reports=reports)


def build_flow_steps(path: List[Component]) -> List[UseCaseFlowStep]:
    steps: List[UseCaseFlowStep] = []
    for idx, comp in enumerate(path):
        steps.append(
            UseCaseFlowStep(
                index=idx,
                component_id=comp.id,
                component_name=comp.name,
                layer=comp.layer,
                package=comp.package or "",
            )
        )
    return steps


def build_ddd_summary(
    flow_steps: List[UseCaseFlowStep],
    rules_index: Dict[str, List[RuleViolation]],
    smells_summary: ProjectSmellSummary,
) -> DddEvaluationSummary:
    rule_violations: List[RuleViolation] = []
    for step in flow_steps:
        rule_violations.extend(rules_index.get(step.component_id, []))
    rule_ids = sorted({violation.rule_id for violation in rule_violations})
    flow_comp_ids = {step.component_id for step in flow_steps}
    flow_smells = [sm for sm in smells_summary.smells if sm.component_id in flow_comp_ids]
    has_anemic = any(sm.smell_type == SmellType.ANEMIC_DOMAIN for sm in flow_smells)
    has_god = any(sm.smell_type == SmellType.GOD_SERVICE for sm in flow_smells)
    has_cross = any(sm.smell_type == SmellType.CROSS_AGGREGATE_COUPLING for sm in flow_smells)
    score = _estimate_hexagon_score(len(rule_violations), len(flow_steps))

    return DddEvaluationSummary(
        hexagon_rule_violations=len(rule_violations),
        hexagon_rule_ids=rule_ids,
        smells=flow_smells,
        hexagon_score=score,
        has_anemic_domain=has_anemic,
        has_god_service=has_god,
        has_cross_aggregate=has_cross,
    )


def build_event_summary(
    use_case_id: str, event_readiness: EventReadinessAnalysisResult
) -> EventEvaluationSummary:
    score = event_readiness.per_use_case_scores.get(use_case_id)
    metrics = event_readiness.per_use_case_metrics.get(use_case_id)
    suggestions = event_readiness.per_use_case_suggestions.get(use_case_id, [])
    if score and metrics:
        return EventEvaluationSummary(
            readiness_score=score.score,
            readiness_level=score.level,
            sync_coupling_strength=metrics.approximate_coupling_score,
            main_suggestions=suggestions,
        )
    return EventEvaluationSummary(
        readiness_score=0,
        readiness_level="low",
        sync_coupling_strength=0.0,
        main_suggestions=[],
    )


def build_bc_summary(
    entry: Component,
    flow_steps: List[UseCaseFlowStep],
    bc_result: BoundedContextAnalysisResult,
    component_to_bc: Dict[str, str],
) -> BoundedContextSummary:
    entry_bc_id = component_to_bc.get(entry.id, "")
    entry_bc_name = (
        bc_result.contexts[entry_bc_id].name if entry_bc_id in bc_result.contexts else "Unknown"
    )
    bc_ids = [
        component_to_bc.get(step.component_id)
        for step in flow_steps
        if component_to_bc.get(step.component_id)
    ]
    unique_bc_ids = sorted(set(bc_ids))
    has_cross = len(unique_bc_ids) > 1
    notes = (
        f"Flow crosses {len(unique_bc_ids)} bounded contexts."
        if has_cross
        else "Flow stays within a single bounded context."
    )
    return BoundedContextSummary(
        entry_bc_id=entry_bc_id,
        entry_bc_name=entry_bc_name,
        bc_ids_on_path=unique_bc_ids,
        has_cross_bc_flow=has_cross,
        notes=notes,
    )


def build_refactoring_suggestions(
    use_case_id: str,
    flow_steps: List[UseCaseFlowStep],
    ddd_summary: DddEvaluationSummary,
    event_summary: EventEvaluationSummary,
    bc_summary: BoundedContextSummary,
) -> List[RefactoringSuggestion]:
    suggestions: List[RefactoringSuggestion] = []
    component_ids = [step.component_id for step in flow_steps]

    if ddd_summary.has_anemic_domain:
        targets = [
            sm.component_id
            for sm in ddd_summary.smells
            if sm.smell_type == SmellType.ANEMIC_DOMAIN
        ]
        suggestions.append(
            RefactoringSuggestion(
                id=f"{use_case_id}_anemic_domain",
                category="ddd",
                title="도메인 모델에 비즈니스 로직 이동",
                description=(
                    "Anemic Domain 모델이 포함되어 있습니다. 애플리케이션 서비스의 "
                    "규칙을 엔티티/애그리게잇으로 이동해 캡슐화하세요."
                ),
                related_components=targets,
            )
        )

    if ddd_summary.has_god_service:
        targets = [
            sm.component_id
            for sm in ddd_summary.smells
            if sm.smell_type == SmellType.GOD_SERVICE
        ]
        suggestions.append(
            RefactoringSuggestion(
                id=f"{use_case_id}_god_service",
                category="smell",
                title="Application Service 분할",
                description=(
                    "God Service/Transaction Script 냄새가 있습니다. 유스케이스별로 "
                    "서비스를 분할하고 도메인 로직을 옮기는 것을 검토하세요."
                ),
                related_components=targets,
            )
        )

    if ddd_summary.has_cross_aggregate:
        targets = [
            sm.component_id
            for sm in ddd_summary.smells
            if sm.smell_type == SmellType.CROSS_AGGREGATE_COUPLING
        ]
        suggestions.append(
            RefactoringSuggestion(
                id=f"{use_case_id}_cross_aggregate",
                category="ddd",
                title="애그리게잇 경계 재검토",
                description=(
                    "여러 aggregate 를 동시에 변경하는 흐름입니다. 도메인 이벤트로 "
                    "분리하거나 경계를 재설계하세요."
                ),
                related_components=targets,
            )
        )

    if event_summary.readiness_level in ("medium", "high"):
        for suggestion in event_summary.main_suggestions:
            suggestions.append(
                RefactoringSuggestion(
                    id=f"{use_case_id}_{suggestion.suggestion_type}",
                    category="event",
                    title=suggestion.title,
                    description=suggestion.description,
                    related_components=suggestion.important_components,
                )
            )

    if bc_summary.has_cross_bc_flow:
        suggestions.append(
            RefactoringSuggestion(
                id=f"{use_case_id}_cross_bc",
                category="bc",
                title="Bounded Context 경계 재검토",
                description=(
                    "유스케이스가 여러 BC를 가로지릅니다. 컨텍스트 맵을 재검토하고 "
                    "BC 간 통합을 이벤트로 느슨하게 연결하는 것을 고려하세요."
                ),
                related_components=component_ids,
            )
        )

    return suggestions


def _component_to_bc(bc_result: BoundedContextAnalysisResult) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for bc in bc_result.contexts.values():
        for component_id in bc.component_ids:
            mapping[component_id] = bc.id
    return mapping


def _estimate_hexagon_score(violation_count: int, flow_len: int) -> float:
    if flow_len <= 1:
        return 1.0
    penalty = min(0.8, violation_count / max(1, flow_len * 2))
    return max(0.0, 1.0 - penalty)
