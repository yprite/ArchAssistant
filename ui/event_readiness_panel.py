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

from analysis.event_readiness import EventReadinessAnalysisResult


class EventReadinessPanel(QWidget):
    use_case_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._result: EventReadinessAnalysisResult | None = None
        self._row_to_use_case: list[str] = []

        self.score_label = QLabel("Project Readiness: -")
        self.summary_label = QLabel("Use Cases: - | High: - | Medium: - | Low: -")

        self.use_case_table = QTableWidget(0, 6)
        self.use_case_table.setHorizontalHeaderLabels(
            ["Use Case", "Entry", "Score", "Externals", "Aggregates", "BCs"]
        )
        self.use_case_table.horizontalHeader().setStretchLastSection(True)
        self.use_case_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.use_case_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.use_case_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.use_case_table.itemSelectionChanged.connect(self._on_selection_changed)

        self.detail_label = QLabel("Select a use case to see suggestions.")
        self.suggestions_list = QListWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.score_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(QLabel("Use Cases"))
        layout.addWidget(self.use_case_table)
        layout.addWidget(QLabel("Refactoring Suggestions"))
        layout.addWidget(self.detail_label)
        layout.addWidget(self.suggestions_list)

        self.setStyleSheet("QLabel { font-size: 12px; color: #333333; }")

    def show_results(self, result: EventReadinessAnalysisResult) -> None:
        self._result = result
        summary = result.project_summary
        self.score_label.setText(f"Project Readiness: {summary.avg_score:.1f} / 100")
        self.summary_label.setText(
            f"Use Cases: {summary.total_use_cases} | High: {summary.high_candidate_count} | "
            f"Medium: {summary.medium_candidate_count} | Low: {summary.low_candidate_count}"
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
            self.use_case_table.setItem(row, 1, QTableWidgetItem(metric.entry_layer))
            self.use_case_table.setItem(row, 2, QTableWidgetItem(str(score.score)))
            self.use_case_table.setItem(row, 3, QTableWidgetItem(str(metric.num_external_systems)))
            self.use_case_table.setItem(row, 4, QTableWidgetItem(str(metric.num_aggregates_touched)))
            self.use_case_table.setItem(row, 5, QTableWidgetItem(str(metric.num_bounded_contexts)))
            self._row_to_use_case.append(score.use_case_id)

        self.suggestions_list.clear()
        self.detail_label.setText("Select a use case to see suggestions.")

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
            self.detail_label.setText(
                f"Score {score.score} ({score.level}) | "
                f"Len {metric.path_length}, Externals {metric.num_external_systems}, "
                f"Aggregates {metric.num_aggregates_touched}"
            )

        self.suggestions_list.clear()
        if suggestions:
            for suggestion in suggestions:
                label = f"[{suggestion.suggestion_type}] {suggestion.title}: {suggestion.description}"
                self.suggestions_list.addItem(QListWidgetItem(label))
        else:
            self.suggestions_list.addItem(QListWidgetItem("No suggestions."))

        self.use_case_selected.emit(use_case_id)
