from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
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

from analysis.smells import ComponentSmell, ProjectSmellSummary, SmellType


class SmellsPanel(QWidget):
    smell_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._smells: list[ComponentSmell] = []
        self.summary_label = QLabel("스멜: -")
        self.ratios_label = QLabel("빈약한 도메인: - | 갓 서비스: - | 레포 누수: - | 크로스 애그: -")

        self.smell_table = QTableWidget(0, 5)
        self.smell_table.setHorizontalHeaderLabels(
            ["유형", "심각도", "컴포넌트", "레이어", "핵심 지표"]
        )
        header = self.smell_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.smell_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.smell_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.smell_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.smell_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.smell_table.setAlternatingRowColors(True)
        self.smell_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.detail_list = QListWidget()
        self.detail_list.setAlternatingRowColors(True)
        self.detail_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.detail_list.setWordWrap(True)
        self.detail_list.itemClicked.connect(self._on_item_clicked)

        def _section_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
            )
            return label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(_section_label("DDD 스멜"))
        layout.addWidget(self.summary_label)
        layout.addWidget(self.ratios_label)
        layout.addWidget(self.smell_table)
        layout.addWidget(_section_label("상세"))
        layout.addWidget(self.detail_list)

        self.setStyleSheet("QLabel { font-size: 12px; }")

    def show_results(self, summary: ProjectSmellSummary) -> None:
        self._smells = summary.smells
        self.summary_label.setText(
            f"스멜: {len(summary.smells)} | 레이어: {len(summary.smells_by_layer)}"
        )
        self.ratios_label.setText(
            "빈약한 도메인: "
            f"{summary.anemic_domain_ratio:.0%} | "
            "갓 서비스: "
            f"{summary.god_service_ratio:.0%} | "
            "레포 누수: "
            f"{summary.repository_leak_ratio:.0%} | "
            "크로스 애그: "
            f"{summary.cross_aggregate_coupling_ratio:.0%}"
        )

        self.smell_table.setRowCount(0)
        if summary.smells:
            for smell in summary.smells:
                row = self.smell_table.rowCount()
                self.smell_table.insertRow(row)
                self.smell_table.setItem(row, 0, QTableWidgetItem(_smell_label(smell.smell_type.value)))
                severity_value = smell.severity.value
                severity_item = QTableWidgetItem(_severity_label(severity_value))
                severity_item.setForeground(QBrush(_severity_color(severity_value)))
                self.smell_table.setItem(row, 1, severity_item)
                self.smell_table.setItem(row, 2, QTableWidgetItem(smell.component_name))
                self.smell_table.setItem(row, 3, QTableWidgetItem(_layer_label(smell.layer)))
                metrics = ", ".join(
                    f"{key}:{value:.0f}" for key, value in smell.metrics.items() if value
                )
                self.smell_table.setItem(row, 4, QTableWidgetItem(metrics or "-"))
        else:
            self.smell_table.setRowCount(1)
            self.smell_table.setItem(0, 0, QTableWidgetItem("스멜 없음"))
            self.smell_table.setItem(0, 1, QTableWidgetItem("-"))
            self.smell_table.setItem(0, 2, QTableWidgetItem("-"))
            self.smell_table.setItem(0, 3, QTableWidgetItem("-"))
            self.smell_table.setItem(0, 4, QTableWidgetItem("-"))

        self.detail_list.clear()
        if not summary.smells:
            self.detail_list.addItem(QListWidgetItem("스멜 없음"))

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
        severity_label = _severity_label(smell.severity.value)
        self.detail_list.addItem(QListWidgetItem(f"[{severity_label}] {smell.description}"))
        for hint in smell.hints:
            self.detail_list.addItem(QListWidgetItem(f"힌트: {hint}"))


def smell_color_key(smell_type: SmellType) -> str:
    return smell_type.value


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


def _smell_label(smell_type: str) -> str:
    labels = {
        "anemic_domain": "빈약한 도메인",
        "god_service": "갓 서비스",
        "repository_leak": "레포지토리 누수",
        "cross_aggregate_coupling": "크로스 애그리게잇",
    }
    return labels.get(smell_type, smell_type)
