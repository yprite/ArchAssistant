from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Tuple

from analyzer.model import Component, Dependency, Graph


class Layer(enum.Enum):
    DOMAIN = "domain"
    APPLICATION = "application"
    INBOUND_ADAPTER = "inbound_adapter"
    INBOUND_PORT = "inbound_port"
    OUTBOUND_PORT = "outbound_port"
    OUTBOUND_ADAPTER = "outbound_adapter"
    UNKNOWN = "unknown"


def map_layer(value: str) -> Layer:
    for layer in Layer:
        if layer.value == value:
            return layer
    return Layer.UNKNOWN


ALLOWED_DEPENDENCIES: Dict[Layer, set[Layer]] = {
    Layer.DOMAIN: {Layer.DOMAIN, Layer.UNKNOWN},
    Layer.APPLICATION: {
        Layer.APPLICATION,
        Layer.DOMAIN,
        Layer.INBOUND_PORT,
        Layer.OUTBOUND_PORT,
        Layer.UNKNOWN,
    },
    Layer.INBOUND_ADAPTER: {Layer.INBOUND_PORT, Layer.APPLICATION, Layer.UNKNOWN},
    Layer.INBOUND_PORT: {Layer.APPLICATION, Layer.DOMAIN, Layer.UNKNOWN},
    Layer.OUTBOUND_PORT: {Layer.DOMAIN, Layer.APPLICATION, Layer.UNKNOWN},
    Layer.OUTBOUND_ADAPTER: {Layer.OUTBOUND_PORT, Layer.UNKNOWN},
    Layer.UNKNOWN: {
        Layer.UNKNOWN,
        Layer.DOMAIN,
        Layer.APPLICATION,
        Layer.INBOUND_PORT,
        Layer.OUTBOUND_PORT,
        Layer.INBOUND_ADAPTER,
        Layer.OUTBOUND_ADAPTER,
    },
}


@dataclass(frozen=True)
class RuleViolation:
    rule_id: str
    severity: str
    message: str
    source_component_id: str
    target_component_id: str | None
    source_layer: Layer
    target_layer: Layer | None
    dependency_kind: str


class RuleAnalysisSummary(NamedTuple):
    score: int
    total_components: int
    total_dependencies: int
    total_violations: int
    violations_by_rule: Dict[str, int]
    violations_by_layer_pair: Dict[Tuple[Layer, Layer], int]


SEVERITY_WEIGHT = {"info": 1, "warning": 3, "error": 7}
EXTRA_RULE_WEIGHT = {
    "DOMAIN_DEPENDS_ON_ADAPTER": 5,
    "APPLICATION_DEPENDS_ON_ADAPTER": 4,
    "ADAPTER_DIRECTLY_DEPENDS_ON_DOMAIN": 4,
}


def analyze_layer_rules(graph: Graph) -> List[RuleViolation]:
    components = {component.id: component for component in graph.components}
    violations: List[RuleViolation] = []

    for dep in graph.dependencies:
        source = components.get(dep.source_id)
        target = components.get(dep.target_id)
        if not source or not target:
            continue
        source_layer = map_layer(source.layer)
        target_layer = map_layer(target.layer)
        allowed = ALLOWED_DEPENDENCIES.get(source_layer, set())
        if target_layer not in allowed:
            violations.append(
                RuleViolation(
                    rule_id="FORBIDDEN_LAYER_DEPENDENCY",
                    severity="warning",
                    message=(
                        f"Layer rule violation: '{source.name}' ({source.layer}) "
                        f"depends on '{target.name}' ({target.layer})."
                    ),
                    source_component_id=source.id,
                    target_component_id=target.id,
                    source_layer=source_layer,
                    target_layer=target_layer,
                    dependency_kind=dep.kind,
                )
            )

        if source_layer == Layer.DOMAIN and target_layer in (
            Layer.INBOUND_ADAPTER,
            Layer.OUTBOUND_ADAPTER,
        ):
            violations.append(
                RuleViolation(
                    rule_id="DOMAIN_DEPENDS_ON_ADAPTER",
                    severity="error",
                    message=(
                        f"Domain layer component '{source.name}' depends on adapter "
                        f"'{target.name}'. Domain must not depend on any adapter."
                    ),
                    source_component_id=source.id,
                    target_component_id=target.id,
                    source_layer=source_layer,
                    target_layer=target_layer,
                    dependency_kind=dep.kind,
                )
            )

        if source_layer == Layer.APPLICATION and target_layer in (
            Layer.INBOUND_ADAPTER,
            Layer.OUTBOUND_ADAPTER,
        ):
            violations.append(
                RuleViolation(
                    rule_id="APPLICATION_DEPENDS_ON_ADAPTER",
                    severity="warning",
                    message=(
                        f"Application component '{source.name}' depends on adapter "
                        f"'{target.name}'. Prefer ports instead."
                    ),
                    source_component_id=source.id,
                    target_component_id=target.id,
                    source_layer=source_layer,
                    target_layer=target_layer,
                    dependency_kind=dep.kind,
                )
            )

        if source_layer in (Layer.INBOUND_ADAPTER, Layer.OUTBOUND_ADAPTER) and target_layer == Layer.DOMAIN:
            violations.append(
                RuleViolation(
                    rule_id="ADAPTER_DIRECTLY_DEPENDS_ON_DOMAIN",
                    severity="warning",
                    message=(
                        f"Adapter '{source.name}' directly depends on domain "
                        f"'{target.name}'. Prefer ports/use-cases."
                    ),
                    source_component_id=source.id,
                    target_component_id=target.id,
                    source_layer=source_layer,
                    target_layer=target_layer,
                    dependency_kind=dep.kind,
                )
            )

    return violations


def score_project(violations: List[RuleViolation]) -> int:
    score = 100
    for violation in violations:
        base = SEVERITY_WEIGHT.get(violation.severity, 1)
        extra = EXTRA_RULE_WEIGHT.get(violation.rule_id, 0)
        score -= base + extra
    return max(0, score)


def run_rule_analysis(graph: Graph) -> tuple[List[RuleViolation], RuleAnalysisSummary]:
    violations = analyze_layer_rules(graph)
    violations_by_rule: Dict[str, int] = {}
    violations_by_layer_pair: Dict[Tuple[Layer, Layer], int] = {}
    for violation in violations:
        violations_by_rule[violation.rule_id] = violations_by_rule.get(violation.rule_id, 0) + 1
        if violation.source_layer and violation.target_layer:
            key = (violation.source_layer, violation.target_layer)
            violations_by_layer_pair[key] = violations_by_layer_pair.get(key, 0) + 1

    summary = RuleAnalysisSummary(
        score=score_project(violations),
        total_components=len(graph.components),
        total_dependencies=len(graph.dependencies),
        total_violations=len(violations),
        violations_by_rule=violations_by_rule,
        violations_by_layer_pair=violations_by_layer_pair,
    )
    return violations, summary
