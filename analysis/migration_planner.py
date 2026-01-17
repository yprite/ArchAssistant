from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from analyzer.model import Component, Graph
from analysis.bounded_context import BoundedContextAnalysisResult
from analysis.event_readiness import EventReadinessAnalysisResult
from analysis.smells import ComponentSmell, ProjectSmellSummary, SmellType
from analysis.target_architecture import TargetArchitectureSpec, matches_package
from analysis.use_case_report import UseCaseReportSet
from architecture.rules import RuleAnalysisSummary, RuleViolation


class MigrationItemType(str, Enum):
    MOVE_TO_LAYER = "move_to_layer"
    MOVE_TO_BOUNDED_CONTEXT = "move_to_bounded_context"
    SPLIT_SERVICE = "split_service"
    EXTRACT_DOMAIN_LOGIC = "extract_domain_logic"
    INTRODUCE_PORT = "introduce_port"
    INTRODUCE_EVENT = "introduce_event"
    INTRODUCE_SAGA = "introduce_saga"
    FIX_REPOSITORY_LEAK = "fix_repository_leak"
    RESTRUCTURE_USE_CASE = "restructure_use_case"
    OTHER = "other"


class MigrationPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class MigrationItem:
    id: str
    item_type: MigrationItemType
    priority: MigrationPriority
    title: str
    description: str
    rationale: str
    related_components: List[str]
    related_use_cases: List[str]
    related_bc_ids: List[str]
    tags: List[str]


@dataclass
class MigrationPhase:
    id: str
    name: str
    description: str
    items: List[MigrationItem]


@dataclass
class MigrationPlan:
    current_project_name: str
    target_name: str
    phases: List[MigrationPhase]
    all_items: List[MigrationItem]


def build_migration_plan(
    current_graph: Graph,
    target_spec: TargetArchitectureSpec,
    rules_summary: RuleAnalysisSummary,
    rules_index: Dict[str, List[RuleViolation]],
    smells_summary: ProjectSmellSummary,
    event_readiness: EventReadinessAnalysisResult,
    bc_result: BoundedContextAnalysisResult,
    use_case_reports: UseCaseReportSet,
    current_project_name: str = "Current Project",
) -> MigrationPlan:
    items: List[MigrationItem] = []
    items.extend(
        generate_layer_level_migration_items(
            current_graph, target_spec, rules_summary, rules_index, smells_summary
        )
    )
    items.extend(
        generate_use_case_level_migration_items(use_case_reports, event_readiness, target_spec)
    )
    items.extend(generate_bounded_context_level_migration_items(bc_result, target_spec))

    phases = group_migration_items_into_phases(items)
    return MigrationPlan(
        current_project_name=current_project_name,
        target_name=target_spec.name,
        phases=phases,
        all_items=items,
    )


def generate_layer_level_migration_items(
    current_graph: Graph,
    target_spec: TargetArchitectureSpec,
    rules_summary: RuleAnalysisSummary,
    rules_index: Dict[str, List[RuleViolation]],
    smells_summary: ProjectSmellSummary,
) -> List[MigrationItem]:
    items: List[MigrationItem] = []
    components = {component.id: component for component in current_graph.components}

    for component_id, violations in rules_index.items():
        for violation in violations:
            if violation.rule_id not in (
                "DOMAIN_DEPENDS_ON_ADAPTER",
                "APPLICATION_DEPENDS_ON_ADAPTER",
                "ADAPTER_DIRECTLY_DEPENDS_ON_DOMAIN",
            ):
                continue
            source = components.get(violation.source_component_id)
            target = components.get(violation.target_component_id) if violation.target_component_id else None
            title = "도메인/어댑터 의존 제거 및 포트 도입"
            description = (
                f"{source.name if source else 'Component'} → "
                f"{target.name if target else 'Component'} 의존을 포트 기반으로 재구성하세요."
            )
            rationale = (
                f"헥사고날 규칙 위반 {violation.rule_id} + target guideline mismatch"
            )
            items.append(
                MigrationItem(
                    id=f"{violation.rule_id}_{violation.source_component_id}",
                    item_type=MigrationItemType.INTRODUCE_PORT,
                    priority=MigrationPriority.HIGH,
                    title=title,
                    description=description,
                    rationale=rationale,
                    related_components=[
                        cid
                        for cid in [
                            violation.source_component_id,
                            violation.target_component_id,
                        ]
                        if cid
                    ],
                    related_use_cases=[],
                    related_bc_ids=[],
                    tags=[violation.rule_id.lower()],
                )
            )

    for smell in smells_summary.smells:
        if smell.smell_type != SmellType.REPOSITORY_LEAK:
            continue
        items.append(
            MigrationItem(
                id=f"repo_leak_{smell.component_id}",
                item_type=MigrationItemType.FIX_REPOSITORY_LEAK,
                priority=MigrationPriority.MEDIUM,
                title="Repository Leak 정리",
                description=(
                    f"{smell.component_name}에서 ORM/Repository 의존이 감지되었습니다. "
                    "Outbound adapter로 이동하거나 포트로 감싸세요."
                ),
                rationale="Repository leak smell",
                related_components=[smell.component_id],
                related_use_cases=[],
                related_bc_ids=[],
                tags=["repository_leak"],
            )
        )

    return items


