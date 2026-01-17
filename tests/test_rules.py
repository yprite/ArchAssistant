from analyzer.model import Component, Dependency, Graph
from architecture.rules import analyze_layer_rules, run_rule_analysis


def test_domain_depends_on_adapter_violation() -> None:
    graph = Graph(
        components=[
            Component(id="domain.Order", name="Order", path="", package="", layer="domain"),
            Component(
                id="adapter.OrderController",
                name="OrderController",
                path="",
                package="",
                layer="inbound_adapter",
            ),
        ],
        dependencies=[
            Dependency(source_id="domain.Order", target_id="adapter.OrderController", kind="import")
        ],
    )
    violations = analyze_layer_rules(graph)
    assert any(v.rule_id == "DOMAIN_DEPENDS_ON_ADAPTER" for v in violations)
    _, summary = run_rule_analysis(graph)
    assert summary.score < 100


def test_clean_graph_has_no_violations() -> None:
    graph = Graph(
        components=[
            Component(id="domain.Order", name="Order", path="", package="", layer="domain"),
            Component(
                id="app.PlaceOrderService",
                name="PlaceOrderService",
                path="",
                package="",
                layer="application",
            ),
        ],
        dependencies=[
            Dependency(
                source_id="app.PlaceOrderService", target_id="domain.Order", kind="import"
            )
        ],
    )
    violations, summary = run_rule_analysis(graph)
    assert not violations
    assert summary.score == 100


def test_application_depends_on_adapter_violation() -> None:
    graph = Graph(
        components=[
            Component(
                id="app.Service", name="Service", path="", package="", layer="application"
            ),
            Component(
                id="adapter.JpaRepo",
                name="JpaRepo",
                path="",
                package="",
                layer="outbound_adapter",
            ),
        ],
        dependencies=[
            Dependency(source_id="app.Service", target_id="adapter.JpaRepo", kind="import")
        ],
    )
    violations = analyze_layer_rules(graph)
    assert any(v.rule_id == "APPLICATION_DEPENDS_ON_ADAPTER" for v in violations)
