from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QBrush
from PySide6.QtWidgets import QGraphicsObject

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
        self._violation_active = False
        self._smell_color: QColor | None = None
        self._flash_animation: QPropertyAnimation | None = None
        self._glow_intensity: float = 0.0
        self._is_dragging = False
        self._drag_start_pos = None
        self._invalid_position = False  # 드래그 위치 검증
        self.setToolTip(self._build_tooltip())
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)  # 드래그 가능
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsObject.CacheMode.DeviceCoordinateCache)

    def boundingRect(self) -> QRectF:
        return QRectF(self._pill_rect)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        zoom = painter.worldTransform().m11()
        
        # 정적 섀도우 그리기 (GPU 부하 감소)
        if zoom > 0.3:
            shadow_offset = 2 if not self._is_hovered else 3
            shadow_rect = self._pill_rect.adjusted(1, shadow_offset, 1, shadow_offset)
            shadow_alpha = 25 if self._is_hovered else 15
            if self._glow_intensity > 0:
                glow_color = QColor(self.color)
                glow_color.setAlpha(int(60 * self._glow_intensity))
                glow_rect = self._pill_rect.adjusted(-3, -3, 3, 3)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow_color)
                painter.drawRoundedRect(glow_rect, self._pill_height / 2 + 3, self._pill_height / 2 + 3)
            shadow_color = QColor(0, 0, 0, shadow_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            painter.drawRoundedRect(shadow_rect, self._pill_height / 2, self._pill_height / 2)
        
        # 노드 본체 그리기
        if self._invalid_position:
            # 잘못된 위치: 빨간색 테두리 + 반투명 배경
            pen_color = QColor("#EF4444")
            fill_brush = QColor("#EF4444")
            fill_brush.setAlphaF(0.3)
        elif self._smell_color:
            pen_color = self._smell_color
            fill_brush = self._fill_color
        elif self._violation_active:
            pen_color = QColor("#EF4444")
            fill_brush = self._fill_color
        else:
            pen_color = self._stroke_color
            fill_brush = self._fill_color
        pen = QPen(pen_color, self._current_stroke_width())
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(fill_brush)
        painter.drawRoundedRect(self._pill_rect, self._pill_height / 2, self._pill_height / 2)
        
        # LOD: 줌 레벨에 따른 텍스트 표시
        if zoom > 0.5:
            text_color = QColor("#FFFFFF") if (self._in_flow or self._flow_active) else TEXT_PRIMARY
            painter.setPen(QPen(text_color))
            painter.setFont(self._label_font())
            painter.drawText(self._pill_rect, Qt.AlignmentFlag.AlignCenter, self._display_text)
        elif zoom > 0.25:
            # 축소 시: 간소화된 라벨 (첫 글자만)
            text_color = QColor("#FFFFFF") if (self._in_flow or self._flow_active) else TEXT_PRIMARY
            painter.setPen(QPen(text_color))
            font = self._label_font()
            font.setPointSize(9)
            painter.setFont(font)
            short_label = self._label_text[0] if self._label_text else ""
            painter.drawText(self._pill_rect, Qt.AlignmentFlag.AlignCenter, short_label)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_start_pos = event.pos()
            # 클릭 피드백: 살짝 스케일 다운
            self.setScale(0.96)
        self.clicked.emit(self.component)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_start_pos is not None:
            # 드래그 감지: 약간의 이동이 있으면 드래그로 판정
            delta = event.pos() - self._drag_start_pos
            if delta.manhattanLength() > 5:
                self._is_dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                
                # 레이어 위치 검증
                pos = self.scenePos()
                detected_layer = self._detect_layer_at_position(pos)
                expected_layer = self.component.layer
                
                # 위치가 올바른지 확인
                was_invalid = self._invalid_position
                self._invalid_position = (detected_layer != expected_layer)
                
                if was_invalid != self._invalid_position:
                    self.update()  # 상태 변경 시만 리페인트
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
            # 스케일 복원
            self.setScale(1.04 if self._is_hovered else 1.0)
            if self._is_dragging:
                self._is_dragging = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                # 잘못된 위치면 상태 유지 (빨간색 표시 계속)
                # 사용자가 올바른 위치로 이동하면 자동으로 복구됨
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self._is_hovered = True
        self._update_glow(True)
        self.setScale(1.04)
        self.setCursor(Qt.CursorShape.OpenHandCursor)  # 드래그 가능 표시
        self.update()
        self.hovered.emit(self.component, True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._is_hovered = False
        self._update_glow(False)
        self.setScale(1.0)
        self.setCursor(Qt.CursorShape.ArrowCursor)
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
            self._glow_intensity = 1.0  # 글로우 효과
            self.setScale(1.06)
        elif self._flow_visited:
            self._fill_color = QColor(FLOW_VISITED)
            self._fill_color.setAlphaF(0.85)
            self._glow_intensity = 0.5
            self.setScale(1.0)
        elif self._in_flow:
            self._fill_color = QColor(FLOW_IN)
            self._fill_color.setAlphaF(0.7)
            self._glow_intensity = 0.3
            self.setScale(1.0)
        else:
            self._fill_color = QColor(self.color).darker(110)
            self._fill_color.setAlphaF(0.26)
            self._glow_intensity = 0.0
            self.setScale(1.0)
        self.update()

    def set_violation_active(self, active: bool) -> None:
        self._violation_active = active
        self.update()

    def set_smell_active(self, color: QColor | None) -> None:
        self._smell_color = color
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
        self._glow_intensity = 1.0 if hovered else 0.0
        self.update()

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

    def _detect_layer_at_position(self, pos) -> str:
        """좌표 기반으로 현재 위치의 레이어를 감지 (관대한 경계)"""
        import math
        
        # 중심에서의 거리 계산
        distance = math.hypot(pos.x(), pos.y())
        
        # 레이어별 반경 (LayoutConfig 기반)
        domain_radius = self.layout.domain_radius
        application_radius = self.layout.application_radius
        ports_radius = self.layout.ports_radius
        adapter_radius = self.layout.adapter_radius
        
        # 관대한 마진 (50px) - 경계 근처에서 더 여유있게 판정
        margin = 50
        
        # 거리 기반 레이어 판정 (간소화)
        if distance <= domain_radius + margin:
            return "domain"
        elif distance <= application_radius + margin:
            return "application"
        elif distance <= ports_radius + margin:
            # 포트 레이어: inbound/outbound 통합 (어느 쪽이든 포트는 OK)
            layer = self.component.layer
            if layer in ("inbound_port", "outbound_port"):
                return layer  # 현재 레이어 유지
            return "inbound_port"  # 기본값
        elif distance <= adapter_radius + margin:
            # 어댑터 레이어: inbound/outbound 통합
            layer = self.component.layer
            if layer in ("inbound_adapter", "outbound_adapter"):
                return layer  # 현재 레이어 유지
            return "inbound_adapter"  # 기본값
        else:
            return "unknown"

    def reset_invalid_position(self) -> None:
        """잘못된 위치 상태 리셋"""
        if self._invalid_position:
            self._invalid_position = False
            # 원래 색상으로 복원
            self._fill_color = QColor(self.color).darker(110)
            self._fill_color.setAlphaF(0.26)
            self.update()

