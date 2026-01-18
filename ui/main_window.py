from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QAction, QDesktopServices, QColor, QPainter, QBrush, QPixmap, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QToolButton,
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
        self.setWindowTitle("DDD 아키텍처 뷰어")
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
        self.view.setBackgroundBrush(self._build_grid_brush(self._get_theme_colors()))
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
        self._pending_focus_component_id: str | None = None
        self._suppress_report_focus = False
        self._rules_done = False
        self._smells_done = False
        self._readiness_done = False
        self._header_status: QLabel | None = None
        self._header_actions_container: QWidget | None = None
        self._header_actions_layout: QHBoxLayout | None = None
        self._summary_report_action: QAction | None = None
        self._watch_timer: QTimer | None = None
        self._watch_snapshot: dict[str, float] = {}
        self._watch_root: Path | None = None
        self._watch_in_progress = False
        self._apply_theme()

    def _init_actions(self) -> None:
        toolbar = QToolBar("메인")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        def add_group_label(text: str) -> None:
            label = QLabel(text)
            label.setObjectName("toolbarGroupLabel")
            label.setContentsMargins(6, 0, 6, 0)
            toolbar.addWidget(label)

        add_group_label("프로젝트")
        open_project_action = QAction("프로젝트 열기...", self)
        open_project_action.triggered.connect(self._open_project)
        toolbar.addAction(open_project_action)

        analyze_action = QAction("분석", self)
        analyze_action.triggered.connect(self._analyze_project)
        toolbar.addAction(analyze_action)

        open_graph_action = QAction("그래프 JSON 열기...", self)
        open_graph_action.triggered.connect(self._open_graph)
        toolbar.addAction(open_graph_action)

        toolbar.addSeparator()
        add_group_label("보고서")
        self._summary_report_action = QAction("유스케이스 종합 보고서", self)
        self._summary_report_action.setEnabled(False)
        self._summary_report_action.triggered.connect(self._export_use_case_summary_report)
        toolbar.addAction(self._summary_report_action)

        toolbar.addSeparator()
        add_group_label("탐색")
        zoom_fit_action = QAction("화면 맞춤", self)
        zoom_fit_action.triggered.connect(self._zoom_to_fit)
        toolbar.addAction(zoom_fit_action)

        search_label = QLabel("검색")
        search_label.setContentsMargins(12, 0, 4, 0)
        toolbar.addWidget(search_label)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("클래스/패키지 검색")
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self._update_search_matches)
        self.search_input.returnPressed.connect(self._find_next_match)
        toolbar.addWidget(self.search_input)
        search_action = QAction("찾기", self)
        search_action.triggered.connect(self._find_next_match)
        toolbar.addAction(search_action)

        focus_label = QLabel("포커스")
        focus_label.setContentsMargins(12, 0, 4, 0)
        toolbar.addWidget(focus_label)
        self.focus_box = QComboBox()
        focus_options = [
            ("전체", "all"),
            ("도메인만", "domain"),
            ("애플리케이션만", "application"),
            ("포트만", "ports"),
            ("어댑터만", "adapter"),
        ]
        for label, value in focus_options:
            self.focus_box.addItem(label, value)
        self.focus_box.currentIndexChanged.connect(self._apply_layer_focus)
        toolbar.addWidget(self.focus_box)

        self._apply_toolbar_styles(toolbar)
        self._init_menu()
        self._init_header_status(toolbar)

    def _init_docks(self) -> None:
        left_sidebar = LeftSidebar()
        self.filter_boxes = left_sidebar.filter_boxes
        for box in self.filter_boxes.values():
            box.stateChanged.connect(self._update_layer_filters)

        filter_dock = QDockWidget("범례/필터", self)
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

        inspector_dock = QDockWidget("인스펙터", self)
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
        rules_dock = QDockWidget("아키텍처 규칙", self)
        rules_dock.setWidget(self._wrap_scroll(self.rules_panel))
        rules_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        rules_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        rules_dock.setMinimumWidth(320)
        rules_dock.setMaximumWidth(420)
        rules_dock.setMinimumHeight(260)
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
        self.report_panel.use_case_box.currentIndexChanged.connect(
            self._on_report_use_case_changed
        )
        report_dock = QDockWidget("유스케이스 리포트", self)
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
        smells_dock = QDockWidget("DDD 스멜", self)
        smells_dock.setWidget(self._wrap_scroll(self.smells_panel))
        smells_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        smells_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        smells_dock.setMinimumWidth(320)
        smells_dock.setMaximumWidth(420)
        smells_dock.setMinimumHeight(260)
        smells_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.smells_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, smells_dock)
        self.tabifyDockWidget(inspector_dock, smells_dock)
        self._smells_dock = smells_dock

        self.readiness_panel = EventReadinessPanel()
        self.readiness_panel.use_case_selected.connect(self._on_readiness_use_case_selected)
        readiness_dock = QDockWidget("이벤트 드리븐 준비도", self)
        readiness_dock.setWidget(self._wrap_scroll(self.readiness_panel))
        readiness_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        readiness_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        readiness_dock.setMinimumWidth(320)
        readiness_dock.setMaximumWidth(420)
        readiness_dock.setMinimumHeight(260)
        readiness_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.readiness_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, readiness_dock)
        self.tabifyDockWidget(inspector_dock, readiness_dock)
        self._readiness_dock = readiness_dock

        self.context_panel = ContextMapInfoPanel()
        context_dock = QDockWidget("컨텍스트 맵 정보", self)
        context_dock.setWidget(self._wrap_scroll(self.context_panel))
        context_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        context_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        context_dock.setMinimumWidth(320)
        context_dock.setMaximumWidth(420)
        context_dock.setMinimumHeight(240)
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
        migration_dock = QDockWidget("마이그레이션 플래너", self)
        migration_dock.setWidget(self._wrap_scroll(self.migration_panel))
        migration_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        migration_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        migration_dock.setMinimumWidth(320)
        migration_dock.setMaximumWidth(420)
        migration_dock.setMinimumHeight(280)
        migration_dock.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.migration_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.addDockWidget(Qt.RightDockWidgetArea, migration_dock)
        self.tabifyDockWidget(inspector_dock, migration_dock)
        self._migration_dock = migration_dock

        self._setup_default_layout()

    def _init_menu(self) -> None:
        analyze_menu = self.menuBar().addMenu("분석")
        run_rules_action = QAction("아키텍처 규칙 검사 실행", self)
        run_rules_action.triggered.connect(self._run_rule_check)
        analyze_menu.addAction(run_rules_action)
        run_smells_action = QAction("DDD 스멜 탐지 실행", self)
        run_smells_action.triggered.connect(self._run_smell_analysis)
        analyze_menu.addAction(run_smells_action)
        readiness_action = QAction("이벤트 드리븐 준비도", self)
        readiness_action.triggered.connect(self._run_event_readiness)
        analyze_menu.addAction(readiness_action)

        view_menu = self.menuBar().addMenu("보기")
        hex_view_action = QAction("헥사곤 뷰", self)
        hex_view_action.triggered.connect(self._show_hex_view)
        context_map_action = QAction("컨텍스트 맵", self)
        context_map_action.triggered.connect(self._show_context_map)
        clear_bc_action = QAction("BC 필터 해제", self)
        clear_bc_action.triggered.connect(self._clear_bc_filter)
        view_menu.addAction(hex_view_action)
        view_menu.addAction(context_map_action)
        view_menu.addAction(clear_bc_action)
        view_menu.addSeparator()
        toggle_theme_action = QAction("다크 테마 전환", self)
        toggle_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme_action)
        reset_layout_action = QAction("레이아웃 초기화", self)
        reset_layout_action.triggered.connect(self._setup_default_layout)
        view_menu.addAction(reset_layout_action)

        file_menu = self.menuBar().addMenu("파일")
        export_md_action = QAction("마이그레이션 계획 내보내기 (마크다운)...", self)
        export_md_action.triggered.connect(self._export_migration_markdown)
        export_csv_action = QAction("마이그레이션 계획 내보내기 (CSV)...", self)
        export_csv_action.triggered.connect(self._export_migration_csv)
        export_plain_action = QAction("마이그레이션 계획 내보내기 (텍스트)...", self)
        export_plain_action.triggered.connect(self._export_migration_plain)
        file_menu.addAction(export_md_action)
        file_menu.addAction(export_csv_action)
        file_menu.addAction(export_plain_action)

    def _init_header_status(self, toolbar: QToolBar) -> None:
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(8)

        self._header_status = QLabel("분석 대기")
        self._header_status.setObjectName("toolbarStatusLabel")
        status_layout.addWidget(self._header_status)

        self._header_actions_container = QWidget()
        self._header_actions_layout = QHBoxLayout(self._header_actions_container)
        self._header_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._header_actions_layout.setSpacing(6)
        status_layout.addWidget(self._header_actions_container)

        toolbar.addSeparator()
        toolbar.addWidget(status_container)

    def _set_header_status(self, text: str, tone: str = "info") -> None:
        if not self._header_status:
            return
        self._header_status.setText(text)
        self._header_status.setProperty("tone", tone)
        self._header_status.style().unpolish(self._header_status)
        self._header_status.style().polish(self._header_status)
        self._header_status.update()

    def _reset_header_actions(self) -> None:
        if not self._header_actions_layout:
            return
        while self._header_actions_layout.count():
            item = self._header_actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_header_action(self, label: str, callback) -> None:
        if not self._header_actions_layout:
            return
        button = QToolButton()
        button.setText(label)
        button.setObjectName("toolbarActionButton")
        button.clicked.connect(callback)
        self._header_actions_layout.addWidget(button)

    def _open_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "프로젝트 루트 선택")
        if directory:
            self.project_root = Path(directory)
            self.inspector.set_base_path(self.project_root)
            self.statusBar().showMessage(f"프로젝트 선택됨: {self.project_root.name}", 2000)

    def _analyze_project(self) -> None:
        if not self.project_root:
            QMessageBox.warning(self, "프로젝트 필요", "먼저 프로젝트를 선택하세요.")
            return
        output_path = self.project_root / "architecture.json"
        self.statusBar().showMessage("분석 중...", 0)
        self._set_header_status("분석 실행 중", "busy")
        self._reset_header_actions()
        self._rules_done = False
        self._smells_done = False
        self._readiness_done = False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            graph = analyze_project(self.project_root, output_path)
        finally:
            QApplication.restoreOverrideCursor()
        self._load_graph(graph)
        self.statusBar().showMessage("분석 완료", 2000)
        self._update_header_status()

    def _open_graph(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "그래프 JSON 열기", "", "JSON 파일 (*.json)"
        )
        if not file_path:
            return
        self.statusBar().showMessage("그래프 불러오는 중...", 0)
        self._set_header_status("그래프 불러오는 중", "busy")
        self._reset_header_actions()
        path = Path(file_path)
        self.project_root = path.parent
        self.inspector.set_base_path(self.project_root)
        graph = load_graph(path)
        self._load_graph(graph)
        self.statusBar().showMessage("그래프 로딩 완료", 2000)
        self._update_header_status()

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
        if self.statusBar().currentMessage() != "그래프 로딩 완료":
            self.statusBar().showMessage("그래프 로딩 완료", 2000)
        self._update_header_status()
        if self._summary_report_action:
            self._summary_report_action.setEnabled(True)

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
        self._restore_focus_after_filter_change()

    def _apply_layer_focus(self) -> None:
        focus = self.focus_box.currentData() or "all"
        if focus == "all":
            self._set_focus_opacity({})
            self.statusBar().showMessage("전체 레이어", 1500)
            return

        if focus == "domain":
            self._set_focus_opacity({"domain"})
            self.statusBar().showMessage("도메인 포커스", 1500)
        elif focus == "application":
            self._set_focus_opacity({"application"})
            self.statusBar().showMessage("애플리케이션 포커스", 1500)
        elif focus == "ports":
            self._set_focus_opacity({"inbound_port", "outbound_port", "ports"})
            self.statusBar().showMessage("포트 포커스", 1500)
        elif focus == "adapter":
            self._set_focus_opacity({"inbound_adapter", "outbound_adapter", "adapter_zone"})
            self.statusBar().showMessage("어댑터 포커스", 1500)

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
        if self._inspector_dock:
            self._inspector_dock.raise_()
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
        self._soft_focus_component(step.component_id)

    def _export_use_case_report(self) -> None:
        if not self._use_case_reports:
            return
        current_id = self.report_panel.use_case_box.currentData()
        report = self._use_case_reports.reports.get(current_id) if current_id else None
        if not report:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "유스케이스 리포트 내보내기", "", "마크다운 (*.md)"
        )
        if not path:
            return
        Path(path).write_text(self.report_panel.markdown_text.toPlainText(), encoding="utf-8")

    def _export_use_case_summary_report(self) -> None:
        if not self._use_case_reports:
            QMessageBox.information(self, "보고서 생성", "유스케이스 분석 결과가 없습니다.")
            return
        default_name = "use_case_summary.md"
        if self.project_root:
            default_path = str(self.project_root / default_name)
        else:
            default_path = default_name
        path, _ = QFileDialog.getSaveFileName(
            self, "유스케이스 종합 보고서 저장", default_path, "마크다운 (*.md)"
        )
        if not path:
            return
        report_text = self._build_use_case_summary_markdown()
        Path(path).write_text(report_text, encoding="utf-8")
        self.statusBar().showMessage("유스케이스 종합 보고서를 저장했습니다.", 2000)

    def _build_use_case_summary_markdown(self) -> str:
        if not self._use_case_reports:
            return "# 유스케이스 종합 보고서\n\n분석 결과가 없습니다."

        report_lines = ["# 유스케이스 종합 보고서", ""]
        if self.project_root:
            report_lines.append(f"- 프로젝트: {self.project_root.name}")
        report_lines.append(f"- 유스케이스 수: {len(self._use_case_reports.reports)}")
        report_lines.append("")

        for report in self._use_case_reports.reports.values():
            report_lines.append(f"## {report.use_case_name}")
            entry_layer = self._report_layer_label(report.entry_layer)
            report_lines.append(f"- 진입: `{report.use_case_name}` ({entry_layer})")
            report_lines.append(f"- 흐름 단계 수: {len(report.flow_steps)}")
            report_lines.append("")

            report_lines.append("### 흐름 요약")
            report_lines.append(self._report_flow_summary_text(report.flow_steps))
            report_lines.append("")

            report_lines.append("### DDD 요약")
            report_lines.append(self._report_ddd_summary_text(report))
            report_lines.append("")

            report_lines.append("### 이벤트 요약")
            report_lines.append(self._report_event_summary_text(report))
            report_lines.append("")

            report_lines.append("### 컴포넌트 스멜")
            if not report.ddd_summary.smells:
                report_lines.append("- 없음")
            else:
                for smell in report.ddd_summary.smells:
                    severity_label = self._report_severity_label(smell.severity.value)
                    smell_label = self._report_smell_label(smell.smell_type.value)
                    report_lines.append(
                        f"- [{severity_label}] {smell_label}: {smell.component_name}"
                    )
            report_lines.append("")

            report_lines.append("### 리팩터링 제안")
            if not report.refactoring_suggestions:
                report_lines.append("- 없음")
            else:
                for suggestion in report.refactoring_suggestions:
                    report_lines.append(f"- {suggestion.title}")
                    report_lines.append(f"  - {suggestion.description}")
            report_lines.append("")

        return "\n".join(report_lines)

    def _report_flow_summary_text(self, steps: list) -> str:
        if not steps:
            return "-"
        names = [step.component_name for step in steps]
        return " → ".join(names[:6]) + (" ..." if len(names) > 6 else "")

    def _report_ddd_summary_text(self, report) -> str:
        summary = report.ddd_summary
        return "\n".join(
            [
                f"헥사곤 점수: {summary.hexagon_score:.2f}",
                f"규칙 위반: {summary.hexagon_rule_violations}",
                f"규칙 ID: {', '.join(summary.hexagon_rule_ids) or '-'}",
                f"빈약한 도메인: {'예' if summary.has_anemic_domain else '아니오'}",
                f"갓 서비스: {'예' if summary.has_god_service else '아니오'}",
                f"크로스 애그리게잇: {'예' if summary.has_cross_aggregate else '아니오'}",
            ]
        )

    def _report_event_summary_text(self, report) -> str:
        summary = report.event_summary
        lines = [
            f"준비도: {summary.readiness_score} ({self._report_readiness_label(summary.readiness_level)})",
            f"동기 결합도: {summary.sync_coupling_strength:.2f}",
        ]
        for suggestion in summary.main_suggestions[:3]:
            lines.append(f"- {suggestion.title}")
        return "\n".join(lines)

    def _report_readiness_label(self, level: str) -> str:
        value = level.lower()
        if value == "high":
            return "높음"
        if value == "medium":
            return "중간"
        if value == "low":
            return "낮음"
        return level

    def _report_layer_label(self, layer: str) -> str:
        labels = {
            "domain": "도메인",
            "application": "애플리케이션",
            "inbound_port": "인바운드 포트",
            "outbound_port": "아웃바운드 포트",
            "inbound_adapter": "인바운드 어댑터",
            "outbound_adapter": "아웃바운드 어댑터",
            "unknown": "미분류",
        }
        return labels.get(layer, layer)

    def _report_severity_label(self, severity: str) -> str:
        value = severity.lower()
        if value == "error":
            return "오류"
        if value == "warning":
            return "경고"
        if value == "info":
            return "정보"
        return severity

    def _report_smell_label(self, smell_type: str) -> str:
        labels = {
            "anemic_domain": "빈약한 도메인",
            "god_service": "갓 서비스",
            "repository_leak": "레포지토리 누수",
            "cross_aggregate_coupling": "크로스 애그리게잇",
        }
        return labels.get(smell_type, smell_type)

    def _run_rule_check(self) -> None:
        if not self._current_graph:
            return
        self._set_header_status("규칙 분석 중", "busy")
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
        self._rules_done = True
        self._update_header_status()

    def _run_smell_analysis(self) -> None:
        if not self._current_graph:
            return
        self._set_header_status("스멜 분석 중", "busy")
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
        self._smells_done = True
        self._update_header_status()

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
            self._suppress_report_focus = True
            self.report_panel.set_reports(self._use_case_reports)
            self._suppress_report_focus = False
        finally:
            self._building_reports = False

    def _load_target_spec(self) -> None:
        return

    def _load_target_spec_override(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "타깃 아키텍처 재지정", "", "JSON 파일 (*.json)"
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
            current_project_name=str(self.project_root) if self.project_root else "현재 프로젝트",
        )
        self.migration_panel.set_plan(self._migration_plan)
        self.migration_panel.set_status("마이그레이션 계획이 새로고침되었습니다.")

    def _export_migration_markdown(self) -> None:
        if not self._migration_plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "마이그레이션 계획 내보내기 (마크다운)", "", "마크다운 (*.md)"
        )
        if not path:
            return
        Path(path).write_text(render_migration_plan_markdown(self._migration_plan), encoding="utf-8")

    def _export_migration_csv(self) -> None:
        if not self._migration_plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "마이그레이션 계획 내보내기 (CSV)", "", "CSV (*.csv)"
        )
        if not path:
            return
        Path(path).write_text(render_migration_plan_csv(self._migration_plan), encoding="utf-8")

    def _export_migration_plain(self) -> None:
        if not self._migration_plan:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "마이그레이션 계획 내보내기 (텍스트)", "", "텍스트 (*.txt)"
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
                f"{target_path.name}에서 타깃을 불러왔습니다."
            )
            self._rebuild_migration_plan()
            return

        target_path = self.project_root / "ddd_target.json"
        self._generate_default_target_spec(target_path)
        self._load_target_spec_from_path(target_path)
        self._save_target_settings(target_path)
        self.migration_panel.set_status(
            "현재 분석 결과로 타깃이 자동 생성되었습니다."
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
                    "notes": "현재 분석 결과로 자동 생성됨",
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
            "name": "자동 생성 타깃",
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
        if self._context_dock:
            self._context_dock.raise_()

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

        if self._inspector_dock and self._rules_dock:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._rules_dock)
            self.splitDockWidget(self._inspector_dock, self._rules_dock, Qt.Orientation.Vertical)

        if self._report_dock and self._inspector_dock:
            self.tabifyDockWidget(self._inspector_dock, self._report_dock)

        analysis_docks = [
            self._smells_dock,
            self._readiness_dock,
            self._context_dock,
            self._migration_dock,
        ]
        for dock in analysis_docks:
            if dock and self._rules_dock:
                self.tabifyDockWidget(self._rules_dock, dock)

        if self._left_dock and self._inspector_dock:
            self.resizeDocks([self._left_dock], [260], Qt.Orientation.Horizontal)
            self.resizeDocks([self._inspector_dock], [360], Qt.Orientation.Horizontal)
        if self._inspector_dock and self._rules_dock:
            self.resizeDocks(
                [self._inspector_dock, self._rules_dock],
                [420, 320],
                Qt.Orientation.Vertical,
            )
        if self._inspector_dock:
            self._inspector_dock.raise_()

    def _show_component_smells(self, component_id: str) -> None:
        smells = self._smells_by_component.get(component_id, [])
        if not smells:
            self.inspector.clear_component_smells()
            return
        severity_labels = {
            "info": "정보",
            "warning": "경고",
            "error": "오류",
        }
        smell_labels = {
            "anemic_domain": "빈약한 도메인",
            "god_service": "갓 서비스",
            "repository_leak": "레포지토리 누수",
            "cross_aggregate_coupling": "크로스 애그리게잇",
        }
        items = [
            f"[{severity_labels.get(smell.severity.value, smell.severity.value)}] "
            f"{smell_labels.get(smell.smell_type.value, smell.smell_type.value)}: {smell.description}"
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
        if self._smells_dock:
            self._smells_dock.raise_()

    def _on_report_suggestion_selected(self, component_ids: list) -> None:
        if not component_ids:
            return
        self.scene.set_component_focus(set(component_ids))

    def _run_event_readiness(self) -> None:
        if not self._current_graph:
            return
        self._set_header_status("이벤트 준비도 분석 중", "busy")
        self._event_readiness = analyze_project_event_readiness(
            self._current_graph, self._violations_by_component
        )
        self.readiness_panel.show_results(self._event_readiness)
        if self._readiness_dock:
            self._readiness_dock.raise_()
        self._build_use_case_reports()
        self._readiness_done = True
        self._update_header_status()

    def _on_readiness_use_case_selected(self, component_id: str) -> None:
        if not self._current_graph:
            return
        self._soft_focus_component(component_id)
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
        if self._rules_dock:
            self._rules_dock.raise_()
        self._soft_focus_component(violation.source_component_id, center=False)

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
        severity_labels = {
            "info": "정보",
            "warning": "경고",
            "error": "오류",
        }
        items = [
            f"[{severity_labels.get(v.severity, v.severity)}] {v.rule_id}: {v.message}"
            for v in violations
        ]
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
            "domain": "도메인",
            "application": "앱",
            "inbound_port": "인포트",
            "outbound_port": "아웃포트",
            "inbound_adapter": "인어댑터",
            "outbound_adapter": "아웃어댑터",
            "unknown": "미분류",
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

    def _update_header_status(self) -> None:
        if not self._current_graph:
            self._set_header_status("분석 대기", "idle")
            self._reset_header_actions()
            return
        states = []
        if self._rules_done:
            states.append("규칙 ✓")
        if self._smells_done:
            states.append("스멜 ✓")
        if self._readiness_done:
            states.append("이벤트 ✓")
        if states:
            self._set_header_status("분석 완료 · " + " / ".join(states), "success")
            self._reset_header_actions()
            self._add_header_action("규칙 보기", self._show_rules_panel)
            self._add_header_action("스멜 보기", self._show_smells_panel)
            self._add_header_action("이벤트 보기", self._show_readiness_panel)
        else:
            self._set_header_status("그래프 로딩 완료", "info")

    def _show_rules_panel(self) -> None:
        if self._rules_dock:
            self._rules_dock.raise_()

    def _show_smells_panel(self) -> None:
        if self._smells_dock:
            self._smells_dock.raise_()

    def _show_readiness_panel(self) -> None:
        if self._readiness_dock:
            self._readiness_dock.raise_()

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

    def _soft_focus_component(self, component_id: str, center: bool = True) -> None:
        item = self.scene.component_items.get(component_id)
        if not item:
            return
        self.scene.set_active_component(component_id)
        self.inspector.show_component(item.component)
        item.flash(2)
        if center:
            self.view.centerOn(item)

    def _on_report_use_case_changed(self, index: int) -> None:
        if self._suppress_report_focus or not self._use_case_reports:
            return
        use_case_id = self.report_panel.use_case_box.itemData(index)
        if use_case_id:
            self._soft_focus_component(use_case_id)
            if self._report_dock:
                self._report_dock.raise_()

    def _restore_focus_after_filter_change(self) -> None:
        active_id = self.scene.active_component_id
        candidate_id = active_id or self._pending_focus_component_id
        if not candidate_id:
            return
        item = self.scene.component_items.get(candidate_id)
        if not item:
            return
        layer_key = item.component.layer
        layer_box = self.filter_boxes.get(layer_key)
        ports_visible = bool(
            (self.filter_boxes.get("inbound_port") and self.filter_boxes["inbound_port"].isChecked())
            or (self.filter_boxes.get("outbound_port") and self.filter_boxes["outbound_port"].isChecked())
        )
        if layer_key in {"inbound_port", "outbound_port"} and not ports_visible:
            self._pending_focus_component_id = candidate_id
            self.statusBar().showMessage("선택한 포트가 필터로 숨겨졌습니다.", 2000)
            return
        if layer_box and not layer_box.isChecked():
            self._pending_focus_component_id = candidate_id
            self.statusBar().showMessage("선택한 컴포넌트가 필터로 숨겨졌습니다.", 2000)
            return
        if self._pending_focus_component_id:
            self._soft_focus_component(self._pending_focus_component_id)
            self._pending_focus_component_id = None

    def _apply_toolbar_styles(self, toolbar: QToolBar) -> None:
        colors = self._get_theme_colors()
        toolbar.setStyleSheet(
            f"""
            QToolBar {{
                spacing: 10px;
                padding: 8px;
                background: {colors['surface']};
                border-bottom: 1px solid {colors['border']};
            }}
            QLineEdit {{
                padding: 7px 10px;
                border-radius: 10px;
                border: 1px solid {colors['border']};
                background: {colors['surface']};
                color: {colors['text']};
            }}
            QLineEdit:focus {{
                border-color: {colors['accent']};
            }}
            QComboBox {{
                padding: 7px 10px;
                border-radius: 10px;
                border: 1px solid {colors['border']};
                background: {colors['surface']};
                color: {colors['text']};
            }}
            QComboBox:focus {{
                border-color: {colors['accent']};
            }}
            QToolButton {{
                padding: 7px 12px;
                border-radius: 10px;
                background: {colors['surface_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
            }}
            QToolButton:hover {{
                background: {colors['accent_soft']};
                border-color: {colors['accent']};
            }}
            QLabel#toolbarGroupLabel {{
                color: {colors['text_muted']};
                font-size: 11px;
                font-weight: 600;
                padding: 0 4px;
            }}
            QLabel#toolbarStatusLabel {{
                padding: 4px 10px;
                border-radius: 10px;
                background: {colors['surface_alt']};
                color: {colors['text']};
                font-weight: 600;
            }}
            QLabel#toolbarStatusLabel[tone="busy"] {{
                background: {colors['accent_soft']};
                color: {colors['text']};
            }}
            QLabel#toolbarStatusLabel[tone="success"] {{
                background: {colors['accent_soft']};
                color: {colors['text']};
            }}
            QLabel#toolbarStatusLabel[tone="idle"] {{
                background: {colors['surface_alt']};
                color: {colors['text_muted']};
            }}
            QToolButton#toolbarActionButton {{
                padding: 6px 10px;
                border-radius: 10px;
                background: {colors['surface']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
            }}
            QToolButton#toolbarActionButton:hover {{
                background: {colors['accent_soft']};
                border-color: {colors['accent']};
            }}
            """
        )

    def start_watch(self, project_root: Path, interval_ms: int = 1000) -> None:
        self._watch_root = project_root
        if self._watch_timer is None:
            self._watch_timer = QTimer(self)
            self._watch_timer.setInterval(interval_ms)
            self._watch_timer.timeout.connect(self._poll_watch_changes)
        self._watch_snapshot = self._snapshot_project_files()
        self._watch_timer.start()
        self._set_header_status("파일 변경 감지 활성화", "info")

    def _poll_watch_changes(self) -> None:
        if self._watch_in_progress or not self._watch_root:
            return
        current = self._snapshot_project_files()
        if current == self._watch_snapshot:
            return
        self._watch_snapshot = current
        self._run_watch_analysis()

    def _run_watch_analysis(self) -> None:
        if not self._watch_root:
            return
        self._watch_in_progress = True
        output_path = self._watch_root / "architecture.json"
        self._set_header_status("파일 변경 감지 · 재분석 중", "busy")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            graph = analyze_project(self._watch_root, output_path)
        finally:
            QApplication.restoreOverrideCursor()
        self._load_graph(graph)
        self._set_header_status("재분석 완료", "success")
        self._watch_snapshot = self._snapshot_project_files()
        self._watch_in_progress = False

    def _snapshot_project_files(self) -> dict[str, float]:
        if not self._watch_root:
            return {}
        ignore_dirs = {
            ".git",
            ".venv",
            "__pycache__",
            ".ddd",
            "node_modules",
            "dist",
            "build",
            "target",
            ".idea",
        }
        ignore_files = {"architecture.json", ".DS_Store"}
        snapshot: dict[str, float] = {}
        for path in self._watch_root.rglob("*"):
            if not path.is_file():
                continue
            if path.name in ignore_files:
                continue
            if any(part in ignore_dirs for part in path.parts):
                continue
            try:
                snapshot[str(path)] = path.stat().st_mtime
            except OSError:
                continue
        return snapshot

    def _get_theme_colors(self) -> dict:
        from core.config import ThemeManager, Theme
        if ThemeManager.get_theme() == Theme.DARK:
            return {
                "background": "#12161C",
                "surface": "#1B222B",
                "surface_alt": "#232C37",
                "border": "#2B3642",
                "text": "#E6EDF5",
                "text_muted": "#A7B2C1",
                "accent": "#4B7CFF",
                "accent_soft": "#203358",
                "grid": "#1F2731",
                "grid_bold": "#2A3642",
            }
        return {
            "background": "#F2F4F6",
            "surface": "#FFFFFF",
            "surface_alt": "#F7F9FB",
            "border": "#D5DADF",
            "text": "#1F2937",
            "text_muted": "#556070",
            "accent": "#2156D8",
            "accent_soft": "#E6EEFF",
            "grid": "#E3E8EE",
            "grid_bold": "#D3DAE3",
        }

    def _build_grid_brush(self, colors: dict) -> QBrush:
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(colors["background"]))
        painter = QPainter(pixmap)
        painter.setPen(QPen(QColor(colors["grid"]), 1))
        step = 8
        for x in range(0, size, step):
            painter.drawLine(x, 0, x, size)
        for y in range(0, size, step):
            painter.drawLine(0, y, size, y)
        painter.setPen(QPen(QColor(colors["grid_bold"]), 1))
        for x in range(0, size, step * 4):
            painter.drawLine(x, 0, x, size)
        for y in range(0, size, step * 4):
            painter.drawLine(0, y, size, y)
        painter.end()
        return QBrush(pixmap)

    def _toggle_theme(self) -> None:
        from core.config import ThemeManager, Theme
        new_theme = ThemeManager.toggle_theme()
        self._apply_theme()
        theme_name = "다크" if new_theme == Theme.DARK else "라이트"
        self.statusBar().showMessage(f"{theme_name} 테마로 전환했습니다.", 2000)

    def _apply_theme(self) -> None:
        from core.config import ThemeManager, Theme
        colors = self._get_theme_colors()
        
        # 배경색 변경
        self.view.setBackgroundBrush(self._build_grid_brush(colors))
        self.view.apply_overlay_theme(ThemeManager.get_theme() == Theme.LIGHT)
        if self.minimap:
            self.minimap.apply_theme(ThemeManager.get_theme())
        
        # 툴바 스타일 업데이트
        for toolbar in self.findChildren(QToolBar):
            self._apply_toolbar_styles(toolbar)
        
        # 메인 윈도우 스타일시트
        self.setStyleSheet(f"""
            QMainWindow {{ background: {colors['background']}; }}
            QDockWidget {{
                background: {colors['surface']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
                titlebar-close-icon: url(none);
            }}
            QDockWidget::title {{
                background: {colors['surface']};
                padding: 10px 12px;
                font-family: 'Gmarket Sans';
                font-weight: 700;
                border-bottom: 1px solid {colors['border']};
            }}
            QDockWidget QWidget {{
                background: {colors['surface']};
                color: {colors['text']};
            }}
            QScrollArea {{
                border: none;
                background: {colors['surface']};
            }}
            QGroupBox {{
                border: 1px solid {colors['border']};
                border-radius: 10px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: {colors['text_muted']};
            }}
            QMenuBar {{
                background: {colors['surface']};
                color: {colors['text']};
            }}
            QMenuBar::item:selected {{ background: {colors['accent_soft']}; }}
            QMenu {{
                background: {colors['surface']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
            }}
            QMenu::item:selected {{ background: {colors['accent_soft']}; }}
            QStatusBar {{
                background: {colors['surface']};
                color: {colors['text_muted']};
            }}
            QListWidget, QTableWidget, QTextEdit, QTreeWidget {{
                background: {colors['surface_alt']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QTableWidget {{
                gridline-color: {colors['border']};
                alternate-background-color: {colors['surface']};
            }}
            QTableWidget::item, QListWidget::item, QTreeWidget::item {{
                padding: 6px 8px;
            }}
            QTableWidget::item:selected, QListWidget::item:selected, QTreeWidget::item:selected {{
                background: {colors['accent_soft']};
                color: {colors['text']};
            }}
            QHeaderView::section {{
                background: {colors['surface']};
                color: {colors['text_muted']};
                border: 1px solid {colors['border']};
                padding: 6px 8px;
                font-weight: 600;
            }}
            QPushButton {{
                background: {colors['accent']};
                color: white;
                border-radius: 8px;
                padding: 7px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {colors['accent']};
                opacity: 0.9;
            }}
            QPushButton:disabled {{
                background: {colors['border']};
                color: {colors['text_muted']};
            }}
        """)

    def _show_onboarding(self) -> None:
        """Show onboarding overlay for first-time users"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("DDD Architecture Viewer 시작하기")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        
        # Welcome header
        header = QLabel("🏗️ DDD Architecture Viewer에 오신 것을 환영합니다!")
        header.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-size: 20px; font-weight: bold; padding: 16px;"
        )
        layout.addWidget(header)
        
        # Tips
        tips = [
            "📂 <b>프로젝트 열기</b>: '프로젝트 열기...'를 눌러 Java/Spring 프로젝트를 선택합니다.",
            "🔍 <b>분석</b>: '분석'을 눌러 아키텍처를 스캔하고 시각화합니다.",
            "🖱️ <b>탐색</b>: 스크롤로 줌, 우클릭 드래그로 패닝, 노드 드래그로 재배치합니다.",
            "🎯 <b>포커스</b>: 컴포넌트를 클릭하면 인스펙터에서 상세를 확인할 수 있습니다.",
            "🌙 <b>다크 모드</b>: 보기 → 다크 테마 전환에서 변경합니다.",
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
        
        close_btn = QPushButton("시작하기")
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
