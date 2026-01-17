from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem

from ui.colors import EDGE_COLOR, EDGE_HIGHLIGHT


class EdgeItem(QGraphicsItem):
    def __init__(self, source_item, target_item) -> None:
        super().__init__()
        self.source_item = source_item
        self.target_item = target_item
        self._highlighted = False
        self._path = QPainterPath()
        self._arrow = QPolygonF()
        self._bounding = QRectF()

        if hasattr(source_item, "position_changed"):
            source_item.position_changed.connect(self.update_positions)
        if hasattr(target_item, "position_changed"):
            target_item.position_changed.connect(self.update_positions)
        self.update_positions()

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return self._bounding

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = self._highlight_pen() if self._highlighted else self._default_pen()
        painter.setPen(pen)
        painter.setBrush(self._arrow_brush())
        painter.drawPath(self._path)
        if not self._arrow.isEmpty():
            painter.drawPolygon(self._arrow)

    def update_positions(self) -> None:
        if not self.source_item or not self.target_item:
            return
        source_center = self.source_item.sceneBoundingRect().center()
        target_center = self.target_item.sceneBoundingRect().center()
        path, arrow = self._build_path(source_center, target_center)
        self.prepareGeometryChange()
        self._path = path
        self._arrow = arrow
        self._bounding = self._path.boundingRect().adjusted(-6, -6, 6, 6)
        self.update()

    def set_highlighted(self, highlighted: bool) -> None:
        self._highlighted = highlighted
        self.update()

    def _default_pen(self) -> QPen:
        color = EDGE_COLOR
        color.setAlphaF(0.55)
        pen = QPen(color, 1.0)
        pen.setCosmetic(True)
        return pen

    def _highlight_pen(self) -> QPen:
        color = EDGE_HIGHLIGHT
        color.setAlphaF(0.9)
        pen = QPen(color, 1.6)
        pen.setCosmetic(True)
        return pen

    def _arrow_brush(self) -> QColor:
        if self._highlighted:
            color = QColor(EDGE_HIGHLIGHT)
            color.setAlphaF(0.85)
            return color
        color = QColor(EDGE_COLOR)
        color.setAlphaF(0.75)
        return color

    def _build_path(self, start: QPointF, end: QPointF) -> tuple[QPainterPath, QPolygonF]:
        path = QPainterPath(start)
        distance = math.hypot(end.x() - start.x(), end.y() - start.y())
        arrow = QPolygonF()
        if distance < 1.0:
            return path, arrow

        if distance < 140:
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            offset = self._perp_offset(start, end, 18)
            control = QPointF(mid.x() + offset.x(), mid.y() + offset.y())
            path.quadTo(control, end)
            arrow = self._arrow_head(control, end)
        else:
            path.lineTo(end)
            arrow = self._arrow_head(start, end)
        return path, arrow

    def _arrow_head(self, tail: QPointF, tip: QPointF) -> QPolygonF:
        angle = math.atan2(tip.y() - tail.y(), tip.x() - tail.x())
        size = 4.0
        left = QPointF(
            tip.x() - size * math.cos(angle - math.pi / 6),
            tip.y() - size * math.sin(angle - math.pi / 6),
        )
        right = QPointF(
            tip.x() - size * math.cos(angle + math.pi / 6),
            tip.y() - size * math.sin(angle + math.pi / 6),
        )
        return QPolygonF([tip, left, right])

    def _perp_offset(self, start: QPointF, end: QPointF, magnitude: float) -> QPointF:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return QPointF(0, 0)
        return QPointF(-dy / length * magnitude, dx / length * magnitude)
