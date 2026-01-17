from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from analyzer.pipeline import analyze_project
from core.graph_loader import load_graph
from ui.inspector_panel import InspectorPanel
from ui.legend_panel import LegendPanel
from ui.minimap_view import MinimapView
from ui.view import ArchitectureView
from ui.scene import ArchitectureScene


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DDD Architecture Viewer")
        self.resize(1200, 800)

        self.project_root: Path | None = None
        self.scene = ArchitectureScene()
        self.view = ArchitectureView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(self.view.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.view.setBackgroundBrush(QColor("#F5F5F7"))
        self.setCentralWidget(self.view)
        self.view.setFocus()
        self.view.set_zoom_reset_callback(self._zoom_to_fit)
        self.minimap = MinimapView(self.view, self.scene)
        self.minimap.setParent(self.view.viewport())
        self.view.set_minimap(self.minimap)
        self.view.viewport_changed.connect(self.minimap.schedule_refresh)
        self.scene.changed.connect(self.minimap.schedule_refresh)

        self.inspector = InspectorPanel()
        self.search_matches: list[str] = []
        self.search_index = 0
        self._last_hovered_id: str | None = None
        self._init_actions()
        self._init_docks()

    def _init_actions(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_project_action = QAction("Open Project...", self)
        open_project_action.triggered.connect(self._open_project)
        toolbar.addAction(open_project_action)

        analyze_action = QAction("Analyze", self)
        analyze_action.triggered.connect(self._analyze_project)
        toolbar.addAction(analyze_action)

        open_graph_action = QAction("Open Graph JSON...", self)
        open_graph_action.triggered.connect(self._open_graph)
        toolbar.addAction(open_graph_action)

        toolbar.addSeparator()
        zoom_fit_action = QAction("Zoom to Fit", self)
        zoom_fit_action.triggered.connect(self._zoom_to_fit)
        toolbar.addAction(zoom_fit_action)

        search_label = QLabel("Search")
        search_label.setContentsMargins(12, 0, 4, 0)
        toolbar.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search class or package")
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self._update_search_matches)
        self.search_input.returnPressed.connect(self._find_next_match)
        toolbar.addWidget(self.search_input)
        search_action = QAction("Find", self)
        search_action.triggered.connect(self._find_next_match)
        toolbar.addAction(search_action)

        focus_label = QLabel("Focus")
        focus_label.setContentsMargins(12, 0, 4, 0)
        toolbar.addWidget(focus_label)
        self.focus_box = QComboBox()
        self.focus_box.addItems(
            ["All", "Domain Only", "Application Only", "Ports Only", "Adapter Only"]
        )
        self.focus_box.currentIndexChanged.connect(self._apply_layer_focus)
        toolbar.addWidget(self.focus_box)

        self._apply_toolbar_styles(toolbar)

    def _init_docks(self) -> None:
        legend_panel = LegendPanel()
        self.filter_boxes = legend_panel.filter_boxes
        for box in self.filter_boxes.values():
            box.stateChanged.connect(self._update_layer_filters)

        filter_dock = QDockWidget("Legend & Filters", self)
        filter_dock.setWidget(legend_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, filter_dock)

        inspector_dock = QDockWidget("Inspector", self)
        inspector_dock.setWidget(self.inspector)
        inspector_dock.setMinimumWidth(320)
        inspector_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, inspector_dock)

    def _open_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Project Root")
        if directory:
            self.project_root = Path(directory)
            self.inspector.set_base_path(self.project_root)

    def _analyze_project(self) -> None:
        if not self.project_root:
            QMessageBox.warning(self, "Project Required", "Select a project first.")
            return
        output_path = self.project_root / "architecture.json"
        graph = analyze_project(self.project_root, output_path)
        self._load_graph(graph)

    def _open_graph(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Graph JSON", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        path = Path(file_path)
        self.project_root = path.parent
        self.inspector.set_base_path(self.project_root)
        graph = load_graph(path)
        self._load_graph(graph)

    def _load_graph(self, graph) -> None:
        self.scene.load_graph(graph)
        for item in self.scene.component_items.values():
            item.clicked.connect(self._on_component_clicked)
            item.hovered.connect(self._on_component_hovered)
            item.double_clicked.connect(self._open_component_path)
        self._update_layer_filters()
        self._apply_layer_focus()

    def _update_layer_filters(self) -> None:
        for layer, box in self.filter_boxes.items():
            self.scene.set_layer_visible(layer, box.isChecked())
        self.scene.set_layer_visible("adapter_zone", True)
        inbound_port_box = self.filter_boxes.get("inbound_port")
        outbound_port_box = self.filter_boxes.get("outbound_port")
        ports_visible = (
            bool(inbound_port_box and inbound_port_box.isChecked())
            or bool(outbound_port_box and outbound_port_box.isChecked())
        )
        self.scene.set_layer_visible("ports", bool(ports_visible))

    def _apply_layer_focus(self) -> None:
        focus = self.focus_box.currentText()
        if focus == "All":
            self._set_focus_opacity({})
            self.statusBar().showMessage("All Layers", 1500)
            return

        if focus == "Domain Only":
            self._set_focus_opacity({"domain"})
            self.statusBar().showMessage("Domain Focus Mode", 1500)
        elif focus == "Application Only":
            self._set_focus_opacity({"application"})
            self.statusBar().showMessage("Application Focus Mode", 1500)
        elif focus == "Ports Only":
            self._set_focus_opacity({"inbound_port", "outbound_port", "ports"})
            self.statusBar().showMessage("Ports Focus Mode", 1500)
        elif focus == "Adapter Only":
            self._set_focus_opacity({"inbound_adapter", "outbound_adapter", "adapter_zone"})
            self.statusBar().showMessage("Adapter Focus Mode", 1500)

    def _zoom_to_fit(self) -> None:
        rect = self.scene.graph_bounds()
        self.view.zoom_to_fit(rect)

    def _open_component_path(self, component) -> None:
        if not component.path:
            return
        path = Path(component.path)
        if self.project_root and not path.is_absolute():
            path = self.project_root / path
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _on_component_clicked(self, component) -> None:
        self.inspector.show_component(component)
        self.scene.set_active_component(component.id)

    def _on_component_hovered(self, component, hovered: bool) -> None:
        if hovered:
            self._last_hovered_id = component.id
            self.inspector.show_component(component)
        else:
            if self._last_hovered_id == component.id:
                self._last_hovered_id = None
            if self.scene.active_component_id:
                active = self.scene.component_items.get(self.scene.active_component_id)
                if active:
                    self.inspector.show_component(active.component)

    def _set_focus_opacity(self, focus_layers: set[str]) -> None:
        dim_opacity = 0.2
        layers = [
            "domain",
            "application",
            "inbound_port",
            "outbound_port",
            "inbound_adapter",
            "outbound_adapter",
            "unknown",
            "adapter_zone",
            "ports",
        ]
        for layer in layers:
            if not focus_layers:
                self.scene.set_layer_opacity(layer, 1.0)
            else:
                opacity = 1.0 if layer in focus_layers else dim_opacity
                self.scene.set_layer_opacity(layer, opacity)

    def _update_search_matches(self, text: str) -> None:
        query = text.strip().lower()
        self.search_matches = []
        self.search_index = 0
        if not query:
            return
        for component_id, item in self.scene.component_items.items():
            component = item.component
            haystacks = [component.name.lower(), component.package.lower()]
            if any(query in haystack for haystack in haystacks):
                self.search_matches.append(component_id)

    def _find_next_match(self) -> None:
        if not self.search_matches:
            return
        component_id = self.search_matches[self.search_index % len(self.search_matches)]
        self.search_index += 1
        self._focus_component(component_id)

    def _focus_component(self, component_id: str) -> None:
        item = self.scene.component_items.get(component_id)
        if not item:
            return
        self.scene.set_active_component(component_id)
        self.inspector.show_component(item.component)
        item.flash(3)
        rect = item.sceneBoundingRect().adjusted(-160, -160, 160, 160)
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.reset_zoom()

    def _apply_toolbar_styles(self, toolbar: QToolBar) -> None:
        toolbar.setStyleSheet(
            "QToolBar { spacing: 8px; padding: 6px; }"
            "QLineEdit { padding: 6px 10px; border-radius: 10px;"
            " border: 1px solid #D8D8D8; background: #FFFFFF; }"
            "QComboBox { padding: 6px 8px; border-radius: 10px;"
            " border: 1px solid #D8D8D8; background: #FFFFFF; }"
            "QToolButton { padding: 6px 10px; border-radius: 8px; }"
        )
