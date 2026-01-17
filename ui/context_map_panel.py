from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from analysis.bounded_context import BcRelation, BoundedContext


class ContextMapInfoPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.title = QLabel("Context Map Info")
        self.title.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.name_label = QLabel("-")
        self.detail_label = QLabel("-")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.name_label)
        layout.addWidget(self.detail_label)

        self.setStyleSheet("QLabel { font-size: 12px; color: #333333; }")

    def show_context(self, context: BoundedContext) -> None:
        self.name_label.setText(f"Context: {context.name}")
        self.detail_label.setText(
            f"Components: {len(context.component_ids)} | "
            f"Layers: {', '.join(sorted(context.layers_present))} | "
            f"Hex score: {context.hexagon_score:.2f}"
        )

    def show_relation(self, relation: BcRelation, source: BoundedContext, target: BoundedContext) -> None:
        self.name_label.setText(f"Relation: {source.name} -> {target.name}")
        self.detail_label.setText(
            f"Type: {relation.relation_type.value} | "
            f"Deps: {relation.dependency_count} | "
            f"Bidirectional: {'Yes' if relation.bidirectional else 'No'}"
        )

    def clear(self) -> None:
        self.name_label.setText("-")
        self.detail_label.setText("-")
