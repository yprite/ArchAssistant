from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget

from ui.filters_panel import FiltersPanel
from ui.legend_panel import LegendPanel
from ui.inspector_help_panel import InspectorHelpPanel


class LeftSidebar(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.tabs = QTabWidget()
        self.filters_panel = FiltersPanel()
        self.legend_panel = LegendPanel()
        self.help_panel = InspectorHelpPanel()
        self.tabs.addTab(self.filters_panel, "필터")
        self.tabs.addTab(self.legend_panel, "범례")
        self.tabs.addTab(self.help_panel, "인스펙터 도움말")

        self.setLayout(self._build_layout())
        self._apply_styles()

    @property
    def filter_boxes(self):
        return self.filters_panel.filter_boxes

    def _build_layout(self):
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
        return layout

    def _apply_styles(self) -> None:
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 0; }"
            "QTabBar::tab { padding: 8px 14px; margin-right: 6px; border-radius: 10px;"
            " font-family: 'Gmarket Sans'; font-weight: 600; }"
            "QTabBar::tab:selected { background: palette(light); }"
        )