def generate_use_case_level_migration_items(
    use_case_reports: UseCaseReportSet,
    event_readiness: EventReadinessAnalysisResult,
    target_spec: TargetArchitectureSpec,
) -> List[MigrationItem]:
    items: List[MigrationItem] = []
    for report in use_case_reports.reports.values():
        event_summary = report.event_summary
        if event_summary.readiness_level == "high":
            for suggestion in event_summary.main_suggestions:
                if "saga" in suggestion.suggestion_type:
                    items.append(
                        MigrationItem(
                            id=f"{report.use_case_id}_saga",
                            item_type=MigrationItemType.INTRODUCE_SAGA,
                            priority=MigrationPriority.HIGH,
                            title=f"유스케이스 '{report.use_case_name}'에 Saga 도입",
                            description=(
                                "여러 외부 시스템과 애그리게잇이 연쇄적으로 등장합니다. "
                                "Saga 또는 Process Manager를 도입하세요."
                            ),
                            rationale="High event readiness + saga suggestion",
                            related_components=suggestion.important_components,
                            related_use_cases=[report.use_case_id],
                            related_bc_ids=[],
                            tags=["saga", "event"],
                        )
                    )
        if report.ddd_summary.has_god_service or report.ddd_summary.has_cross_aggregate:
            items.append(
                MigrationItem(
                    id=f"{report.use_case_id}_split_service",
                    item_type=MigrationItemType.RESTRUCTURE_USE_CASE,
                    priority=MigrationPriority.HIGH,
                    title=f"유스케이스 '{report.use_case_name}' 리팩토링",
                    description=(
                        "God Service 또는 Cross-Aggregate 스멜이 감지되었습니다. "
                        "유스케이스를 분리하고 애그리게잇 경계를 재설계하세요."
                    ),
                    rationale="DDD smell detected in flow",
                    related_components=[step.component_id for step in report.flow_steps],
                    related_use_cases=[report.use_case_id],
                    related_bc_ids=report.bc_summary.bc_ids_on_path,
                    tags=["god_service", "cross_aggregate"],
                )
            )

        blueprint = _match_blueprint(report.use_case_name, target_spec)
        if blueprint and blueprint.expected_events and not event_summary.main_suggestions:
            items.append(
                MigrationItem(
                    id=f"{report.use_case_id}_events",
                    item_type=MigrationItemType.INTRODUCE_EVENT,
                    priority=MigrationPriority.MEDIUM,
                    title=f"유스케이스 '{report.use_case_name}' 이벤트 도입",
                    description=(
                        "Target blueprint에 기대 이벤트가 정의되어 있습니다. "
                        f"예: {', '.join(blueprint.expected_events)}"
                    ),
                    rationale="Target blueprint expected events not present",
                    related_components=[step.component_id for step in report.flow_steps],
                    related_use_cases=[report.use_case_id],
                    related_bc_ids=report.bc_summary.bc_ids_on_path,
                    tags=["event"],
                )
            )

    return items


def generate_bounded_context_level_migration_items(
    bc_result: BoundedContextAnalysisResult,
    target_spec: TargetArchitectureSpec,
) -> List[MigrationItem]:
    items: List[MigrationItem] = []
    for bc in bc_result.contexts.values():
        target_bc = _match_target_bc(bc, target_spec)
        if not target_bc:
            continue
        missing_layers = [layer for layer in target_bc.expected_layers if layer not in bc.layers_present]
        if missing_layers:
            items.append(
                MigrationItem(
                    id=f"{bc.id}_missing_layers",
                    item_type=MigrationItemType.INTRODUCE_PORT,
                    priority=MigrationPriority.MEDIUM,
                    title=f"BC '{bc.name}' 레이어 보완",
                    description=f"Target BC에서 필요한 레이어가 누락됨: {', '.join(missing_layers)}",
                    rationale="Target BC expected layers missing",
                    related_components=bc.component_ids,
                    related_use_cases=[],
                    related_bc_ids=[bc.id],
                    tags=["bounded_context"],
                )
            )

    return items


