from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QHeaderView,
    QSizePolicy,
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
        self.score_label = QLabel("헥사곤 순도 점수: -")
        self.summary_label = QLabel("규칙 위반: -")
        self.counts_label = QLabel("컴포넌트: - | 의존성: -")

        self.rule_table = QTableWidget(0, 3)
        self.rule_table.setHorizontalHeaderLabels(["규칙", "심각도", "건수"])
        header = self.rule_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.rule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rule_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.rule_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.rule_table.setAlternatingRowColors(True)
        self.rule_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.violation_list = QListWidget()
        self.violation_list.setAlternatingRowColors(True)
        self.violation_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.violation_list.setWordWrap(True)
        self.violation_list.itemClicked.connect(self._on_violation_clicked)

        def _section_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
            )
            return label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.score_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.counts_label)
        layout.addWidget(_section_label("규칙"))
        layout.addWidget(self.rule_table)
        layout.addWidget(_section_label("규칙 위반"))
        layout.addWidget(self.violation_list)

        self.setStyleSheet("QLabel { font-size: 12px; }")

    def show_results(self, summary: RuleAnalysisSummary, violations: list[RuleViolation]) -> None:
        self._violations = violations
        self.score_label.setText(f"헥사곤 순도 점수: {summary.score} / 100")
        self.summary_label.setText(
            f"규칙 위반: {summary.total_violations}"
        )
        self.counts_label.setText(
            f"컴포넌트: {summary.total_components} | 의존성: {summary.total_dependencies}"
        )

        self.rule_table.setRowCount(0)
        if summary.violations_by_rule:
            for rule_id, count in summary.violations_by_rule.items():
                row = self.rule_table.rowCount()
                self.rule_table.insertRow(row)
                self.rule_table.setItem(row, 0, QTableWidgetItem(rule_id))
                severity = _severity_for_rule(rule_id, violations)
                severity_item = QTableWidgetItem(_severity_label(severity))
                severity_item.setForeground(QBrush(_severity_color(severity)))
                self.rule_table.setItem(row, 1, severity_item)
                self.rule_table.setItem(row, 2, QTableWidgetItem(str(count)))
        else:
            self.rule_table.setRowCount(1)
            self.rule_table.setItem(0, 0, QTableWidgetItem("규칙 위반 없음"))
            self.rule_table.setItem(0, 1, QTableWidgetItem("-"))
            self.rule_table.setItem(0, 2, QTableWidgetItem("0"))

        self.violation_list.clear()
        if violations:
            for violation in violations:
                severity_label = _severity_label(violation.severity)
                source_label = _layer_label(violation.source_layer.value)
                target_label = (
                    _layer_label(violation.target_layer.value)
                    if violation.target_layer
                    else "없음"
                )
                label = (
                    f"[{severity_label}] {source_label} → {target_label}: "
                    f"{violation.message}"
                )
                self.violation_list.addItem(QListWidgetItem(label))
        else:
            self.violation_list.addItem(QListWidgetItem("규칙 위반 없음"))

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


def _severity_color(severity: str) -> QColor:
    value = severity.lower()
    if value == "error":
        return QColor("#DC2626")
    if value == "warning":
        return QColor("#F59E0B")
    return QColor("#2563EB")


def _severity_label(severity: str) -> str:
    value = severity.lower()
    if value == "error":
        return "오류"
    if value == "warning":
        return "경고"
    if value == "info":
        return "정보"
    return severity


def _layer_label(layer: str) -> str:
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
