from __future__ import annotations

from pathlib import Path
from typing import Tuple

from analyzer.pipeline import analyze_project
from core.graph_loader import load_graph


def analyze_command(project_path: Path, output_path: Path | None) -> Tuple[Path, object]:
    project_root = project_path.resolve()
    output = output_path.resolve() if output_path else project_root / "architecture.json"
    graph = analyze_project(project_root, output)
    return output, graph


def load_graph_command(graph_path: Path) -> object:
    return load_graph(graph_path)


def open_ui(graph, project_root: Path | None) -> int:
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
    window.show()
    return app.exec()
