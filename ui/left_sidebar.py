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
        self.tabs.addTab(self.filters_panel, "Filters")
        self.tabs.addTab(self.legend_panel, "Legend")
        self.tabs.addTab(self.help_panel, "Inspector Help")

        self.setLayout(self._build_layout())

    @property
    def filter_boxes(self):
        return self.filters_panel.filter_boxes

    def _build_layout(self):
        from PySide6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
        return layout
