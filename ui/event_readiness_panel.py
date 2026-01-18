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

from analysis.event_readiness import EventReadinessAnalysisResult


class EventReadinessPanel(QWidget):
    use_case_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._result: EventReadinessAnalysisResult | None = None
        self._row_to_use_case: list[str] = []
        self.empty_label = QLabel(
            "이벤트 드리븐 준비도 분석이 아직 실행되지 않았습니다.\n"
            "분석 메뉴에서 이벤트 드리븐 준비도를 실행하세요."
        )
        self.empty_label.setWordWrap(True)

        self.score_label = QLabel("프로젝트 준비도: -")
        self.summary_label = QLabel("유스케이스: - | 높음: - | 중간: - | 낮음: -")

        self.use_case_table = QTableWidget(0, 6)
        self.use_case_table.setHorizontalHeaderLabels(
            ["유스케이스", "진입", "점수", "외부", "애그리게잇", "BC"]
        )
        header = self.use_case_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.use_case_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.use_case_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.use_case_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.use_case_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.use_case_table.setAlternatingRowColors(True)
        self.use_case_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.detail_label = QLabel("유스케이스를 선택하면 제안을 확인할 수 있습니다.")
        self.suggestions_list = QListWidget()
        self.suggestions_list.setAlternatingRowColors(True)
        self.suggestions_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.suggestions_list.setWordWrap(True)

        def _section_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setStyleSheet(
                "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
            )
            return label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.score_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(_section_label("유스케이스"))
        layout.addWidget(self.use_case_table)
        layout.addWidget(_section_label("리팩터링 제안"))
        layout.addWidget(self.detail_label)
        layout.addWidget(self.suggestions_list)

        self.setStyleSheet("QLabel { font-size: 12px; }")
        self._set_empty_state(True)

    def show_results(self, result: EventReadinessAnalysisResult) -> None:
        self._result = result
        summary = result.project_summary
        if summary.total_use_cases == 0:
            self.show_empty_state("분석된 유스케이스가 없습니다.")
            return
        self._set_empty_state(False)
        self.score_label.setText(f"프로젝트 준비도: {summary.avg_score:.1f} / 100")
        self.summary_label.setText(
            f"유스케이스: {summary.total_use_cases} | 높음: {summary.high_candidate_count} | "
            f"중간: {summary.medium_candidate_count} | 낮음: {summary.low_candidate_count}"
        )

        scores = result.project_summary.scores_by_use_case
        metrics = result.per_use_case_metrics

        self._row_to_use_case = []
        self.use_case_table.setRowCount(0)
        for score in sorted(scores, key=lambda s: s.score, reverse=True):
            metric = metrics.get(score.use_case_id)
            if not metric:
                continue
            row = self.use_case_table.rowCount()
            self.use_case_table.insertRow(row)
            self.use_case_table.setItem(row, 0, QTableWidgetItem(metric.use_case_name))
            self.use_case_table.setItem(
                row, 1, QTableWidgetItem(_layer_label(metric.entry_layer))
            )
            score_item = QTableWidgetItem(str(score.score))
            score_item.setForeground(QBrush(_score_color(score.level)))
            self.use_case_table.setItem(row, 2, score_item)
            self.use_case_table.setItem(row, 3, QTableWidgetItem(str(metric.num_external_systems)))
            self.use_case_table.setItem(row, 4, QTableWidgetItem(str(metric.num_aggregates_touched)))
            self.use_case_table.setItem(row, 5, QTableWidgetItem(str(metric.num_bounded_contexts)))
            self._row_to_use_case.append(score.use_case_id)

        self.suggestions_list.clear()
        self.detail_label.setText("유스케이스를 선택하면 제안을 확인할 수 있습니다.")

    def show_empty_state(self, message: str) -> None:
        self.empty_label.setText(message)
        self._set_empty_state(True)

    def _on_selection_changed(self) -> None:
        if not self._result:
            return
        row = self.use_case_table.currentRow()
        if row < 0 or row >= len(self._row_to_use_case):
            return
        use_case_id = self._row_to_use_case[row]
        score = self._result.per_use_case_scores.get(use_case_id)
        metric = self._result.per_use_case_metrics.get(use_case_id)
        suggestions = self._result.per_use_case_suggestions.get(use_case_id, [])

        if score and metric:
            level_label = _level_label(score.level)
            self.detail_label.setText(
                f"점수 {score.score} ({level_label}) | "
                f"길이 {metric.path_length}, 외부 {metric.num_external_systems}, "
                f"애그리게잇 {metric.num_aggregates_touched}"
            )

        self.suggestions_list.clear()
        if suggestions:
            for suggestion in suggestions:
                label = f"[{suggestion.suggestion_type}] {suggestion.title}: {suggestion.description}"
                self.suggestions_list.addItem(QListWidgetItem(label))
        else:
            self.suggestions_list.addItem(QListWidgetItem("제안 없음."))

        self.use_case_selected.emit(use_case_id)

    def _set_empty_state(self, empty: bool) -> None:
        self.empty_label.setVisible(empty)
        self.score_label.setVisible(not empty)
        self.summary_label.setVisible(not empty)
        self.use_case_table.setVisible(not empty)
        self.detail_label.setVisible(not empty)
        self.suggestions_list.setVisible(not empty)


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


def _score_color(level: str) -> QColor:
    value = level.lower()
    if value == "high":
        return QColor("#16A34A")
    if value == "medium":
        return QColor("#F59E0B")
    return QColor("#DC2626")


def _level_label(level: str) -> str:
    value = level.lower()
    if value == "high":
        return "높음"
    if value == "medium":
        return "중간"
    return "낮음"
