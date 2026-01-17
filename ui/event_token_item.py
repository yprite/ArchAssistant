from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsObject


class EventTokenItem(QGraphicsObject):
    def __init__(self, color: QColor | None = None) -> None:
        super().__init__()
        self._radius = 4.0
        self._color = color or QColor("#4A74E0")
        self.setZValue(50)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 0)
        shadow_color = QColor(self._color)
        shadow_color.setAlphaF(0.4)
        shadow.setColor(shadow_color)
        self.setGraphicsEffect(shadow)

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        r = self._radius
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(self._color)
        painter.setPen(QColor(self._color).darker(130))
        painter.drawEllipse(self.boundingRect())
