from __future__ import annotations

from pathlib import Path
from typing import Tuple

from analyzer.pipeline import analyze_project
from core.graph_loader import load_graph
from architecture.rules import run_rule_analysis


def analyze_command(project_path: Path, output_path: Path | None) -> Tuple[Path, object]:
    project_root = project_path.resolve()
    output = output_path.resolve() if output_path else project_root / "architecture.json"
    graph = analyze_project(project_root, output)
    return output, graph


def load_graph_command(graph_path: Path) -> object:
    return load_graph(graph_path)


def analyze_rules_command(graph_path: Path) -> int:
    graph = load_graph(graph_path)
    violations, summary = run_rule_analysis(graph)
    print(f"Hexagon Purity Score: {summary.score} / 100")
    print(f"Components: {summary.total_components} | Dependencies: {summary.total_dependencies}")
    print(f"Violations: {summary.total_violations}")
    for rule_id, count in summary.violations_by_rule.items():
        print(f"- {rule_id}: {count}")
    for violation in violations:
        target = violation.target_component_id or "-"
        print(
            f"[{violation.severity}] {violation.rule_id} {violation.source_component_id} -> "
            f"{target} ({violation.dependency_kind})"
        )
    return 0


def open_ui(graph, project_root: Path | None, watch: bool = False) -> int:
    try:
        from PySide6.QtWidgets import QApplication

        from ui.main_window import MainWindow
    except ImportError as exc:
        print(f"PySide6 is required to open the UI: {exc}")
        return 1

    app = QApplication([])
    window = MainWindow()
    if project_root:
        window.project_root = project_root
        window.inspector.set_base_path(project_root)
    window._load_graph(graph)
    if watch and project_root:
        window.start_watch(project_root)
    window.show()
    return app.exec()
