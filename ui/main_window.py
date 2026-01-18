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
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QScrollArea,
    QWidget,
)
import json

from analyzer.pipeline import analyze_project
from architecture.rules import run_rule_analysis
from analysis.smells import ComponentMetricsProvider, analyze_project_smells
from analysis.bounded_context import analyze_bounded_contexts, BoundedContextAnalysisResult
from analysis.target_architecture import load_target_architecture_spec, TargetArchitectureSpec
from analysis.migration_planner import (
    build_migration_plan,
    render_migration_plan_csv,
    render_migration_plan_markdown,
    render_migration_plan_plain,
)
from core.flow import compute_flow_path
from analysis.event_readiness import analyze_project_event_readiness
from core.graph_loader import load_graph
from core.use_case_utils import is_use_case_entry
from analysis.use_case_report import build_use_case_reports, UseCaseReportSet
from ui.inspector_panel import InspectorPanel
from ui.left_sidebar import LeftSidebar
from ui.rules_panel import ArchitectureRulesPanel
from ui.smells_panel import SmellsPanel, smell_color_key
from ui.colors import SMELL_COLORS
from ui.context_map_scene import ContextMapScene
from ui.context_map_view import ContextMapView
from ui.context_map_panel import ContextMapInfoPanel
from ui.migration_planner_panel import MigrationPlannerPanel
from ui.event_readiness_panel import EventReadinessPanel
from ui.minimap_view import MinimapView
from ui.view import ArchitectureView
from ui.flow_animation_controller import FlowAnimationController, FlowStep
from ui.scene import ArchitectureScene
from ui.use_case_report_panel import UseCaseReportPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DDD Architecture Viewer")
        self.resize(1200, 800)
        self.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.ForceTabbedDocks
        )

        self.project_root: Path | None = None
        self.scene = ArchitectureScene()
        self.view = ArchitectureView(self.scene)
        self.context_scene = ContextMapScene()
        self.context_view = ContextMapView(self.context_scene)
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.view)
        self.view_stack.addWidget(self.context_view)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(self.view.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.view.setBackgroundBrush(QColor("#F5F5F7"))
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._central_container = QWidget()
        central_layout = QVBoxLayout(self._central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.view_stack)
        self.setCentralWidget(self._central_container)
        self.view.setFocus()
        self.view.set_zoom_reset_callback(self._zoom_to_fit)
        self.view.set_flow_controls(
            self._play_flow_animation,
            self._pause_flow_animation,
            self._step_flow_animation,
            self._restart_flow_animation,
        )
        self.minimap = MinimapView(self.view, self.scene)
        self.minimap.setParent(self.view.viewport())
        self.view.set_minimap(self.minimap)
        self.view.viewport_changed.connect(self.minimap.schedule_viewport_update)
        self.scene.changed.connect(self.minimap.schedule_refresh)

        self.inspector = InspectorPanel()
        self.search_matches: list[str] = []
        self.search_index = 0
        self._last_hovered_id: str | None = None
        self._inspector_dock: QDockWidget | None = None
        self._rules_dock: QDockWidget | None = None
        self._report_dock: QDockWidget | None = None
        self._readiness_dock: QDockWidget | None = None
        self._smells_dock: QDockWidget | None = None
        self._context_dock: QDockWidget | None = None
        self._left_dock: QDockWidget | None = None
        self._migration_dock: QDockWidget | None = None
        self._init_actions()
        self._init_docks()
        self._current_graph = None
        self._flow_animation: FlowAnimationController | None = None
        self._last_flow_nodes: list = []
        self._violations_by_component: dict[str, list] = {}
        self._violations: list = []
        self._event_readiness = None
        self._smell_summary = None
        self._smells_by_component: dict[str, list] = {}
        self._bc_analysis: BoundedContextAnalysisResult | None = None
        self._component_to_bc: dict[str, str] = {}
        self._use_case_reports: UseCaseReportSet | None = None
        self._building_reports = False
        self._target_spec: TargetArchitectureSpec | None = None
        self._migration_plan = None

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
        self._init_menu()

    def _init_docks(self) -> None:
        left_sidebar = LeftSidebar()
        self.filter_boxes = left_sidebar.filter_boxes
        for box in self.filter_boxes.values():
            box.stateChanged.connect(self._update_layer_filters)

        filter_dock = QDockWidget("Legend & Filters", self)
        filter_dock.setWidget(left_sidebar)
        filter_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        filter_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        filter_dock.setMinimumWidth(220)
        left_sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.LeftDockWidgetArea, filter_dock)
        self._left_dock = filter_dock

        inspector_dock = QDockWidget("Inspector", self)
        inspector_dock.setWidget(self._wrap_scroll(self.inspector))
        inspector_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        inspector_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        inspector_dock.setMinimumWidth(320)
        inspector_dock.setMaximumWidth(420)
        inspector_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.inspector.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, inspector_dock)
        self._inspector_dock = inspector_dock

        self.rules_panel = ArchitectureRulesPanel()
        self.rules_panel.violation_selected.connect(self._on_rule_violation_selected)
        rules_dock = QDockWidget("Architecture Rules", self)
        rules_dock.setWidget(self._wrap_scroll(self.rules_panel))
        rules_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        rules_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        rules_dock.setMinimumWidth(320)
        rules_dock.setMaximumWidth(420)
        rules_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.rules_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, rules_dock)
        self.tabifyDockWidget(inspector_dock, rules_dock)
        self._rules_dock = rules_dock

        self.report_panel = UseCaseReportPanel()
        if hasattr(self, "_on_use_case_step_selected"):
            self.report_panel.step_selected.connect(self._on_use_case_step_selected)
        self.report_panel.export_requested.connect(self._export_use_case_report)
        self.report_panel.suggestion_selected.connect(self._on_report_suggestion_selected)
        report_dock = QDockWidget("Use Case Report", self)
        report_dock.setWidget(self._wrap_scroll(self.report_panel))
        report_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        report_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        report_dock.setMinimumWidth(320)
        report_dock.setMaximumWidth(420)
        report_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.report_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, report_dock)
        self.tabifyDockWidget(inspector_dock, report_dock)
        self._report_dock = report_dock

        self.smells_panel = SmellsPanel()
        self.smells_panel.smell_selected.connect(self._on_smell_selected)
        smells_dock = QDockWidget("DDD Smells", self)
        smells_dock.setWidget(self._wrap_scroll(self.smells_panel))
        smells_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        smells_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        smells_dock.setMinimumWidth(320)
        smells_dock.setMaximumWidth(420)
        smells_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.smells_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, smells_dock)
        self.tabifyDockWidget(inspector_dock, smells_dock)
        self._smells_dock = smells_dock

        self.readiness_panel = EventReadinessPanel()
        self.readiness_panel.use_case_selected.connect(self._on_readiness_use_case_selected)
        readiness_dock = QDockWidget("Event-Driven Readiness", self)
        readiness_dock.setWidget(self._wrap_scroll(self.readiness_panel))
        readiness_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        readiness_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        readiness_dock.setMinimumWidth(320)
        readiness_dock.setMaximumWidth(420)
        readiness_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.readiness_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, readiness_dock)
        self.tabifyDockWidget(inspector_dock, readiness_dock)
        self._readiness_dock = readiness_dock

        self.context_panel = ContextMapInfoPanel()
        context_dock = QDockWidget("Context Map Info", self)
        context_dock.setWidget(self._wrap_scroll(self.context_panel))
        context_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        context_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        context_dock.setMinimumWidth(320)
        context_dock.setMaximumWidth(420)
        context_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.context_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, context_dock)
        self.tabifyDockWidget(inspector_dock, context_dock)
        self._context_dock = context_dock

        self.context_scene.bc_selected.connect(self._on_bc_selected)

        self.migration_panel = MigrationPlannerPanel()
        self.migration_panel.override_target_requested.connect(self._load_target_spec_override)
        self.migration_panel.refresh_requested.connect(self._rebuild_migration_plan)
        self.migration_panel.export_markdown_requested.connect(
            self._export_migration_markdown
        )
        self.migration_panel.export_csv_requested.connect(self._export_migration_csv)
        self.migration_panel.export_plain_requested.connect(self._export_migration_plain)
        self.migration_panel.item_selected.connect(self._on_migration_item_selected)
        migration_dock = QDockWidget("Migration Planner", self)
        migration_dock.setWidget(self._wrap_scroll(self.migration_panel))
        migration_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        migration_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        migration_dock.setMinimumWidth(320)
        migration_dock.setMaximumWidth(420)
        migration_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.migration_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, migration_dock)
        self.tabifyDockWidget(inspector_dock, migration_dock)
        self._migration_dock = migration_dock

        self._setup_default_layout()

    def _init_menu(self) -> None:
        analyze_menu = self.menuBar().addMenu("Analyze")
        run_rules_action = QAction("Run Architecture Rule Check", self)
        run_rules_action.triggered.connect(self._run_rule_check)
        analyze_menu.addAction(run_rules_action)
        run_smells_action = QAction("Run DDD Smell Detector", self)
        run_smells_action.triggered.connect(self._run_smell_analysis)
        analyze_menu.addAction(run_smells_action)
        readiness_action = QAction("Event-Driven Readiness", self)
        readiness_action.triggered.connect(self._run_event_readiness)
        analyze_menu.addAction(readiness_action)

        view_menu = self.menuBar().addMenu("View")
        hex_view_action = QAction("Hex View", self)
        hex_view_action.triggered.connect(self._show_hex_view)
        context_map_action = QAction("Context Map", self)
        context_map_action.triggered.connect(self._show_context_map)
        clear_bc_action = QAction("Clear BC Filter", self)
        clear_bc_action.triggered.connect(self._clear_bc_filter)
        view_menu.addAction(hex_view_action)
        view_menu.addAction(context_map_action)
        view_menu.addAction(clear_bc_action)
        view_menu.addSeparator()
        toggle_theme_action = QAction("Toggle Dark Theme", self)
        toggle_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme_action)
        reset_layout_action = QAction("Reset Layout", self)
        reset_layout_action.triggered.connect(self._setup_default_layout)
        view_menu.addAction(reset_layout_action)

        file_menu = self.menuBar().addMenu("File")
        export_md_action = QAction("Export Migration Plan (Markdown)...", self)
        export_md_action.triggered.connect(self._export_migration_markdown)
        export_csv_action = QAction("Export Migration Plan (CSV)...", self)
        export_csv_action.triggered.connect(self._export_migration_csv)
        export_plain_action = QAction("Export Migration Plan (Plain)...", self)
        export_plain_action.triggered.connect(self._export_migration_plain)
        file_menu.addAction(export_md_action)
        file_menu.addAction(export_csv_action)
        file_menu.addAction(export_plain_action)

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
        self._current_graph = graph
        for item in self.scene.component_items.values():
            item.clicked.connect(self._on_component_clicked)
            item.hovered.connect(self._on_component_hovered)
            item.double_clicked.connect(self._open_component_path)
        self._update_layer_filters()
        self._apply_layer_focus()
        self.inspector.flow_button.clicked.connect(self._show_flow_from_inspector)
        self.inspector.clear_flow_button.clicked.connect(self._clear_flow)
        self.inspector.flow_list.itemClicked.connect(self._on_flow_item_clicked)
        self.inspector.animate_flow_button.clicked.connect(self._play_flow_animation)
        self.inspector.flow_speed.currentTextChanged.connect(self._update_flow_speed)
        self.inspector.violations_list.itemClicked.connect(self._on_component_violation_clicked)
        self.inspector.smells_list.itemClicked.connect(self._on_component_smell_clicked)
        self.inspector.report_button.clicked.connect(self._show_use_case_report_for_selection)
        self._run_rule_check()
        self._run_smell_analysis()
        self._run_bounded_context_analysis()
        self._build_use_case_reports()
        self._auto_load_or_create_target_spec()
        self._setup_default_layout()

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
        if is_use_case_entry(component) and self._use_case_reports:
            self.report_panel.select_use_case(component.id)
            if self._report_dock:
                self._report_dock.raise_()
        path = Path(component.path)
        if self.project_root and not path.is_absolute():
            path = self.project_root / path
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _on_component_clicked(self, component) -> None:
        self.inspector.show_component(component)
        self.scene.set_active_component(component.id)
        self._show_component_violations(component.id)
        self._show_component_smells(component.id)
        self.inspector.report_button.setEnabled(is_use_case_entry(component))
        bc_id = self._component_to_bc.get(component.id)
        if bc_id and self._bc_analysis:
            self.context_scene.highlight_bc(bc_id)
            context = self._bc_analysis.contexts.get(bc_id)
            if context:
                self.context_panel.show_context(context)
        if is_use_case_entry(component) and self._use_case_reports:
            self.report_panel.select_use_case(component.id)

    def _on_component_hovered(self, component, hovered: bool) -> None:
        if hovered:
            self._last_hovered_id = component.id
            self.inspector.show_component(component)
            self.inspector.report_button.setEnabled(is_use_case_entry(component))
            self._show_component_smells(component.id)
        else:
            if self._last_hovered_id == component.id:
                self._last_hovered_id = None
            if self.scene.active_component_id:
                active = self.scene.component_items.get(self.scene.active_component_id)
                if active:
                    self.inspector.show_component(active.component)
                    self.inspector.report_button.setEnabled(
                        is_use_case_entry(active.component)
                    )
                    self._show_component_smells(active.component.id)

    def _generate_use_case_report(self) -> None:
        return

    def _show_use_case_report_for_selection(self) -> None:
        component = self.inspector.current_component()
        if not component:
            return
        if not self._use_case_reports:
            self._build_use_case_reports()
        if not self._use_case_reports:
            return
        self.report_panel.select_use_case(component.id)
        if self._report_dock:
            self._report_dock.raise_()

    def _on_use_case_step_selected(self, index: int) -> None:
        if not self._use_case_reports:
            return
        current_id = self.report_panel.use_case_box.currentData()
        report = self._use_case_reports.reports.get(current_id) if current_id else None
        if not report or index < 0 or index >= len(report.flow_steps):
            return
        step = report.flow_steps[index]
        self._focus_component(step.component_id)

    def _export_use_case_report(self) -> None:
        if not self._use_case_reports:
            return
        current_id = self.report_panel.use_case_box.currentData()
        report = self._use_case_reports.reports.get(current_id) if current_id else None
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Use Case Report", "", "Markdown (*.md)"
        )
        if not path:
            return
        Path(path).write_text(self.report_panel.markdown_text.toPlainText(), encoding="utf-8")

    def _run_rule_check(self) -> None:
        if not self._current_graph:
            return
        violations, summary = run_rule_analysis(self._current_graph)
        self._violations = violations
        self.rules_panel.show_results(summary, violations)
        self._violations_by_component = {}
        for violation in violations:
            self._violations_by_component.setdefault(violation.source_component_id, []).append(
                violation
            )
            if violation.target_component_id:
                self._violations_by_component.setdefault(violation.target_component_id, []).append(
                    violation
                )
        self.scene.apply_rule_violations(violations)
        if self.scene.active_component_id:
            self._show_component_violations(self.scene.active_component_id)
        self._build_use_case_reports()

    def _run_smell_analysis(self) -> None:
        if not self._current_graph:
            return
        components = {component.id: component for component in self._current_graph.components}
        metrics = ComponentMetricsProvider(components)
        summary = analyze_project_smells(self._current_graph, metrics)
        self._smell_summary = summary
        self.smells_panel.show_results(summary)
        self._smells_by_component = {}
        for smell in summary.smells:
            self._smells_by_component.setdefault(smell.component_id, []).append(smell)
        if self.scene.active_component_id:
            self._show_component_smells(self.scene.active_component_id)
        self._build_use_case_reports()

    def _run_bounded_context_analysis(self) -> None:
        if not self._current_graph:
            return
        self._bc_analysis = analyze_bounded_contexts(self._current_graph)
        self.context_scene.load_analysis(self._bc_analysis)
        self._component_to_bc = {}
        for bc in self._bc_analysis.contexts.values():
            for component_id in bc.component_ids:
                self._component_to_bc[component_id] = bc.id
        self._build_use_case_reports()

    def _build_use_case_reports(self) -> None:
        if not self._current_graph or self._building_reports:
            return
        self._building_reports = True
        try:
            if not self._bc_analysis:
                self._run_bounded_context_analysis()
            if not self._event_readiness:
                self._event_readiness = analyze_project_event_readiness(
                    self._current_graph, self._violations_by_component
                )
            if not self._smell_summary:
                self._run_smell_analysis()
            if not self._bc_analysis or not self._event_readiness or not self._smell_summary:
                return
            self._use_case_reports = build_use_case_reports(
                self._current_graph,
                self._violations_by_component,
                self._smell_summary,
                self._event_readiness,
                self._bc_analysis,
            )
            self.report_panel.set_reports(self._use_case_reports)
        finally:
            self._building_reports = False

    def _load_target_spec(self) -> None:
        return

    def _load_target_spec_override(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Override Target Architecture", "", "JSON Files (*.json)"
        )
        if not path:
            return
        self._load_target_spec_from_path(Path(path))
        self._save_target_settings(Path(path))
        self._rebuild_migration_plan()

    def _rebuild_migration_plan(self) -> None:
        if not self._current_graph or not self._target_spec:
            return
        if not self._use_case_reports:
            self._build_use_case_reports()
        if not self._event_readiness:
            self._event_readiness = analyze_project_event_readiness(
                self._current_graph, self._violations_by_component
            )
        if not self._smell_summary:
            self._run_smell_analysis()
        if not self._bc_analysis:
            self._run_bounded_context_analysis()
        if not self._use_case_reports or not self._bc_analysis or not self._smell_summary:
            return
        self._migration_plan = build_migration_plan(
            current_graph=self._current_graph,
            target_spec=self._target_spec,
            rules_summary=run_rule_analysis(self._current_graph)[1],
            rules_index=self._violations_by_component,
            smells_summary=self._smell_summary,
            event_readiness=self._event_readiness,
            bc_result=self._bc_analysis,
            use_case_reports=self._use_case_reports,
            current_project_name=str(self.project_root) if self.project_root else "Current",
        )
        self.migration_panel.set_plan(self._migration_plan)
        self.migration_panel.set_status("Migration plan refreshed.")

    def _export_migration_markdown(self) -> None:
        if not self._migration_plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Migration Plan (Markdown)", "", "Markdown (*.md)"
        )
        if not path:
            return
        Path(path).write_text(render_migration_plan_markdown(self._migration_plan), encoding="utf-8")

    def _export_migration_csv(self) -> None:
        if not self._migration_plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Migration Plan (CSV)", "", "CSV (*.csv)"
        )
        if not path:
            return
        Path(path).write_text(render_migration_plan_csv(self._migration_plan), encoding="utf-8")

    def _export_migration_plain(self) -> None:
        if not self._migration_plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Migration Plan (Plain)", "", "Text (*.txt)"
        )
        if not path:
            return
        Path(path).write_text(render_migration_plan_plain(self._migration_plan), encoding="utf-8")

    def _on_migration_item_selected(self, item) -> None:
        if not item:
            return
        if item.related_components:
            self.scene.set_component_focus(set(item.related_components))
        if item.related_use_cases and self._use_case_reports:
            self.report_panel.select_use_case(item.related_use_cases[0])
            if self._report_dock:
                self._report_dock.raise_()

    def _auto_load_or_create_target_spec(self) -> None:
        if not self.project_root or not self._current_graph:
            return
        settings_path = self._target_settings_path()
        target_path = None
        if settings_path.exists():
            try:
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                saved = data.get("last_target_json_path")
                if saved and Path(saved).exists():
                    target_path = Path(saved)
            except json.JSONDecodeError:
                target_path = None

        if not target_path:
            for candidate in [
                self.project_root / "ddd_target.json",
                self.project_root / ".ddd" / "target.json",
                self.project_root / "migration" / "target_architecture.json",
            ]:
                if candidate.exists():
                    target_path = candidate
                    break

        if target_path and target_path.exists():
            self._load_target_spec_from_path(target_path)
            self._save_target_settings(target_path)
            self.migration_panel.set_status(
                f"Target loaded from {target_path.name}"
            )
            self._rebuild_migration_plan()
            return

        target_path = self.project_root / "ddd_target.json"
        self._generate_default_target_spec(target_path)
        self._load_target_spec_from_path(target_path)
        self._save_target_settings(target_path)
        self.migration_panel.set_status(
            "Target auto-generated from current analysis."
        )
        self._rebuild_migration_plan()

    def _generate_default_target_spec(self, path: Path) -> None:
        if not self._bc_analysis:
            self._run_bounded_context_analysis()
        if not self._use_case_reports:
            self._build_use_case_reports()
        if not self._bc_analysis or not self._use_case_reports:
            return

        bounded_contexts = []
        for bc in self._bc_analysis.contexts.values():
            prefix = bc.name or "unknown"
            bounded_contexts.append(
                {
                    "id": bc.id,
                    "name": prefix,
                    "packagePatterns": [f"{prefix}.*"] if prefix else [],
                    "expectedLayers": [
                        "domain",
                        "application",
                        "inbound_port",
                        "outbound_port",
                        "inbound_adapter",
                        "outbound_adapter",
                    ],
                    "notes": "Auto-generated from current analysis",
                }
            )

        use_cases = []
        for report in self._use_case_reports.reports.values():
            use_cases.append(
                {
                    "id": report.use_case_id,
                    "name": report.use_case_name,
                    "boundedContextId": report.bc_summary.entry_bc_id,
                    "expectedFlowLayers": [
                        "inbound_adapter",
                        "inbound_port",
                        "application",
                        "domain",
                        "outbound_port",
                        "outbound_adapter",
                    ],
                    "expectedEvents": [],
                }
            )

        data = {
            "name": "Auto Generated Target",
            "boundedContexts": bounded_contexts,
            "useCaseBlueprints": use_cases,
            "moduleGuidelines": {
                "allowRepositoryAnnotationsInDomain": False,
                "allowDirectAdapterToDomain": False,
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_target_spec_from_path(self, path: Path) -> None:
        self._target_spec = load_target_architecture_spec(str(path))
        self.migration_panel.set_target_name(f"{self._target_spec.name} ({path.name})")

    def _target_settings_path(self) -> Path:
        return (self.project_root / ".ddd" / "settings.json") if self.project_root else Path("settings.json")

    def _save_target_settings(self, path: Path) -> None:
        if not self.project_root:
            return
        settings_path = self._target_settings_path()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {"last_target_json_path": str(path)}
        settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    def _on_bc_selected(self, bc_id: str) -> None:
        if not self._bc_analysis:
            return
        context = self._bc_analysis.contexts.get(bc_id)
        if not context:
            return
        self.context_panel.show_context(context)
        self.scene.set_bc_filter(set(context.component_ids))

    def _show_hex_view(self) -> None:
        self.view_stack.setCurrentWidget(self.view)
        self.view.set_overlays_visible(True)
        self.minimap.setVisible(True)
        self.view.setFocus()

    def _show_context_map(self) -> None:
        self.view_stack.setCurrentWidget(self.context_view)
        self.view.set_overlays_visible(False)
        self.minimap.setVisible(False)
        self.context_view.setFocus()

    def _clear_bc_filter(self) -> None:
        self.scene.set_bc_filter(None)
        self.context_scene.highlight_bc(None)
        self.context_panel.clear()

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    def _setup_default_layout(self) -> None:
        self.setDockNestingEnabled(True)
        if self._left_dock:
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._left_dock)
            self._left_dock.show()
        if self._inspector_dock:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._inspector_dock)
            self._inspector_dock.show()

        right_docks = [
            self._rules_dock,
            self._report_dock,
            self._smells_dock,
            self._readiness_dock,
            self._context_dock,
            self._migration_dock,
        ]
        for dock in right_docks:
            if dock and self._inspector_dock:
                self.tabifyDockWidget(self._inspector_dock, dock)

        if self._left_dock and self._inspector_dock:
            self.resizeDocks([self._left_dock], [260], Qt.Orientation.Horizontal)
            self.resizeDocks([self._inspector_dock], [360], Qt.Orientation.Horizontal)
        if self._inspector_dock:
            self._inspector_dock.raise_()

    def _show_component_smells(self, component_id: str) -> None:
        smells = self._smells_by_component.get(component_id, [])
        if not smells:
            self.inspector.clear_component_smells()
            return
        items = [
            f"[{smell.severity.value}] {smell.smell_type.value}: {smell.description}"
            for smell in smells
        ]
        self.inspector.show_component_smells(items)

    def _on_component_smell_clicked(self, item) -> None:
        component = self.inspector.current_component()
        if not component:
            return
        smells = self._smells_by_component.get(component.id, [])
        row = self.inspector.smells_list.currentRow()
        if row < 0 or row >= len(smells):
            return
        smell = smells[row]
        color = QColor(SMELL_COLORS.get(smell_color_key(smell.smell_type), "#EF4444"))
        self.scene.focus_on_smell(smell.component_id, color)

    def _on_smell_selected(self, smell) -> None:
        color = QColor(SMELL_COLORS.get(smell_color_key(smell.smell_type), "#EF4444"))
        self.scene.focus_on_smell(smell.component_id, color)
        self._focus_component(smell.component_id)

    def _on_report_suggestion_selected(self, component_ids: list) -> None:
        if not component_ids:
            return
        self.scene.set_component_focus(set(component_ids))

    def _run_event_readiness(self) -> None:
        if not self._current_graph:
            return
        self._event_readiness = analyze_project_event_readiness(
            self._current_graph, self._violations_by_component
        )
        self.readiness_panel.show_results(self._event_readiness)
        if self._readiness_dock:
            self._readiness_dock.raise_()
        self._build_use_case_reports()

    def _on_readiness_use_case_selected(self, component_id: str) -> None:
        if not self._current_graph:
            return
        self._focus_component(component_id)
        flow = compute_flow_path(self._current_graph, component_id)
        if flow.nodes:
            self.scene.apply_flow(flow, component_id)
            self._last_flow_nodes = flow.nodes
        if not self._use_case_reports:
            self._build_use_case_reports()
        if self._use_case_reports:
            self.report_panel.select_use_case(component_id)
        if self._report_dock:
            self._report_dock.raise_()

    def _on_rule_violation_selected(self, violation) -> None:
        self.scene.focus_on_violation(violation)
        edge = self.scene.edge_lookup.get(
            (violation.source_component_id, violation.target_component_id)
        )
        if not edge and violation.target_component_id:
            edge = self.scene.edge_lookup.get(
                (violation.target_component_id, violation.source_component_id)
            )
        if edge:
            point = edge.path().pointAtPercent(0.5)
            self.view.centerOn(point)
        self._show_component_violations(violation.source_component_id)

    def _on_component_violation_clicked(self, item) -> None:
        component = self.inspector.current_component()
        if not component:
            return
        violations = self._violations_by_component.get(component.id, [])
        row = self.inspector.violations_list.currentRow()
        if row < 0 or row >= len(violations):
            return
        self._on_rule_violation_selected(violations[row])

    def _show_component_violations(self, component_id: str) -> None:
        if not self._violations:
            self.inspector.clear_component_violations()
            return
        violations = self._violations_by_component.get(component_id, [])
        items = [f"[{v.severity.upper()}] {v.rule_id}: {v.message}" for v in violations]
        self.inspector.show_component_violations(items)

    def _show_flow_from_inspector(self) -> None:
        component = self.inspector.current_component()
        if not component or not self._current_graph:
            return
        flow = compute_flow_path(self._current_graph, component.id)
        self.scene.apply_flow(flow, component.id)
        self.inspector.show_flow_steps(self._flow_step_labels(flow))
        self._last_flow_nodes = flow.nodes

    def _clear_flow(self) -> None:
        self.scene.clear_flow()
        self.inspector.clear_flow()
        if self._flow_animation:
            self._flow_animation.stop()

    def _flow_step_labels(self, flow) -> list[str]:
        labels = {
            "domain": "Domain",
            "application": "App",
            "inbound_port": "InPort",
            "outbound_port": "OutPort",
            "inbound_adapter": "InAdp",
            "outbound_adapter": "OutAdp",
            "unknown": "Unknown",
        }
        steps = []
        for idx in range(len(flow.nodes) - 1):
            source = flow.nodes[idx]
            target = flow.nodes[idx + 1]
            steps.append(
                f"[{labels.get(source.layer, source.layer)}] {source.name} → "
                f"[{labels.get(target.layer, target.layer)}] {target.name}"
            )
        return steps

    def _on_flow_item_clicked(self, item) -> None:
        row = self.inspector.flow_list.currentRow()
        if row < 0 or row + 1 >= len(self._last_flow_nodes):
            return
        target = self._last_flow_nodes[row + 1]
        self._focus_component(target.id)

    def _play_flow_animation(self) -> None:
        component = self.inspector.current_component()
        if not component or not self._current_graph:
            return
        flow = compute_flow_path(self._current_graph, component.id)
        if not flow.nodes:
            return
        self.scene.apply_flow(flow, component.id)
        self._last_flow_nodes = flow.nodes
        steps = self._build_flow_steps(flow)
        if not steps:
            return
        if self._flow_animation:
            self._flow_animation.stop()
        self._flow_animation = FlowAnimationController(self.scene, steps)
        self._flow_animation.step_changed.connect(self.inspector.set_active_flow_step)
        self._flow_animation.token_updated.connect(self.minimap.schedule_viewport_update)
        self._update_flow_speed()
        self._flow_animation.play()

    def _pause_flow_animation(self) -> None:
        if self._flow_animation:
            self._flow_animation.pause()

    def _step_flow_animation(self) -> None:
        if self._flow_animation:
            self._flow_animation.step_forward()

    def _restart_flow_animation(self) -> None:
        if self._flow_animation:
            self._flow_animation.restart()

    def _update_flow_speed(self) -> None:
        if not self._flow_animation:
            return
        text = self.inspector.flow_speed.currentText().replace("x", "")
        try:
            speed = float(text)
        except ValueError:
            speed = 1.0
        self._flow_animation.set_speed(speed)

    def _build_flow_steps(self, flow) -> list[FlowStep]:
        steps: list[FlowStep] = []
        node_items = {item.component.id: item for item in self.scene.component_items.values()}
        edge_items = {}
        for edge in self.scene.edge_items:
            edge_items[(edge.source_item.component.id, edge.target_item.component.id)] = edge
        base_duration = 400
        for idx in range(len(flow.nodes) - 1):
            source = flow.nodes[idx]
            target = flow.nodes[idx + 1]
            edge = edge_items.get((source.id, target.id)) or edge_items.get(
                (target.id, source.id)
            )
            if not edge:
                continue
            steps.append(
                FlowStep(
                    index=idx,
                    source_item=node_items[source.id],
                    target_item=node_items[target.id],
                    edge_item=edge,
                    duration_ms=base_duration,
                )
            )
        return steps

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

    def _apply_toolbar_styles(self, toolbar: QToolBar) -> None:
        colors = self._get_theme_colors()
        toolbar.setStyleSheet(
            f"QToolBar {{ spacing: 8px; padding: 6px; background: {colors['surface']}; }}"
            f"QLineEdit {{ padding: 6px 10px; border-radius: 10px;"
            f" border: 1px solid {colors['border']}; background: {colors['surface']}; color: {colors['text']}; }}"
            f"QComboBox {{ padding: 6px 8px; border-radius: 10px;"
            f" border: 1px solid {colors['border']}; background: {colors['surface']}; color: {colors['text']}; }}"
            "QToolButton { padding: 6px 10px; border-radius: 8px; }"
        )

    def _get_theme_colors(self) -> dict:
        from core.config import ThemeManager, Theme
        if ThemeManager.get_theme() == Theme.DARK:
            return {
                'background': '#1E1E2E',
                'surface': '#2D2D3D',
                'border': '#4A4A5A',
                'text': '#E4E4E7',
            }
        return {
            'background': '#F5F5F7',
            'surface': '#FFFFFF',
            'border': '#D8D8D8',
            'text': '#2F2F2F',
        }

    def _toggle_theme(self) -> None:
        from core.config import ThemeManager, Theme
        new_theme = ThemeManager.toggle_theme()
        self._apply_theme()
        theme_name = "Dark" if new_theme == Theme.DARK else "Light"
        self.statusBar().showMessage(f"Switched to {theme_name} Theme", 2000)

    def _apply_theme(self) -> None:
        from core.config import ThemeManager, Theme
        colors = self._get_theme_colors()
        
        # 배경색 변경
        self.view.setBackgroundBrush(QColor(colors['background']))
        
        # 툴바 스타일 업데이트
        for toolbar in self.findChildren(QToolBar):
            self._apply_toolbar_styles(toolbar)
        
        # 메인 윈도우 스타일시트
        self.setStyleSheet(f"""
            QMainWindow {{ background: {colors['background']}; }}
            QDockWidget {{ 
                background: {colors['surface']}; 
                color: {colors['text']};
                titlebar-close-icon: url(none);
            }}
            QDockWidget::title {{
                background: {colors['surface']};
                padding: 8px;
            }}
            QMenuBar {{ 
                background: {colors['surface']}; 
                color: {colors['text']};
            }}
            QMenuBar::item:selected {{ background: {colors['border']}; }}
            QMenu {{ 
                background: {colors['surface']}; 
                color: {colors['text']};
            }}
            QMenu::item:selected {{ background: {colors['border']}; }}
            QStatusBar {{ 
                background: {colors['surface']}; 
                color: {colors['text']};
            }}
        """)

    def _show_onboarding(self) -> None:
        """Show onboarding overlay for first-time users"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Welcome to DDD Architecture Viewer")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        
        # Welcome header
        header = QLabel("🏗️ Welcome to DDD Architecture Viewer!")
        header.setStyleSheet("font-size: 20px; font-weight: bold; padding: 16px;")
        layout.addWidget(header)
        
        # Tips
        tips = [
            "📂 <b>Open a Project</b>: Click 'Open Project...' to select your Java/Spring project",
            "🔍 <b>Analyze</b>: Click 'Analyze' to scan and visualize your architecture",
            "🖱️ <b>Navigate</b>: Scroll to zoom, right-click drag to pan, drag nodes to rearrange",
            "🎯 <b>Focus</b>: Click on components to see details in the Inspector panel",
            "🌙 <b>Dark Mode</b>: View → Toggle Dark Theme for dark mode",
        ]
        
        for tip in tips:
            tip_label = QLabel(tip)
            tip_label.setWordWrap(True)
            tip_label.setStyleSheet("font-size: 14px; padding: 8px 16px;")
            layout.addWidget(tip_label)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("Get Started!")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #4A74E0;
                color: white;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #3A64D0;
            }
        """)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 첫 실행 시 온보딩 표시 (프로젝트 로드 안됐을 때)
        if not hasattr(self, '_onboarding_shown'):
            self._onboarding_shown = True
            if not self._current_graph:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(500, self._show_onboarding)

