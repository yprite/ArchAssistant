from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analysis.migration_planner import MigrationItem, MigrationPlan


class MigrationPlannerPanel(QWidget):
    load_target_requested = Signal()
    rebuild_requested = Signal()
    export_markdown_requested = Signal()
    export_csv_requested = Signal()
    export_plain_requested = Signal()
    item_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._plan: MigrationPlan | None = None

        self.target_label = QLabel("Target: -")
        self.load_button = QPushButton("Load Target...")
        self.rebuild_button = QPushButton("Rebuild Plan")
        self.export_md_button = QPushButton("Export Markdown")
        self.export_csv_button = QPushButton("Export CSV")
        self.export_plain_button = QPushButton("Export Plain")

        self.load_button.clicked.connect(self.load_target_requested.emit)
        self.rebuild_button.clicked.connect(self.rebuild_requested.emit)
        self.export_md_button.clicked.connect(self.export_markdown_requested.emit)
        self.export_csv_button.clicked.connect(self.export_csv_requested.emit)
        self.export_plain_button.clicked.connect(self.export_plain_requested.emit)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Priority", "Type", "Title", "Use Cases", "BC"])
        self.tree.itemSelectionChanged.connect(self._on_item_selected)

        self.detail_title = QLabel("-")
        self.detail_desc = QLabel("-")
        self.detail_desc.setWordWrap(True)
        self.detail_reason = QLabel("-")
        self.detail_reason.setWordWrap(True)

        top_row = QHBoxLayout()
        top_row.addWidget(self.target_label)
        top_row.addStretch(1)
        top_row.addWidget(self.load_button)
        top_row.addWidget(self.rebuild_button)

        export_row = QHBoxLayout()
        export_row.addWidget(self.export_md_button)
        export_row.addWidget(self.export_csv_button)
        export_row.addWidget(self.export_plain_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addLayout(top_row)
        layout.addLayout(export_row)
        layout.addWidget(self.tree)
        layout.addWidget(QLabel("Selected Item"))
        layout.addWidget(self.detail_title)
        layout.addWidget(self.detail_desc)
        layout.addWidget(self.detail_reason)

        self.setStyleSheet("QLabel { font-size: 12px; color: #333333; }")

    def set_target_name(self, name: str) -> None:
        self.target_label.setText(f"Target: {name}")

    def set_plan(self, plan: MigrationPlan) -> None:
        self._plan = plan
        self.tree.clear()
        for phase in plan.phases:
            phase_item = QTreeWidgetItem(
                ["", "", phase.name, "", ""]
            )
            phase_item.setFirstColumnSpanned(True)
            self.tree.addTopLevelItem(phase_item)
            for item in phase.items:
                child = QTreeWidgetItem(
                    [
                        item.priority.value,
                        item.item_type.value,
                        item.title,
                        ";".join(item.related_use_cases),
                        ";".join(item.related_bc_ids),
                    ]
                )
                child.setData(0, 256, item)
                phase_item.addChild(child)
            phase_item.setExpanded(True)

    def _on_item_selected(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, 256)
        if not isinstance(data, MigrationItem):
            return
        self.detail_title.setText(f"{data.title} ({data.priority.value})")
        self.detail_desc.setText(data.description)
        self.detail_reason.setText(f"Rationale: {data.rationale}")
        self.item_selected.emit(data)
