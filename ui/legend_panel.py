from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget, QFrame

from core.config import LAYER_COLORS
from ui.colors import SMELL_COLORS, TEXT_SECONDARY


class LegendPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QLabel("범례")
        header.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 700; font-size: 14px;"
        )
        layout.addWidget(header)

        legend_card = QFrame()
        legend_card.setObjectName("legendCard")
        legend_card_layout = QVBoxLayout(legend_card)
        legend_card_layout.setContentsMargins(14, 14, 14, 14)
        legend_card_layout.setSpacing(8)

        title_legend = QLabel("레이어")
        title_legend.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
        )
        legend_card_layout.addWidget(title_legend)
        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(6)
        for name, layer_key, description in [
            ("도메인", "domain", "핵심 비즈니스 규칙"),
            ("애플리케이션", "application", "유스케이스/흐름"),
            ("인바운드 포트", "inbound_port", "입력 포트 / 유스케이스 인터페이스"),
            ("아웃바운드 포트", "outbound_port", "출력 포트 / 게이트웨이 인터페이스"),
            ("인바운드 어댑터", "inbound_adapter", "입력 어댑터"),
            ("아웃바운드 어댑터", "outbound_adapter", "출력 어댑터"),
            ("미분류", "unknown", "미분류"),
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

        legend_card_layout.addLayout(legend_layout)
        layout.addWidget(legend_card)

        smells_card = QFrame()
        smells_card.setObjectName("smellsCard")
        smells_card_layout = QVBoxLayout(smells_card)
        smells_card_layout.setContentsMargins(14, 14, 14, 14)
        smells_card_layout.setSpacing(8)

        title_smells = QLabel("스멜")
        title_smells.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
        )
        smells_card_layout.addWidget(title_smells)
        smells_layout = QVBoxLayout()
        smells_layout.setSpacing(6)
        for name, color_key, description in [
            ("빈약한 도메인", "anemic_domain", "빈약한 도메인 모델"),
            ("갓 서비스", "god_service", "과도한 서비스/트랜잭션 스크립트"),
            ("레포지토리 누수", "repository_leak", "ORM/인프라 누수"),
            ("크로스 애그리게잇", "cross_aggregate_coupling", "애그리게잇 경계 혼합"),
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

        smells_card_layout.addLayout(smells_layout)
        layout.addWidget(smells_card)
        layout.addStretch(1)
        self.setStyleSheet(
            "QLabel { font-size: 12px; }"
            "QFrame#legendCard { border: 1px solid palette(mid); border-radius: 12px; }"
            "QFrame#smellsCard { border: 1px solid palette(mid); border-radius: 12px; }"
        )
