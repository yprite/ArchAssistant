from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsObject

from analyzer.model import Component
from core.config import LAYER_COLORS, LayoutConfig
from ui.colors import FLOW_ACTIVE, FLOW_DIM, FLOW_IN, FLOW_VISITED, STROKE_COLOR, TEXT_PRIMARY


class ComponentItem(QGraphicsObject):
    clicked = Signal(object)
    hovered = Signal(object, bool)
    double_clicked = Signal(object)
    position_changed = Signal()

    def __init__(self, component: Component, layout: LayoutConfig | None = None) -> None:
        super().__init__()
        self.component = component
        self.layout = layout or LayoutConfig()
        self._label_text = component.name
        self._display_text = self._ellipsize_label(component.name)
        self._pill_height = 20
        self._pill_padding = 10
        self._pill_rect = self._build_pill_rect()
        self.color = QColor(LAYER_COLORS.get(component.layer, "#9C9C9C"))
        self._fill_color = QColor(self.color).darker(110)
        self._fill_color.setAlphaF(0.26)
        self._stroke_color = QColor(self.color).darker(140)
        self._is_active = False
        self._is_hovered = False
        self._in_flow = False
        self._flow_visited = False
        self._flow_active = False
        self._flow_start = False
        self._anim_active = False
        self._flash_animation: QPropertyAnimation | None = None
        self.setToolTip(self._build_tooltip())
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsObject.CacheMode.DeviceCoordinateCache)
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(8)
        self._shadow.setOffset(0, 2)
        shadow_color = QColor(0, 0, 0)
        shadow_color.setAlphaF(0.06)
        self._shadow.setColor(shadow_color)
        self.setGraphicsEffect(self._shadow)

    def boundingRect(self) -> QRectF:
        return QRectF(self._pill_rect)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(self._stroke_color, self._current_stroke_width())
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(self._fill_color)
        painter.drawRoundedRect(self._pill_rect, self._pill_height / 2, self._pill_height / 2)
        if painter.worldTransform().m11() > 0.35:
            text_color = QColor("#FFFFFF") if (self._in_flow or self._flow_active) else TEXT_PRIMARY
            painter.setPen(QPen(text_color))
            painter.setFont(self._label_font())
            painter.drawText(self._pill_rect, Qt.AlignmentFlag.AlignCenter, self._display_text)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.clicked.emit(self.component)
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self._is_hovered = True
        self._update_glow(True)
        self.setScale(1.04)
        self.update()
        self.hovered.emit(self.component, True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._is_hovered = False
        self._update_glow(False)
        self.setScale(1.0)
        self.update()
        self.hovered.emit(self.component, False)
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        self.double_clicked.emit(self.component)
        super().mouseDoubleClickEvent(event)

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.update()

    def set_flow_state(self, in_flow: bool, is_start: bool = False) -> None:
        self._in_flow = in_flow
        self._flow_start = is_start
        if in_flow:
            self._fill_color = QColor(FLOW_IN)
            self._fill_color.setAlphaF(0.7)
        else:
            self._fill_color = QColor(self.color).darker(110)
            self._fill_color.setAlphaF(0.26)
        self.update()

    def set_flow_visited(self, visited: bool) -> None:
        self._flow_visited = visited
        if visited:
            self._fill_color = QColor(FLOW_VISITED)
            self._fill_color.setAlphaF(0.85)
        elif self._in_flow:
            self._fill_color = QColor(FLOW_IN)
            self._fill_color.setAlphaF(0.7)
        self.update()

    def set_flow_active(self, active: bool) -> None:
        self._flow_active = active
        if active:
            self._fill_color = QColor(FLOW_ACTIVE)
            self._fill_color.setAlphaF(0.95)
        elif self._flow_visited:
            self._fill_color = QColor(FLOW_VISITED)
            self._fill_color.setAlphaF(0.85)
        elif self._in_flow:
            self._fill_color = QColor(FLOW_IN)
            self._fill_color.setAlphaF(0.7)
        else:
            self._fill_color = QColor(self.color).darker(110)
            self._fill_color.setAlphaF(0.26)
        self.update()

    def set_animation_active(self, active: bool) -> None:
        self._anim_active = active
        if active:
            self._fill_color = QColor(self.color).darker(150)
            self._fill_color.setAlphaF(0.95)
        elif self._in_flow:
            self._fill_color = QColor(self.color).darker(140)
            self._fill_color.setAlphaF(0.9)
        else:
            self._fill_color = QColor(self.color).darker(110)
            self._fill_color.setAlphaF(0.26)
        self.update()

    def flash(self, cycles: int = 3) -> None:
        if self._flash_animation:
            self._flash_animation.stop()
        animation = QPropertyAnimation(self, b"opacity")
        animation.setDuration(2000)
        animation.setStartValue(1.0)
        animation.setKeyValueAt(0.25, 0.7)
        animation.setKeyValueAt(0.5, 1.0)
        animation.setKeyValueAt(0.75, 0.7)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.start()
        self._flash_animation = animation

    def _update_glow(self, hovered: bool) -> None:
        blur = 14 if hovered else 8
        color = QColor(0, 0, 0)
        color.setAlphaF(0.1 if hovered else 0.06)
        self._shadow.setBlurRadius(blur)
        self._shadow.setColor(color)

    def _current_stroke_width(self) -> float:
        if self._is_active:
            return 1.4
        if self._is_hovered:
            return 1.2
        if self._flow_active:
            return 1.8
        if self._flow_start:
            return 1.6
        if self._anim_active:
            return 1.6
        return 1.0

    def _build_tooltip(self) -> str:
        if self.component.layer == "unknown":
            return f"{self.component.name}\nUnknown (미분류 컴포넌트)"
        return f"{self.component.name}\n{self.component.layer}"

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsObject.GraphicsItemChange.ItemScenePositionHasChanged:
            self.position_changed.emit()
        return super().itemChange(change, value)

    def _label_font(self) -> QFont:
        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def _ellipsize_label(self, text: str) -> str:
        metrics = QFontMetrics(self._label_font())
        return metrics.elidedText(text, Qt.TextElideMode.ElideRight, 90)

    def _build_pill_rect(self) -> QRectF:
        metrics = QFontMetrics(self._label_font())
        text_width = metrics.horizontalAdvance(self._display_text)
        width = max(55, min(95, text_width + self._pill_padding * 2))
        height = self._pill_height
        return QRectF(-width / 2, -height / 2, width, height)
