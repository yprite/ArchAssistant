from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.config import LAYER_COLORS
from ui.colors import SMELL_COLORS, TEXT_SECONDARY


class LegendPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_legend = QLabel("LEGEND")
        title_legend.setStyleSheet("font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title_legend)
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(6)
        for name, layer_key, description in [
            ("Domain", "domain", "핵심 비즈니스 규칙"),
            ("Application", "application", "유스케이스/흐름"),
            ("Inbound Port", "inbound_port", "Input Port / UseCase 인터페이스"),
            ("Outbound Port", "outbound_port", "Output Port / Gateway 인터페이스"),
            ("Inbound Adapter", "inbound_adapter", "Input Port"),
            ("Outbound Adapter", "outbound_adapter", "Output Port"),
            ("Unknown", "unknown", "미분류"),
        ]:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"background-color: {LAYER_COLORS[layer_key]}; border-radius: 6px;"
            )
            row_layout.addWidget(dot)
            label = QLabel(f"{name} – {description}")
            label.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")
            row_layout.addWidget(label)
            row_layout.addStretch(1)
            legend_layout.addWidget(row)

        layout.addLayout(legend_layout)

        title_smells = QLabel("SMELLS")
        title_smells.setStyleSheet("font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title_smells)
        smells_layout = QVBoxLayout()
        smells_layout.setSpacing(6)
        for name, color_key, description in [
            ("Anemic Domain", "anemic_domain", "빈약한 도메인 모델"),
            ("God Service", "god_service", "과도한 서비스/트랜잭션 스크립트"),
            ("Repository Leak", "repository_leak", "ORM/인프라 누수"),
            ("Cross-Aggregate", "cross_aggregate_coupling", "애그리게잇 경계 혼합"),
        ]:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"background-color: {SMELL_COLORS[color_key].name()}; border-radius: 6px;"
            )
            row_layout.addWidget(dot)
            label = QLabel(f"{name} – {description}")
            label.setStyleSheet(f"color: {TEXT_SECONDARY.name()};")
            row_layout.addWidget(label)
            row_layout.addStretch(1)
            smells_layout.addWidget(row)

        layout.addLayout(smells_layout)
        layout.addStretch(1)
        self.setStyleSheet(
            "QLabel { color: #333333; font-size: 12px; }"
        )
