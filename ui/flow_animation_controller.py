from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QEasingCurve, QObject, QSequentialAnimationGroup, Signal, QVariantAnimation

from ui.event_token_item import EventTokenItem


@dataclass(frozen=True)
class FlowStep:
    index: int
    source_item: object
    target_item: object
    edge_item: object
    duration_ms: int


class FlowAnimationController(QObject):
    step_changed = Signal(int)
    token_updated = Signal()

    def __init__(self, scene, steps: List[FlowStep]) -> None:
        super().__init__()
        self._scene = scene
        self._steps = steps
        self._group = QSequentialAnimationGroup(self)
        self._group_connected = False
        self._token = EventTokenItem()
        self._token.setVisible(False)
        self._scene.addItem(self._token)
        self._speed = 1.0
        self._build_group()
        self._group.finished.connect(self.stop)

    def play(self) -> None:
        if not self._steps or self._group.animationCount() == 0:
            return
        if self._group.state() == QSequentialAnimationGroup.State.Paused:
            self._group.resume()
            return
        if self._group.state() == QSequentialAnimationGroup.State.Stopped:
            self._group.start()
            return

    def pause(self) -> None:
        if self._group.state() == QSequentialAnimationGroup.State.Running:
            self._group.pause()

    def restart(self) -> None:
        if not self._steps or self._group.animationCount() == 0:
            return
        self._group.stop()
        self._group.setCurrentTime(0)
        self._group.start()

    def step_forward(self) -> None:
        if not self._steps or self._group.animationCount() == 0:
            return
        if self._group.state() == QSequentialAnimationGroup.State.Running:
            self._group.pause()
        current = self._group.currentAnimation()
        index = self._group.indexOfAnimation(current) if current else 0
        if index < 0:
            index = 0
        if index >= len(self._steps):
            return
        self._activate_step(index)
        self._animate_step(index, jump=True)

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.5, min(2.0, speed))
        if self._group.state() != QSequentialAnimationGroup.State.Stopped:
            self._group.stop()
        self._build_group()

    def stop(self) -> None:
        for step in self._steps:
            step.edge_item.set_flow_active(False)
            step.edge_item.set_flow_visited(False)
            step.target_item.set_flow_active(False)
            step.target_item.set_flow_visited(False)
        if self._steps:
            self._steps[0].source_item.set_flow_active(False)
            self._steps[0].source_item.set_flow_visited(False)
        self._token.setVisible(False)
        self._scene.set_flow_token_position(None)
        if self._group.state() != QSequentialAnimationGroup.State.Stopped:
            self._group.stop()

    def _build_group(self) -> None:
        if self._group_connected:
            self._group.currentAnimationChanged.disconnect(self._on_step_changed)
            self._group_connected = False
        if self._group.state() != QSequentialAnimationGroup.State.Stopped:
            self._group.stop()
        self._group.clear()
        if not self._steps:
            return
        for index in range(len(self._steps)):
            anim = QVariantAnimation()
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setDuration(int(self._steps[index].duration_ms / self._speed))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.valueChanged.connect(
                lambda value, idx=index: self._update_token(idx, float(value))
            )
            anim.finished.connect(lambda idx=index: self._mark_visited(idx))
            self._group.addAnimation(anim)
        if self._steps:
            self._steps[0].source_item.set_flow_active(True)
        if self._group.animationCount() > 0:
            self._group.currentAnimationChanged.connect(self._on_step_changed)
            self._group_connected = True

    def _on_step_changed(self, animation) -> None:
        if animation is None:
            return
        index = self._group.indexOfAnimation(animation)
        if index < 0 or index >= len(self._steps):
            return
        self._activate_step(index)
        self.step_changed.emit(index)

    def _activate_step(self, index: int) -> None:
        for step in self._steps:
            step.edge_item.set_flow_active(False)
            step.target_item.set_flow_active(False)
        step = self._steps[index]
        self._token.setVisible(True)
        self._token.setPos(step.source_item.sceneBoundingRect().center())
        step.edge_item.set_flow_active(True)
        step.target_item.set_flow_active(True)

    def _update_token(self, index: int, progress: float) -> None:
        step = self._steps[index]
        path = step.edge_item.path()
        point = path.pointAtPercent(progress)
        self._token.setPos(point)
        self._scene.set_flow_token_position(point)
        self.token_updated.emit()

    def _mark_visited(self, index: int) -> None:
        step = self._steps[index]
        step.edge_item.set_flow_visited(True)
        step.target_item.set_flow_visited(True)

    def _animate_step(self, index: int, jump: bool = False) -> None:
        if jump:
            step = self._steps[index]
            self._token.setVisible(True)
            self._token.setPos(step.target_item.sceneBoundingRect().center())
