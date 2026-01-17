from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem


@dataclass(frozen=True)
class RingSpec:
    inner_radius: float
    outer_radius: float


class LayerBackgroundItem(QGraphicsPathItem):
    def __init__(self, path: QPainterPath, color: QColor, z: float = -100) -> None:
        super().__init__(path)
        color.setAlphaF(0.18)
        self.setBrush(color)
        pen = QPen(color.darker(130))
        pen.setWidth(1)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setZValue(z)


def ring_path(center: QPointF, spec: RingSpec) -> QPainterPath:
    path = QPainterPath()
    outer = QRectF(
        center.x() - spec.outer_radius,
        center.y() - spec.outer_radius,
        spec.outer_radius * 2,
        spec.outer_radius * 2,
    )
    inner = QRectF(
        center.x() - spec.inner_radius,
        center.y() - spec.inner_radius,
        spec.inner_radius * 2,
        spec.inner_radius * 2,
    )
    path.addEllipse(outer)
    path.addEllipse(inner)
    path.setFillRule(Qt.FillRule.OddEvenFill)
    return path


def sector_path(center: QPointF, spec: RingSpec, start_angle: float, end_angle: float) -> QPainterPath:
    path = QPainterPath()
    outer_rect = QRectF(
        center.x() - spec.outer_radius,
        center.y() - spec.outer_radius,
        spec.outer_radius * 2,
        spec.outer_radius * 2,
    )
    inner_rect = QRectF(
        center.x() - spec.inner_radius,
        center.y() - spec.inner_radius,
        spec.inner_radius * 2,
        spec.inner_radius * 2,
    )
    start_deg = math.degrees(start_angle)
    span_deg = math.degrees(end_angle - start_angle)

    path.moveTo(center)
    path.arcMoveTo(outer_rect, start_deg)
    path.arcTo(outer_rect, start_deg, span_deg)
    path.arcTo(inner_rect, start_deg + span_deg, -span_deg)
    path.closeSubpath()
    return path


def hex_path(center: QPointF, radius: float) -> QPainterPath:
    path = QPainterPath()
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.append(
            QPointF(
                center.x() + math.cos(angle) * radius,
                center.y() + math.sin(angle) * radius,
            )
        )
    if points:
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
    return path
