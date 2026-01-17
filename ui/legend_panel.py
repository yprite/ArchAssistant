from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.config import LAYER_COLORS
from ui.colors import TEXT_SECONDARY


class LegendPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.filter_boxes: dict[str, QCheckBox] = {}
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_filters = QLabel("FILTERS")
        title_filters.setStyleSheet("font-weight: 700; letter-spacing: 1px;")
        layout.addWidget(title_filters)
        for layer in [
            "domain",
            "application",
            "inbound_port",
            "outbound_port",
            "inbound_adapter",
            "outbound_adapter",
            "unknown",
        ]:
            box = QCheckBox(layer)
            box.setChecked(True)
            layout.addWidget(box)
            self.filter_boxes[layer] = box

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
        layout.addStretch(1)
        self.setStyleSheet(
            "QLabel { color: #333333; font-size: 12px; }"
            "QCheckBox { font-size: 12px; padding: 2px 0; }"
        )
