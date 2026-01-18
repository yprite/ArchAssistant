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
        self.title_label = QLabel("유스케이스 리포트")
        self.title_label.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 700; font-size: 14px;"
        )
        self.use_case_box = QComboBox()
        self.use_case_box.currentIndexChanged.connect(self._on_use_case_changed)
        self.summary_label = QLabel("-")
        self.flow_summary = QLabel("-")
        self.ddd_text = QTextEdit()
        self.ddd_text.setReadOnly(True)
        self.ddd_text.setFixedHeight(140)
        self.component_smells_list = QListWidget()
        self.component_smells_list.setFixedHeight(120)
        self.component_smells_list.setAlternatingRowColors(True)
        self.component_smells_list.setWordWrap(True)
        self.steps_list = QListWidget()
        self.steps_list.setFixedHeight(180)
        self.steps_list.itemClicked.connect(self._on_step_clicked)
        self.steps_list.setAlternatingRowColors(True)
        self.steps_list.setWordWrap(True)
        self.event_text = QTextEdit()
        self.event_text.setReadOnly(True)
        self.event_text.setFixedHeight(120)
        self.bc_text = QLabel("-")
        self.refactor_list = QListWidget()
        self.refactor_list.setFixedHeight(140)
        self.refactor_list.itemClicked.connect(self._on_suggestion_clicked)
        self.refactor_list.setAlternatingRowColors(True)
        self.refactor_list.setWordWrap(True)
        self.markdown_text = QTextEdit()
        self.markdown_text.setReadOnly(True)
        self.export_button = QPushButton("마크다운 내보내기")
        self.export_button.clicked.connect(self.export_requested.emit)

        def _section_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
            )
            return label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.use_case_box)
        layout.addWidget(self.summary_label)
        layout.addWidget(_section_label("흐름 요약"))
        layout.addWidget(self.flow_summary)
        layout.addWidget(_section_label("DDD 요약"))
        layout.addWidget(self.ddd_text)
        layout.addWidget(_section_label("컴포넌트 스멜"))
        layout.addWidget(self.component_smells_list)
        layout.addWidget(_section_label("흐름 단계"))
        layout.addWidget(self.steps_list)
        layout.addWidget(_section_label("이벤트 요약"))
        layout.addWidget(self.event_text)
        layout.addWidget(_section_label("바운디드 컨텍스트"))
        layout.addWidget(self.bc_text)
        layout.addWidget(_section_label("리팩터링 제안"))
        layout.addWidget(self.refactor_list)
        layout.addWidget(_section_label("마크다운"))
        layout.addWidget(self.markdown_text)
        layout.addWidget(self.export_button)

        self.setStyleSheet("QLabel { font-size: 12px; }")

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
        entry_layer = _layer_label(report.entry_layer)
        self.summary_label.setText(
            f"진입: {report.use_case_name} ({entry_layer}) | 단계: {len(report.flow_steps)}"
        )
        self.flow_summary.setText(_flow_summary_text(report.flow_steps))
        self.ddd_text.setPlainText(_ddd_summary_text(report))
        self.event_text.setPlainText(_event_summary_text(report))
        self.bc_text.setText(
            f"{report.bc_summary.entry_bc_name} | {report.bc_summary.notes}"
        )
        self.component_smells_list.clear()
        if not report.ddd_summary.smells:
            self.component_smells_list.addItem(QListWidgetItem("스멜 없음"))
        else:
            for smell in report.ddd_summary.smells:
                severity_label = _severity_label(smell.severity.value)
                smell_label = _smell_label(smell.smell_type.value)
                self.component_smells_list.addItem(
                    QListWidgetItem(
                        f"[{severity_label}] {smell_label}: {smell.component_name}"
                    )
                )
        self.steps_list.clear()
        for step in report.flow_steps:
            layer_label = _layer_label(step.layer)
            self.steps_list.addItem(
                QListWidgetItem(
                    f"{step.index + 1}. {step.component_name} ({layer_label})"
                )
            )
        self.refactor_list.clear()
        if not report.refactoring_suggestions:
            self.refactor_list.addItem(QListWidgetItem("제안 없음"))
        else:
            for suggestion in report.refactoring_suggestions:
                self.refactor_list.addItem(QListWidgetItem(suggestion.title))
        self.markdown_text.setPlainText(_report_markdown(report))
        if report.event_summary.readiness_score == 0 and not report.event_summary.main_suggestions:
            self.event_text.setPlainText(
                "이벤트 드리븐 준비도 분석 결과가 없습니다.\n"
                "분석 → 이벤트 드리븐 준비도를 먼저 실행하세요."
            )

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


def _readiness_label(level: str) -> str:
    value = level.lower()
    if value == "high":
        return "높음"
    if value == "medium":
        return "중간"
    if value == "low":
        return "낮음"
    return level


def _severity_label(severity: str) -> str:
    value = severity.lower()
    if value == "error":
        return "오류"
    if value == "warning":
        return "경고"
    if value == "info":
        return "정보"
    return severity


def _smell_label(smell_type: str) -> str:
    labels = {
        "anemic_domain": "빈약한 도메인",
        "god_service": "갓 서비스",
        "repository_leak": "레포지토리 누수",
        "cross_aggregate_coupling": "크로스 애그리게잇",
    }
    return labels.get(smell_type, smell_type)


def _ddd_summary_text(report: UseCaseReport) -> str:
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


def _event_summary_text(report: UseCaseReport) -> str:
    summary = report.event_summary
    lines = [
        f"준비도: {summary.readiness_score} ({_readiness_label(summary.readiness_level)})",
        f"동기 결합도: {summary.sync_coupling_strength:.2f}",
    ]
    for suggestion in summary.main_suggestions[:3]:
        lines.append(f"- {suggestion.title}")
    return "\n".join(lines)


def _report_markdown(report: UseCaseReport) -> str:
    lines = [
        f"# 유스케이스 리포트: {report.use_case_name}",
        "",
        f"- 진입: `{report.use_case_name}` ({_layer_label(report.entry_layer)})",
        f"- 흐름 단계: {len(report.flow_steps)}",
        "",
        "## DDD 요약",
        _ddd_summary_text(report),
        "",
        "## 이벤트 요약",
        _event_summary_text(report),
        "",
        "## 바운디드 컨텍스트",
        f"- 진입 BC: {report.bc_summary.entry_bc_name}",
        f"- 노트: {report.bc_summary.notes}",
        "",
        "## 리팩터링 제안",
    ]
    if not report.refactoring_suggestions:
        lines.append("- 없음")
    else:
        for suggestion in report.refactoring_suggestions:
            lines.append(f"- {suggestion.title}")
            lines.append(f"  - {suggestion.description}")
    return "\n".join(lines)
