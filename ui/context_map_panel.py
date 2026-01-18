from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizePolicy

from analysis.bounded_context import BcRelation, BoundedContext


class ContextMapInfoPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.title = QLabel("컨텍스트 맵 정보")
        self.title.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 700; font-size: 13px;"
        )
        self.name_label = QLabel("-")
        self.detail_label = QLabel("-")
        self.name_label.setWordWrap(True)
        self.detail_label.setWordWrap(True)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.detail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.name_label)
        layout.addWidget(self.detail_label)

        self.setStyleSheet("QLabel { font-size: 12px; }")

    def show_context(self, context: BoundedContext) -> None:
        self.name_label.setText(f"컨텍스트: {context.name}")
        layers = ", ".join(sorted(_layer_label(layer) for layer in context.layers_present))
        self.detail_label.setText(
            f"컴포넌트: {len(context.component_ids)} | "
            f"레이어: {layers} | "
            f"헥사곤 점수: {context.hexagon_score:.2f}"
        )

    def show_relation(self, relation: BcRelation, source: BoundedContext, target: BoundedContext) -> None:
        self.name_label.setText(f"관계: {source.name} -> {target.name}")
        self.detail_label.setText(
            f"유형: {relation.relation_type.value} | "
            f"의존: {relation.dependency_count} | "
            f"양방향: {'예' if relation.bidirectional else '아니오'}"
        )

    def clear(self) -> None:
        self.name_label.setText("-")
        self.detail_label.setText("-")


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
