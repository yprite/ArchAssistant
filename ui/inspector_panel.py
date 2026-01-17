from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QComboBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analyzer.model import Component


class InspectorPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Inspector")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        self.name_label = QLabel("-")
        self.layer_label = QLabel("-")
        self.package_label = QLabel("-")
        self.package_label.setWordWrap(True)
        self.path_label = QLabel("-")
        self.path_label.setWordWrap(True)
        self.annotations_text = QTextEdit()
        self.imports_text = QTextEdit()
        self.open_button = QPushButton("Open in File Explorer")
        self.flow_button = QPushButton("Show Flow from Here")
        self.animate_flow_button = QPushButton("Play Flow Animation")
        self.clear_flow_button = QPushButton("Clear Flow")
        self.report_button = QPushButton("Generate Use Case Report")
        self.flow_title = QLabel("Flow")
        self.flow_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.flow_speed = QComboBox()
        self.flow_speed.addItems(["0.5x", "1x", "1.5x", "2x"])
        self.flow_speed.setCurrentText("1x")
        self.flow_list = QListWidget()
        self.flow_list.setFixedHeight(180)
        self.flow_list.setVisible(False)
        self.flow_title.setVisible(False)
        self.clear_flow_button.setVisible(False)
        self.violations_title = QLabel("Violations")
        self.violations_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.violations_list = QListWidget()
        self.violations_list.setFixedHeight(140)
        self.violations_title.setVisible(False)
        self.violations_list.setVisible(False)
        self.smells_title = QLabel("DDD Smells")
        self.smells_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        self.smells_list = QListWidget()
        self.smells_list.setFixedHeight(140)
        self.smells_title.setVisible(False)
        self.smells_list.setVisible(False)
        self.open_button.setEnabled(False)

        for widget in (self.annotations_text, self.imports_text):
            widget.setReadOnly(True)
            widget.setFixedHeight(120)
            widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        for label in (self.name_label, self.layer_label, self.package_label, self.path_label):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(8)
        form_layout.addRow("Name", self.name_label)
        form_layout.addRow("Layer", self.layer_label)
        form_layout.addRow("Package", self.package_label)
        form_layout.addRow("Path", self.path_label)
        form_layout.addRow("Annotations", self.annotations_text)
        form_layout.addRow("Imports", self.imports_text)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addLayout(form_layout)
        layout.addWidget(self.open_button)
        layout.addWidget(self.flow_button)
        layout.addWidget(self.animate_flow_button)
        layout.addWidget(QLabel("Flow Speed"))
        layout.addWidget(self.flow_speed)
        layout.addWidget(self.clear_flow_button)
        layout.addWidget(self.report_button)
        layout.addWidget(self.flow_title)
        layout.addWidget(self.flow_list)
        layout.addWidget(self.violations_title)
        layout.addWidget(self.violations_list)
        layout.addWidget(self.smells_title)
        layout.addWidget(self.smells_list)
        self.setLayout(layout)
        self.setStyleSheet(
            "QLabel { font-size: 13px; color: #333333; }"
            "QTextEdit { font-size: 11px; }"
            "QPushButton { padding: 8px 12px; border-radius: 8px;"
            " background: #4A74E0; color: white; font-weight: 600; }"
            "QPushButton:disabled { background: #BFC9E8; }"
        )

        self._current_path: Path | None = None
        self._base_path: Path | None = None
        self.open_button.clicked.connect(self._open_path)
        self._current_component: Component | None = None
        self._layer_labels = {
            "domain": "Domain",
            "application": "Application",
            "inbound_port": "Inbound Port",
            "outbound_port": "Outbound Port",
            "inbound_adapter": "Inbound Adapter",
            "outbound_adapter": "Outbound Adapter",
            "unknown": "Unknown",
        }

    def set_base_path(self, base_path: Path | None) -> None:
        self._base_path = base_path

    def show_component(self, component: Component | None) -> None:
        self._current_component = component
        if component is None:
            self.name_label.setText("-")
            self.layer_label.setText("-")
            self.package_label.setText("-")
            self.path_label.setText("-")
            self.annotations_text.setPlainText("")
            self.imports_text.setPlainText("")
            self.open_button.setEnabled(False)
            self.flow_button.setEnabled(False)
            self.animate_flow_button.setEnabled(False)
            self.report_button.setEnabled(False)
            self.clear_component_violations()
            self.clear_component_smells()
            self._current_path = None
            return

        self.name_label.setText(component.name)
        self.layer_label.setText(self._layer_labels.get(component.layer, component.layer))
        self.package_label.setText(component.package)
        self.path_label.setText(component.path)
        self.annotations_text.setPlainText("\n".join(component.annotations))
        self.imports_text.setPlainText("\n".join(component.imports[:30]))
        self.open_button.setEnabled(bool(component.path))
        self.flow_button.setEnabled(True)
        self.animate_flow_button.setEnabled(True)
        if component.path:
            path = Path(component.path)
            if self._base_path and not path.is_absolute():
                path = self._base_path / path
            self._current_path = path
        else:
            self._current_path = None

    def show_flow(self, flow_items: list[tuple[str, str, str]]) -> None:
        self.flow_list.clear()
        for index, layer_label, name in flow_items:
            item = QListWidgetItem(f"{index}. [{layer_label}] {name}")
            self.flow_list.addItem(item)
        has_items = bool(flow_items)
        self.flow_title.setVisible(True)
        self.flow_list.setVisible(True)
        self.clear_flow_button.setVisible(True)
        if not has_items:
            self.flow_list.addItem(QListWidgetItem("No flow"))

    def show_flow_steps(self, steps: list[str]) -> None:
        self.flow_list.clear()
        for idx, label in enumerate(steps, start=1):
            self.flow_list.addItem(QListWidgetItem(f"{idx}. {label}"))
        self.flow_title.setVisible(True)
        self.flow_list.setVisible(True)
        self.clear_flow_button.setVisible(True)

    def set_active_flow_step(self, index: int) -> None:
        if index < 0 or index >= self.flow_list.count():
            return
        self.flow_list.setCurrentRow(index)
        self.flow_list.scrollToItem(self.flow_list.currentItem())

    def clear_flow(self) -> None:
        self.flow_list.clear()
        self.flow_list.setVisible(False)
        self.flow_title.setVisible(False)
        self.clear_flow_button.setVisible(False)

    def current_component(self) -> Component | None:
        return self._current_component

    def show_component_violations(self, items: list[str]) -> None:
        self.violations_list.clear()
        for item in items:
            self.violations_list.addItem(QListWidgetItem(item))
        self.violations_title.setVisible(True)
        self.violations_list.setVisible(True)
        if not items:
            self.violations_list.addItem(QListWidgetItem("No violations"))

    def clear_component_violations(self) -> None:
        self.violations_list.clear()
        self.violations_list.setVisible(False)
        self.violations_title.setVisible(False)

    def show_component_smells(self, items: list[str]) -> None:
        self.smells_list.clear()
        for item in items:
            self.smells_list.addItem(QListWidgetItem(item))
        self.smells_title.setVisible(True)
        self.smells_list.setVisible(True)
        if not items:
            self.smells_list.addItem(QListWidgetItem("No smells detected"))

    def clear_component_smells(self) -> None:
        self.smells_list.clear()
        self.smells_list.setVisible(False)
        self.smells_title.setVisible(False)

    def _open_path(self) -> None:
        if not self._current_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_path.resolve())))
