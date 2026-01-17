from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from architecture.rules import RuleAnalysisSummary, RuleViolation


class ArchitectureRulesPanel(QWidget):
    violation_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._violations: list[RuleViolation] = []
        self.score_label = QLabel("Hexagon Purity Score: -")
        self.summary_label = QLabel("Violations: -")
        self.counts_label = QLabel("Components: - | Dependencies: -")

        self.rule_table = QTableWidget(0, 3)
        self.rule_table.setHorizontalHeaderLabels(["Rule", "Severity", "Count"])
        self.rule_table.horizontalHeader().setStretchLastSection(True)
        self.rule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rule_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.violation_list = QListWidget()
        self.violation_list.itemClicked.connect(self._on_violation_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.score_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.counts_label)
        layout.addWidget(QLabel("Rules"))
        layout.addWidget(self.rule_table)
        layout.addWidget(QLabel("Violations"))
        layout.addWidget(self.violation_list)

        self.setStyleSheet("QLabel { font-size: 12px; color: #333333; }")

    def show_results(self, summary: RuleAnalysisSummary, violations: list[RuleViolation]) -> None:
        self._violations = violations
        self.score_label.setText(f"Hexagon Purity Score: {summary.score} / 100")
        self.summary_label.setText(
            f"Violations: {summary.total_violations}"
        )
        self.counts_label.setText(
            f"Components: {summary.total_components} | Dependencies: {summary.total_dependencies}"
        )

        self.rule_table.setRowCount(0)
        for rule_id, count in summary.violations_by_rule.items():
            row = self.rule_table.rowCount()
            self.rule_table.insertRow(row)
            self.rule_table.setItem(row, 0, QTableWidgetItem(rule_id))
            severity = _severity_for_rule(rule_id, violations)
            self.rule_table.setItem(row, 1, QTableWidgetItem(severity))
            self.rule_table.setItem(row, 2, QTableWidgetItem(str(count)))

        self.violation_list.clear()
        for violation in violations:
            label = (
                f"[{violation.severity.upper()}] {violation.source_layer.value} → "
                f"{violation.target_layer.value if violation.target_layer else 'n/a'}: "
                f"{violation.message}"
            )
            self.violation_list.addItem(QListWidgetItem(label))

    def _on_violation_clicked(self, item: QListWidgetItem) -> None:
        index = self.violation_list.currentRow()
        if index < 0 or index >= len(self._violations):
            return
        self.violation_selected.emit(self._violations[index])


def _severity_for_rule(rule_id: str, violations: list[RuleViolation]) -> str:
    for violation in violations:
        if violation.rule_id == rule_id:
            return violation.severity
    return "-"
