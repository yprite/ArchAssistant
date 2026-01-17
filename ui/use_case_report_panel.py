from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analysis.use_case_report import UseCaseReport, UseCaseReportSet


class UseCaseReportPanel(QWidget):
    step_selected = Signal(int)
    export_requested = Signal()
    suggestion_selected = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self._report_set: UseCaseReportSet | None = None
        self._current_report: UseCaseReport | None = None
        self.title_label = QLabel("Use Case Report")
        self.title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.use_case_box = QComboBox()
        self.use_case_box.currentIndexChanged.connect(self._on_use_case_changed)
        self.summary_label = QLabel("-")
        self.flow_summary = QLabel("-")
        self.ddd_text = QTextEdit()
        self.ddd_text.setReadOnly(True)
        self.ddd_text.setFixedHeight(140)
        self.component_smells_list = QListWidget()
        self.component_smells_list.setFixedHeight(120)
        self.steps_list = QListWidget()
        self.steps_list.setFixedHeight(180)
        self.steps_list.itemClicked.connect(self._on_step_clicked)
        self.event_text = QTextEdit()
        self.event_text.setReadOnly(True)
        self.event_text.setFixedHeight(120)
        self.bc_text = QLabel("-")
        self.refactor_list = QListWidget()
        self.refactor_list.setFixedHeight(140)
        self.refactor_list.itemClicked.connect(self._on_suggestion_clicked)
        self.markdown_text = QTextEdit()
        self.markdown_text.setReadOnly(True)
        self.export_button = QPushButton("Export Markdown")
        self.export_button.clicked.connect(self.export_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.use_case_box)
        layout.addWidget(self.summary_label)
        layout.addWidget(QLabel("Flow Summary"))
        layout.addWidget(self.flow_summary)
        layout.addWidget(QLabel("DDD Summary"))
        layout.addWidget(self.ddd_text)
        layout.addWidget(QLabel("Component Smells"))
        layout.addWidget(self.component_smells_list)
        layout.addWidget(QLabel("Flow Steps"))
        layout.addWidget(self.steps_list)
        layout.addWidget(QLabel("Event Summary"))
        layout.addWidget(self.event_text)
        layout.addWidget(QLabel("Bounded Context"))
        layout.addWidget(self.bc_text)
        layout.addWidget(QLabel("Refactoring Suggestions"))
        layout.addWidget(self.refactor_list)
        layout.addWidget(QLabel("Markdown"))
        layout.addWidget(self.markdown_text)
        layout.addWidget(self.export_button)

        self.setStyleSheet("QLabel { font-size: 12px; color: #333333; }")

    def set_reports(self, report_set: UseCaseReportSet) -> None:
        self._report_set = report_set
        self.use_case_box.blockSignals(True)
        self.use_case_box.clear()
        for report in report_set.reports.values():
            self.use_case_box.addItem(report.use_case_name, report.use_case_id)
        self.use_case_box.blockSignals(False)
        if self.use_case_box.count() > 0:
            self.use_case_box.setCurrentIndex(0)

    def select_use_case(self, use_case_id: str) -> None:
        if not self._report_set:
            return
        for idx in range(self.use_case_box.count()):
            if self.use_case_box.itemData(idx) == use_case_id:
                self.use_case_box.setCurrentIndex(idx)
                return

    def show_report(self, report: UseCaseReport) -> None:
        self._current_report = report
        self.summary_label.setText(
            f"Entry: {report.use_case_name} ({report.entry_layer}) | Steps: {len(report.flow_steps)}"
        )
        self.flow_summary.setText(_flow_summary_text(report.flow_steps))
        self.ddd_text.setPlainText(_ddd_summary_text(report))
        self.event_text.setPlainText(_event_summary_text(report))
        self.bc_text.setText(
            f"{report.bc_summary.entry_bc_name} | {report.bc_summary.notes}"
        )
        self.component_smells_list.clear()
        if not report.ddd_summary.smells:
            self.component_smells_list.addItem(QListWidgetItem("No smells detected"))
        else:
            for smell in report.ddd_summary.smells:
                self.component_smells_list.addItem(
                    QListWidgetItem(
                        f"[{smell.severity.value}] {smell.smell_type.value}: {smell.component_name}"
                    )
                )
        self.steps_list.clear()
        for step in report.flow_steps:
            self.steps_list.addItem(
                QListWidgetItem(
                    f"{step.index + 1}. {step.component_name} ({step.layer})"
                )
            )
        self.refactor_list.clear()
        if not report.refactoring_suggestions:
            self.refactor_list.addItem(QListWidgetItem("No suggestions"))
        else:
            for suggestion in report.refactoring_suggestions:
                self.refactor_list.addItem(QListWidgetItem(suggestion.title))
        self.markdown_text.setPlainText(_report_markdown(report))

    def _on_step_clicked(self, item: QListWidgetItem) -> None:
        row = self.steps_list.currentRow()
        if row < 0:
            return
        self.step_selected.emit(row)

    def _on_use_case_changed(self, index: int) -> None:
        if not self._report_set or index < 0:
            return
        use_case_id = self.use_case_box.itemData(index)
        report = self._report_set.reports.get(use_case_id)
        if report:
            self.show_report(report)

    def _on_suggestion_clicked(self, item: QListWidgetItem) -> None:
        if not self._current_report:
            return
        row = self.refactor_list.currentRow()
        if row < 0 or row >= len(self._current_report.refactoring_suggestions):
            return
        suggestion = self._current_report.refactoring_suggestions[row]
        self.suggestion_selected.emit(suggestion.related_components)


def _flow_summary_text(steps: list) -> str:
    if not steps:
        return "-"
    names = [step.component_name for step in steps]
    return " → ".join(names[:6]) + (" ..." if len(names) > 6 else "")


def _ddd_summary_text(report: UseCaseReport) -> str:
    summary = report.ddd_summary
    return "\n".join(
        [
            f"Hexagon score: {summary.hexagon_score:.2f}",
            f"Rule violations: {summary.hexagon_rule_violations}",
            f"Rule IDs: {', '.join(summary.hexagon_rule_ids) or '-'}",
            f"Anemic Domain: {'Yes' if summary.has_anemic_domain else 'No'}",
            f"God Service: {'Yes' if summary.has_god_service else 'No'}",
            f"Cross Aggregate: {'Yes' if summary.has_cross_aggregate else 'No'}",
        ]
    )


def _event_summary_text(report: UseCaseReport) -> str:
    summary = report.event_summary
    lines = [
        f"Readiness: {summary.readiness_score} ({summary.readiness_level})",
        f"Sync coupling: {summary.sync_coupling_strength:.2f}",
    ]
    for suggestion in summary.main_suggestions[:3]:
        lines.append(f"- {suggestion.title}")
    return "\n".join(lines)


def _report_markdown(report: UseCaseReport) -> str:
    lines = [
        f"# Use Case Report: {report.use_case_name}",
        "",
        f"- Entry: `{report.use_case_name}` ({report.entry_layer})",
        f"- Flow steps: {len(report.flow_steps)}",
        "",
        "## DDD Summary",
        _ddd_summary_text(report),
        "",
        "## Event Summary",
        _event_summary_text(report),
        "",
        "## Bounded Context",
        f"- Entry BC: {report.bc_summary.entry_bc_name}",
        f"- Notes: {report.bc_summary.notes}",
        "",
        "## Refactoring Suggestions",
    ]
    if not report.refactoring_suggestions:
        lines.append("- None")
    else:
        for suggestion in report.refactoring_suggestions:
            lines.append(f"- {suggestion.title}")
            lines.append(f"  - {suggestion.description}")
    return "\n".join(lines)
