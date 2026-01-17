from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analysis.smells import ComponentSmell, ProjectSmellSummary, SmellType


class SmellsPanel(QWidget):
    smell_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._smells: list[ComponentSmell] = []
        self.summary_label = QLabel("Smells: -")
        self.ratios_label = QLabel("Anemic: - | God: - | RepoLeak: - | CrossAgg: -")

        self.smell_table = QTableWidget(0, 5)
        self.smell_table.setHorizontalHeaderLabels(
            ["Type", "Severity", "Component", "Layer", "Key Metrics"]
        )
        self.smell_table.horizontalHeader().setStretchLastSection(True)
        self.smell_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.smell_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.smell_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.smell_table.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail_list = QListWidget()
        self.detail_list.itemClicked.connect(self._on_item_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel("DDD Smells"))
        layout.addWidget(self.summary_label)
        layout.addWidget(self.ratios_label)
        layout.addWidget(self.smell_table)
        layout.addWidget(QLabel("Details"))
        layout.addWidget(self.detail_list)

        self.setStyleSheet("QLabel { font-size: 12px; color: #333333; }")

    def show_results(self, summary: ProjectSmellSummary) -> None:
        self._smells = summary.smells
        self.summary_label.setText(
            f"Smells: {len(summary.smells)} | Layers: {len(summary.smells_by_layer)}"
        )
        self.ratios_label.setText(
            "Anemic: "
            f"{summary.anemic_domain_ratio:.0%} | "
            "God: "
            f"{summary.god_service_ratio:.0%} | "
            "RepoLeak: "
            f"{summary.repository_leak_ratio:.0%} | "
            "CrossAgg: "
            f"{summary.cross_aggregate_coupling_ratio:.0%}"
        )

        self.smell_table.setRowCount(0)
        for smell in summary.smells:
            row = self.smell_table.rowCount()
            self.smell_table.insertRow(row)
            self.smell_table.setItem(row, 0, QTableWidgetItem(smell.smell_type.value))
            self.smell_table.setItem(row, 1, QTableWidgetItem(smell.severity.value))
            self.smell_table.setItem(row, 2, QTableWidgetItem(smell.component_name))
            self.smell_table.setItem(row, 3, QTableWidgetItem(smell.layer))
            metrics = ", ".join(
                f"{key}:{value:.0f}" for key, value in smell.metrics.items() if value
            )
            self.smell_table.setItem(row, 4, QTableWidgetItem(metrics or "-"))

        self.detail_list.clear()
        if not summary.smells:
            self.detail_list.addItem(QListWidgetItem("No smells detected"))

    def _on_selection_changed(self) -> None:
        row = self.smell_table.currentRow()
        if row < 0 or row >= len(self._smells):
            return
        smell = self._smells[row]
        self._populate_details(smell)
        self.smell_selected.emit(smell)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        index = self.smell_table.currentRow()
        if index < 0 or index >= len(self._smells):
            return
        self.smell_selected.emit(self._smells[index])

    def _populate_details(self, smell: ComponentSmell) -> None:
        self.detail_list.clear()
        self.detail_list.addItem(QListWidgetItem(f"[{smell.severity.value}] {smell.description}"))
        for hint in smell.hints:
            self.detail_list.addItem(QListWidgetItem(f"Hint: {hint}"))


def smell_color_key(smell_type: SmellType) -> str:
    return smell_type.value
