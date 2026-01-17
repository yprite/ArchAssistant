from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget


class FiltersPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.filter_boxes: dict[str, QCheckBox] = {}

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

        layout.addStretch(1)

        self.setStyleSheet(
            "QLabel { color: #333333; font-size: 12px; }"
            "QCheckBox { font-size: 12px; padding: 2px 0; }"
        )
