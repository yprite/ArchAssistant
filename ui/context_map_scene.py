from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsObject, QGraphicsPathItem, QGraphicsScene

from analysis.bounded_context import BcRelation, BoundedContextAnalysisResult
from ui.colors import TEXT_PRIMARY


@dataclass
class ContextNode:
    bc_id: str
    name: str
    component_count: int
    layers: str
    score: float


class BoundedContextItem(QGraphicsObject):
    clicked = Signal(str)

    def __init__(self, node: ContextNode) -> None:
        super().__init__()
        self.node = node
        self._rect = QRectF(0, 0, 180, 72)
        self._selected = False

    def boundingRect(self) -> QRectF:
        return QRectF(self._rect)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        border = QColor("#4A4A4A")
        if self._selected:
            border = QColor("#4A74E0")
        pen = QPen(border, 1.4)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QColor(240, 242, 247, 220))
        painter.drawRoundedRect(self._rect, 8, 8)
        painter.setPen(TEXT_PRIMARY)
        painter.drawText(
            QRectF(12, 8, 156, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.node.name,
        )
        meta = f"{self.node.component_count} comps | layers {self.node.layers}"
        painter.setPen(QColor("#555555"))
        painter.drawText(
            QRectF(12, 28, 156, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            meta,
        )
        score_text = f"hex {self.node.score:.2f}"
        painter.drawText(
            QRectF(12, 48, 156, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            score_text,
        )

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.clicked.emit(self.node.bc_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()


class BcRelationItem(QGraphicsPathItem):
    def __init__(self, relation: BcRelation) -> None:
        super().__init__()
        self.relation = relation
        self.setZValue(-1)
        self._pen = QPen(QColor("#9A9A9A"), 1.2)
        self._pen.setCosmetic(True)
        if relation.relation_type.value == "partnership":
            self._pen.setStyle(Qt.PenStyle.DashLine)
            self._pen.setColor(QColor("#8B5CF6"))
        elif relation.relation_type.value == "downstream":
            self._pen.setColor(QColor("#4A74E0"))
        self.setPen(self._pen)

    def update_path(self, source: QPointF, target: QPointF) -> None:
        path = QPainterPath()
        path.moveTo(source)
        mid = (source + target) * 0.5
        path.lineTo(mid)
        path.lineTo(target)
        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.pen())
        painter.drawPath(self.path())
        if self.path().elementCount() < 2:
            return
        end = self.path().pointAtPercent(1.0)
        start = self.path().pointAtPercent(0.95)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = 8.0
        p1 = QPointF(
            end.x() - arrow_size * math.cos(angle - math.pi / 6),
            end.y() - arrow_size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            end.x() - arrow_size * math.cos(angle + math.pi / 6),
            end.y() - arrow_size * math.sin(angle + math.pi / 6),
        )
        painter.setBrush(self.pen().color())
        painter.drawPolygon(end, p1, p2)


class ContextMapScene(QGraphicsScene):
    bc_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._items: Dict[str, BoundedContextItem] = {}
        self._relations: List[BcRelationItem] = []
        self._analysis: BoundedContextAnalysisResult | None = None

    def load_analysis(self, result: BoundedContextAnalysisResult) -> None:
        self.clear()
        self._items = {}
        self._relations = []
        self._analysis = result

        nodes = []
        for bc in result.contexts.values():
            node = ContextNode(
                bc_id=bc.id,
                name=bc.name,
                component_count=len(bc.component_ids),
                layers=",".join(sorted(bc.layers_present)),
                score=bc.hexagon_score,
            )
            nodes.append(node)

        positions = _circle_layout(len(nodes), radius=260.0)
        for node, pos in zip(nodes, positions):
            item = BoundedContextItem(node)
            item.setPos(pos)
            item.clicked.connect(self._on_item_clicked)
            self.addItem(item)
            self._items[node.bc_id] = item

        for relation in result.relations:
            item = BcRelationItem(relation)
            self._relations.append(item)
            self.addItem(item)

        self._update_relation_paths()
        self.setSceneRect(self.itemsBoundingRect().adjusted(-120, -120, 120, 120))

    def highlight_bc(self, bc_id: str | None) -> None:
        for item_id, item in self._items.items():
            item.set_selected(item_id == bc_id)

    def _update_relation_paths(self) -> None:
        for relation_item in self._relations:
            src_item = self._items.get(relation_item.relation.source_bc_id)
            tgt_item = self._items.get(relation_item.relation.target_bc_id)
            if not src_item or not tgt_item:
                continue
            source = src_item.sceneBoundingRect().center()
            target = tgt_item.sceneBoundingRect().center()
            relation_item.update_path(source, target)

    def _on_item_clicked(self, bc_id: str) -> None:
        self.highlight_bc(bc_id)
        self.bc_selected.emit(bc_id)


def _circle_layout(count: int, radius: float) -> List[QPointF]:
    if count == 0:
        return []
    angle_step = 2 * math.pi / count
    positions: List[QPointF] = []
    for idx in range(count):
        angle = idx * angle_step - math.pi / 2
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        positions.append(QPointF(x, y))
    return positions
