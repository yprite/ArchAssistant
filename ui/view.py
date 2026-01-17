from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtWidgets import QGraphicsView, QHBoxLayout, QToolButton, QWidget


class ArchitectureView(QGraphicsView):
    viewport_changed = Signal()

    def __init__(self, scene) -> None:
        super().__init__(scene)
        self._min_zoom = 0.25
        self._max_zoom = 3.0
        self._zoom_factor = 1.12
        self._space_pan = False
        self._panning = False
        self._last_pan_point: QPointF | None = None
        self._minimap = None
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._init_zoom_controls()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if event.angleDelta().y() == 0:
            return
        factor = self._zoom_factor if event.angleDelta().y() > 0 else 1 / self._zoom_factor
        old_pos = self.mapToScene(event.position().toPoint())
        self._apply_zoom(factor)
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        self.viewport_changed.emit()
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.RightButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_pan
        ):
            self._panning = True
            self._last_pan_point = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._panning and self._last_pan_point is not None:
            delta = event.position() - self._last_pan_point
            self.translate(delta.x(), delta.y())
            self._last_pan_point = event.position()
            self.viewport_changed.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._panning and event.button() in (
            Qt.MouseButton.RightButton,
            Qt.MouseButton.LeftButton,
        ):
            self._panning = False
            self._last_pan_point = None
            self.setCursor(
                Qt.CursorShape.OpenHandCursor if self._space_pan else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Space:
            self._space_pan = True
            if not self._panning:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        step = 40
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step = 120
        if event.key() == Qt.Key.Key_Left:
            self.translate(-step, 0)
            self.viewport_changed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.translate(step, 0)
            self.viewport_changed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Up:
            self.translate(0, -step)
            self.viewport_changed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self.translate(0, step)
            self.viewport_changed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Space:
            self._space_pan = False
            if not self._panning:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def zoom_in(self) -> None:
        self._apply_zoom(self._zoom_factor)
        self.viewport_changed.emit()

    def zoom_out(self) -> None:
        self._apply_zoom(1 / self._zoom_factor)
        self.viewport_changed.emit()

    def zoom_to_fit(self, rect) -> None:
        if rect.isNull():
            return
        padded = rect.adjusted(
            -rect.width() * 0.14,
            -rect.height() * 0.14,
            rect.width() * 0.14,
            rect.height() * 0.14,
        )
        self.fitInView(padded, Qt.AspectRatioMode.KeepAspectRatio)
        if self._current_scale() > 1.0:
            self.resetTransform()
            self.centerOn(padded.center())
        self.viewport_changed.emit()

    def _apply_zoom(self, factor: float) -> None:
        current = self._current_scale()
        target = max(self._min_zoom, min(self._max_zoom, current * factor))
        if abs(target - current) < 1e-4:
            return
        actual = target / current
        self.scale(actual, actual)

    def _current_scale(self) -> float:
        return self.transform().m11()

    def _init_zoom_controls(self) -> None:
        self._zoom_controls = QWidget(self.viewport())
        self._zoom_controls.setFixedSize(120, 32)
        layout = QHBoxLayout(self._zoom_controls)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        self._zoom_in = QToolButton()
        self._zoom_in.setText("+")
        self._zoom_out = QToolButton()
        self._zoom_out.setText("-")
        self._zoom_reset = QToolButton()
        self._zoom_reset.setText("[]")
        for button in (self._zoom_in, self._zoom_out, self._zoom_reset):
            button.setFixedSize(28, 24)
        self._zoom_in.clicked.connect(self.zoom_in)
        self._zoom_out.clicked.connect(self.zoom_out)
        layout.addWidget(self._zoom_in)
        layout.addWidget(self._zoom_out)
        layout.addWidget(self._zoom_reset)
        self._zoom_controls.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.75); border-radius: 8px; }"
            "QToolButton { background: transparent; border: 1px solid #D6D6D6;"
            " border-radius: 6px; font-weight: 600; }"
        )
        self._position_zoom_controls()

    def set_zoom_reset_callback(self, callback) -> None:
        self._zoom_reset.clicked.connect(callback)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_zoom_controls()
        if self._minimap is not None:
            self._minimap.position_in_view()
        self.viewport_changed.emit()

    def _position_zoom_controls(self) -> None:
        margin = 12
        x = self.viewport().width() - self._zoom_controls.width() - margin
        y = margin
        self._zoom_controls.move(x, y)

    def set_minimap(self, minimap) -> None:
        self._minimap = minimap
        self._minimap.position_in_view()

    def centerOn(self, *args) -> None:  # type: ignore[override]
        super().centerOn(*args)
        self.viewport_changed.emit()
