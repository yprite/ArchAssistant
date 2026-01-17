from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

from core.config import LAYER_COLORS
from ui.colors import EDGE_COLOR, STROKE_COLOR


class MinimapView(QGraphicsView):
    def __init__(self, main_view: QGraphicsView, main_scene) -> None:
        super().__init__()
        self._main_view = main_view
        self._main_scene = main_scene
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setInteractive(False)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setFixedSize(180, 180)
        self.setStyleSheet(
            "QGraphicsView { background: rgba(255, 255, 255, 0.75);"
            " border: 1px solid rgba(0, 0, 0, 0.25); border-radius: 10px; }"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(4)
        shadow.setOffset(0, 1)
        shadow_color = QColor(0, 0, 0)
        shadow_color.setAlphaF(0.15)
        shadow.setColor(shadow_color)
        self.setGraphicsEffect(shadow)

        self._viewport_rect: QGraphicsRectItem | None = None
        self._static_built = False
        self._edge_overlay: dict[tuple[str, str], QGraphicsLineItem] = {}
        self._token_item: QGraphicsEllipseItem | None = None

        self._dragging = False
        self._drag_offset = QPointF(0, 0)
        self._full_refresh_timer = QTimer(self)
        self._full_refresh_timer.setSingleShot(True)
        self._full_refresh_timer.setInterval(120)
        self._full_refresh_timer.timeout.connect(self.refresh_full)

        self._viewport_timer = QTimer(self)
        self._viewport_timer.setSingleShot(True)
        self._viewport_timer.setInterval(60)
        self._viewport_timer.timeout.connect(self._update_viewport_rect)

        self.refresh_full()

    def position_in_view(self) -> None:
        margin = 16
        parent = self.parentWidget()
        if not parent:
            return
        x = parent.width() - self.width() - margin
        y = parent.height() - self.height() - margin
        self.move(x, y)

    def schedule_refresh(self) -> None:
        if not self._full_refresh_timer.isActive():
            self._full_refresh_timer.start()

    def schedule_viewport_update(self) -> None:
        if not self._viewport_timer.isActive():
            self._viewport_timer.start()

    def refresh_full(self) -> None:
        self._scene.clear()
        self._viewport_rect = QGraphicsRectItem()
        self._viewport_rect.setZValue(10)
        self._viewport_rect.setPen(QPen(QColor(74, 116, 224, 140), 1.5))
        self._viewport_rect.setBrush(QColor(74, 116, 224, 40))
        self._scene.addItem(self._viewport_rect)
        bounds = self._main_scene.itemsBoundingRect()
        if bounds.isNull():
            return
        self._scene.setSceneRect(
            bounds.adjusted(
                -bounds.width() * 0.1,
                -bounds.height() * 0.1,
                bounds.width() * 0.1,
                bounds.height() * 0.1,
            )
        )
        self._draw_layers()
        self._draw_edges()
        self._draw_nodes()
        self._token_item = QGraphicsEllipseItem(0, 0, 4, 4)
        self._token_item.setBrush(QColor("#3B82F6"))
        self._token_item.setPen(Qt.PenStyle.NoPen)
        self._token_item.setZValue(5)
        self._scene.addItem(self._token_item)
        self._static_built = True
        self._update_viewport_rect()
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        scene_pos = self.mapToScene(event.position().toPoint())
        if self._viewport_rect and self._viewport_rect.contains(scene_pos):
            self._dragging = True
            self._drag_offset = scene_pos - self._viewport_rect.rect().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        self._center_main_view(scene_pos)
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not self._dragging or not self._viewport_rect:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        top_left = scene_pos - self._drag_offset
        rect = QRectF(top_left, self._viewport_rect.rect().size())
        self._viewport_rect.setRect(rect)
        self._center_main_view(rect.center())

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        if not self._dragging:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().enterEvent(event)

    def _draw_layers(self) -> None:
        pen = QPen(STROKE_COLOR)
        pen.setWidthF(0.6)
        pen.setCosmetic(True)
        for items in self._main_scene.layer_backgrounds.values():
            for item in items:
                if isinstance(item, QGraphicsPolygonItem):
                    poly_item = QGraphicsPolygonItem(item.polygon())
                    poly_item.setPen(pen)
                    poly_item.setBrush(Qt.BrushStyle.NoBrush)
                    poly_item.setZValue(-10)
                    self._scene.addItem(poly_item)
                elif isinstance(item, QGraphicsPathItem):
                    path_item = QGraphicsPathItem(item.path())
                    path_item.setPen(pen)
                    path_item.setBrush(Qt.BrushStyle.NoBrush)
                    path_item.setZValue(-10)
                    self._scene.addItem(path_item)

    def _draw_nodes(self) -> None:
        for component_id, item in self._main_scene.component_items.items():
            center = item.sceneBoundingRect().center()
            color = QColor(LAYER_COLORS.get(item.component.layer, "#B5B5B5"))
            dot = QGraphicsEllipseItem(center.x() - 1.5, center.y() - 1.5, 3, 3)
            dot.setBrush(color)
            dot.setPen(Qt.PenStyle.NoPen)
            dot.setZValue(2)
            self._scene.addItem(dot)

    def _draw_edges(self) -> None:
        pen = QPen(EDGE_COLOR)
        pen.setWidthF(0.6)
        pen.setCosmetic(True)
        color = QColor(EDGE_COLOR)
        color.setAlphaF(0.35)
        pen.setColor(color)
        self._edge_overlay.clear()
        for edge in self._main_scene.edge_items:
            if not hasattr(edge, "source_item") or not hasattr(edge, "target_item"):
                continue
            source_center = edge.source_item.sceneBoundingRect().center()
            target_center = edge.target_item.sceneBoundingRect().center()
            line = QGraphicsLineItem(
                source_center.x(), source_center.y(), target_center.x(), target_center.y()
            )
            line.setPen(pen)
            line.setZValue(-20)
            self._scene.addItem(line)
            key = (edge.source_item.component.id, edge.target_item.component.id)
            self._edge_overlay[key] = line

    def _update_viewport_rect(self) -> None:
        viewport_rect = self._main_view.mapToScene(self._main_view.viewport().geometry()).boundingRect()
        if self._viewport_rect:
            self._viewport_rect.setRect(viewport_rect)
        self._update_flow_overlay()

    def _update_flow_overlay(self) -> None:
        for edge in self._main_scene.edge_items:
            key = (edge.source_item.component.id, edge.target_item.component.id)
            line = self._edge_overlay.get(key)
            if not line:
                continue
            in_flow, visited, active = edge.flow_states()
            pen = line.pen()
            if active:
                pen.setColor(QColor("#3B82F6"))
                pen.setWidthF(1.4)
            elif visited:
                pen.setColor(QColor("#60A5FA"))
                pen.setWidthF(1.0)
            elif in_flow:
                pen.setColor(QColor("#93C5FD"))
                pen.setWidthF(0.8)
            else:
                pen.setColor(QColor("#CBD5E1"))
                pen.setWidthF(0.6)
            line.setPen(pen)

        token_pos = self._main_scene.flow_token_pos
        if not self._token_item:
            return
        if token_pos is None:
            self._token_item.setVisible(False)
        else:
            self._token_item.setVisible(True)
            self._token_item.setPos(token_pos.x() - 2, token_pos.y() - 2)

    def _center_main_view(self, scene_pos: QPointF) -> None:
        self._main_view.centerOn(scene_pos)
