from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView, QHBoxLayout, QToolButton, QWidget


class ArchitectureView(QGraphicsView):
    viewport_changed = Signal()

    def __init__(self, scene) -> None:
        super().__init__(scene)
        self._min_zoom = 0.25
        self._max_zoom = 3.0
        self._zoom_factor = 1.12
        self._zoom_accumulator = 0.0
        self._space_pan = False
        self._panning = False
        self._last_pan_point: QPointF | None = None
        self._minimap = None
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self._init_zoom_controls()

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if event.angleDelta().y() == 0:
            return
        if abs(event.angleDelta().y()) < abs(event.angleDelta().x()):
            event.ignore()
            return

        self._zoom_accumulator += event.angleDelta().y()
        step = 120.0
        anchor = event.position().toPoint()
        changed = False
        while self._zoom_accumulator >= step:
            changed = self._apply_zoom_step(True, anchor) or changed
            self._zoom_accumulator -= step
        while self._zoom_accumulator <= -step:
            changed = self._apply_zoom_step(False, anchor) or changed
            self._zoom_accumulator += step
        if changed:
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
        if event.button() == Qt.MouseButton.LeftButton:
            if self.itemAt(event.position().toPoint()) is None:
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
        if self._apply_zoom_step(True, None):
            self.viewport_changed.emit()

    def zoom_out(self) -> None:
        if self._apply_zoom_step(False, None):
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

    def _apply_zoom(self, factor: float) -> bool:
        current = self._current_scale()
        target = max(self._min_zoom, min(self._max_zoom, current * factor))
        if abs(target - current) < 1e-4:
            return False
        actual = target / current
        self.scale(actual, actual)
        return True

    def _apply_zoom_step(self, zoom_in: bool, anchor_pos) -> bool:
        factor = self._zoom_factor if zoom_in else 1 / self._zoom_factor
        if anchor_pos is None:
            return self._apply_zoom(factor)
        old_pos = self.mapToScene(anchor_pos)
        changed = self._apply_zoom(factor)
        if not changed:
            return False
        new_pos = self.mapToScene(anchor_pos)
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        return True

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
        self._init_flow_controls()

    def set_zoom_reset_callback(self, callback) -> None:
        self._zoom_reset.clicked.connect(callback)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_zoom_controls()
        self._position_flow_controls()
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

    def set_overlays_visible(self, visible: bool) -> None:
        self._zoom_controls.setVisible(visible)
        self._flow_controls.setVisible(visible)

    def centerOn(self, *args) -> None:  # type: ignore[override]
        super().centerOn(*args)
        self.viewport_changed.emit()

    def _init_flow_controls(self) -> None:
        self._flow_controls = QWidget(self.viewport())
        self._flow_controls.setFixedSize(156, 32)
        layout = QHBoxLayout(self._flow_controls)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        self._flow_play = QToolButton()
        self._flow_play.setText("▶")
        self._flow_pause = QToolButton()
        self._flow_pause.setText("⏸")
        self._flow_step = QToolButton()
        self._flow_step.setText("⏭")
        self._flow_restart = QToolButton()
        self._flow_restart.setText("⟲")
        for button in (self._flow_play, self._flow_pause, self._flow_step, self._flow_restart):
            button.setFixedSize(28, 24)
        layout.addWidget(self._flow_play)
        layout.addWidget(self._flow_pause)
        layout.addWidget(self._flow_step)
        layout.addWidget(self._flow_restart)
        self._flow_controls.setStyleSheet(
            "QWidget { background: rgba(255, 255, 255, 0.75); border-radius: 8px; }"
            "QToolButton { background: transparent; border: 1px solid #D6D6D6;"
            " border-radius: 6px; font-weight: 600; }"
        )
        self._position_flow_controls()

    def set_flow_controls(self, play_cb, pause_cb, step_cb, restart_cb) -> None:
        self._flow_play.clicked.connect(play_cb)
        self._flow_pause.clicked.connect(pause_cb)
        self._flow_step.clicked.connect(step_cb)
        self._flow_restart.clicked.connect(restart_cb)

    def _position_flow_controls(self) -> None:
        margin = 12
        x = self.viewport().width() - self._flow_controls.width() - margin
        y = self.viewport().height() - self._flow_controls.height() - margin
        self._flow_controls.move(x, y)