def group_migration_items_into_phases(items: List[MigrationItem]) -> List[MigrationPhase]:
    phase_map: Dict[str, MigrationPhase] = {
        "phase_1": MigrationPhase(
            id="phase_1",
            name="Phase 1 - Rules & Infra Cleanup",
            description="Fix rule violations, repo leaks, and layer issues.",
            items=[],
        ),
        "phase_2": MigrationPhase(
            id="phase_2",
            name="Phase 2 - Use Case Refactoring",
            description="Split services and adjust domain boundaries.",
            items=[],
        ),
        "phase_3": MigrationPhase(
            id="phase_3",
            name="Phase 3 - Events & BC Optimization",
            description="Introduce events/sagas and align bounded contexts.",
            items=[],
        ),
    }
    for item in items:
        if item.item_type in (
            MigrationItemType.MOVE_TO_LAYER,
            MigrationItemType.FIX_REPOSITORY_LEAK,
            MigrationItemType.INTRODUCE_PORT,
        ):
            phase_map["phase_1"].items.append(item)
        elif item.item_type in (
            MigrationItemType.SPLIT_SERVICE,
            MigrationItemType.EXTRACT_DOMAIN_LOGIC,
            MigrationItemType.RESTRUCTURE_USE_CASE,
        ):
            phase_map["phase_2"].items.append(item)
        else:
            phase_map["phase_3"].items.append(item)

    return list(phase_map.values())


def render_migration_plan_markdown(plan: MigrationPlan) -> str:
    lines = [
        f"# Migration Plan: {plan.current_project_name} → {plan.target_name}",
        "",
    ]
    for phase in plan.phases:
        lines.append(f"## {phase.name}")
        lines.append("")
        for item in phase.items:
            lines.append(f"- [ ] ({item.priority.value.upper()}) {item.title}")
            lines.append(f"  - Type: {item.item_type.value}")
            if item.related_components:
                lines.append(f"  - Components: {', '.join(item.related_components)}")
            if item.related_use_cases:
                lines.append(f"  - Use Cases: {', '.join(item.related_use_cases)}")
            if item.related_bc_ids:
                lines.append(f"  - Bounded Contexts: {', '.join(item.related_bc_ids)}")
            lines.append(f"  - Rationale: {item.rationale}")
            lines.append("")
    return "\n".join(lines)


def render_migration_plan_csv(plan: MigrationPlan) -> str:
    rows = [
        "phase,item_id,priority,type,title,description,rationale,components,use_cases,bounded_contexts,tags"
    ]
    for phase in plan.phases:
        for item in phase.items:
            rows.append(
                ",".join(
                    [
                        phase.name,
                        item.id,
                        item.priority.value,
                        item.item_type.value,
                        _csv(item.title),
                        _csv(item.description),
                        _csv(item.rationale),
                        _csv(";".join(item.related_components)),
                        _csv(";".join(item.related_use_cases)),
                        _csv(";".join(item.related_bc_ids)),
                        _csv(";".join(item.tags)),
                    ]
                )
            )
    return "\n".join(rows)


def render_migration_plan_plain(plan: MigrationPlan) -> str:
    lines = [f"Migration Plan: {plan.current_project_name} -> {plan.target_name}", ""]
    for phase in plan.phases:
        lines.append(phase.name)
        for item in phase.items:
            lines.append(f"- ({item.priority.value.upper()}) {item.title}")
            lines.append(f"  {item.description}")
            lines.append(f"  Rationale: {item.rationale}")
        lines.append("")
    return "\n".join(lines)


def _csv(value: str) -> str:
    if "," in value or "\"" in value or "\n" in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def _match_blueprint(name: str, target_spec: TargetArchitectureSpec):
    for blueprint in target_spec.use_case_blueprints.values():
        if blueprint.name.lower() == name.lower():
            return blueprint
    return None


def _match_target_bc(bc, target_spec: TargetArchitectureSpec):
    for target in target_spec.bounded_contexts.values():
        for pattern in target.package_patterns:
            if matches_package(pattern, bc.name):
                return target
    return None
