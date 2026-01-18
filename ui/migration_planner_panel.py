from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QHeaderView,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analysis.migration_planner import MigrationItem, MigrationPlan


class MigrationPlannerPanel(QWidget):
    override_target_requested = Signal()
    refresh_requested = Signal()
    export_markdown_requested = Signal()
    export_csv_requested = Signal()
    export_plain_requested = Signal()
    item_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._plan: MigrationPlan | None = None

        self.target_label = QLabel("타깃: -")
        self.load_button = QPushButton("타깃 재지정...")
        self.rebuild_button = QPushButton("계획 새로고침")
        self.status_label = QLabel("-")
        self.export_md_button = QPushButton("마크다운 내보내기")
        self.export_csv_button = QPushButton("CSV 내보내기")
        self.export_plain_button = QPushButton("텍스트 내보내기")

        self.load_button.clicked.connect(self.override_target_requested.emit)
        self.rebuild_button.clicked.connect(self.refresh_requested.emit)
        self.export_md_button.clicked.connect(self.export_markdown_requested.emit)
        self.export_csv_button.clicked.connect(self.export_csv_requested.emit)
        self.export_plain_button.clicked.connect(self.export_plain_requested.emit)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["우선순위", "유형", "제목", "유스케이스", "BC"])
        self.tree.itemSelectionChanged.connect(self._on_item_selected)
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

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

        def _section_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
            )
            return label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addLayout(top_row)
        layout.addWidget(self.status_label)
        layout.addLayout(export_row)
        layout.addWidget(self.tree)
        layout.addWidget(_section_label("선택 항목"))
        layout.addWidget(self.detail_title)
        layout.addWidget(self.detail_desc)
        layout.addWidget(self.detail_reason)

        self.setStyleSheet("QLabel { font-size: 12px; }")

    def set_target_name(self, name: str) -> None:
        self.target_label.setText(f"타깃: {name}")

    def set_plan(self, plan: MigrationPlan) -> None:
        self._plan = plan
        self.tree.clear()
        if not plan.phases:
            self.tree.setHeaderLabels(["우선순위", "유형", "제목", "유스케이스", "BC"])
            empty_item = QTreeWidgetItem(["", "", "마이그레이션 계획 없음", "", ""])
            empty_item.setFirstColumnSpanned(True)
            self.tree.addTopLevelItem(empty_item)
            self.set_status("마이그레이션 계획이 없습니다.")
            return
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

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

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
        self.detail_reason.setText(f"근거: {data.rationale}")
        self.item_selected.emit(data)
