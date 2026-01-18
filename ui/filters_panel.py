from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget, QFrame


class FiltersPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.filter_boxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QLabel("필터")
        header.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 700; font-size: 14px;"
        )
        layout.addWidget(header)

        card = QFrame()
        card.setObjectName("filtersCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(8)

        title_filters = QLabel("레이어")
        title_filters.setStyleSheet(
            "font-family: 'Gmarket Sans'; font-weight: 600; font-size: 12px;"
        )
        card_layout.addWidget(title_filters)

        labels = {
            "domain": "도메인 (domain)",
            "application": "애플리케이션 (application)",
            "inbound_port": "인바운드 포트 (inbound_port)",
            "outbound_port": "아웃바운드 포트 (outbound_port)",
            "inbound_adapter": "인바운드 어댑터 (inbound_adapter)",
            "outbound_adapter": "아웃바운드 어댑터 (outbound_adapter)",
            "unknown": "미분류 (unknown)",
        }

        for layer in [
            "domain",
            "application",
            "inbound_port",
            "outbound_port",
            "inbound_adapter",
            "outbound_adapter",
            "unknown",
        ]:
            box = QCheckBox(labels.get(layer, layer))
            box.setChecked(True)
            card_layout.addWidget(box)
            self.filter_boxes[layer] = box

        layout.addWidget(card)
        layout.addStretch(1)

        self.setStyleSheet(
            "QLabel { font-size: 12px; }"
            "QCheckBox { font-size: 12px; padding: 2px 0; }"
            "QFrame#filtersCard { border: 1px solid palette(mid); border-radius: 12px; }"
        )
