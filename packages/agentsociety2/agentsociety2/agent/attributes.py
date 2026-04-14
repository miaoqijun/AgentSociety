"""Agent属性与状态分离设计。

本模块提供Agent属性和状态的分离设计，这是ABM研究的关键基础设施。

核心概念
========

**属性 (Attributes)**
    Agent的静态特征，初始化后基本不变。
    定义Agent的"本质"，是研究的实验变量。

**状态 (State)**
    Agent的动态变化部分，随仿真演化。
    记录Agent的"行为"，是研究的观测指标。
"""

from __future__ import annotations

import json
from abc import ABC
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar, Type

import json_repair


T = TypeVar("T")


@dataclass
class AgentAttributes(ABC):
    """Agent属性基类。

    属性是Agent的静态特征，定义Agent的"本质"。
    """

    agent_id: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """从字典反序列化。"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """从JSON反序列化。"""
        return cls.from_dict(json_repair.loads(json_str))

    def save(self, path: Path) -> None:
        """保存到文件。"""
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls: Type[T], path: Path) -> T:
        """从文件加载。"""
        return cls.from_json(path.read_text(encoding="utf-8"))


@dataclass
class AgentState(ABC):
    """Agent状态基类。

    状态是Agent的动态变化部分，随仿真演化。
    """

    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """从字典反序列化。"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def to_json(self) -> str:
        """序列化为JSON。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """从JSON反序列化。"""
        return cls.from_dict(json_repair.loads(json_str))

    def update_timestamp(self, tick: int) -> None:
        """更新时间戳。"""
        self.tick = tick
        self.updated_at = datetime.now().isoformat()


@dataclass
class PersonAttributes(AgentAttributes):
    """Person Agent属性。

    定义仿真人的静态特征。
    """

    # 基本信息
    name: str = "Unknown"
    age: int = 25
    gender: str = "unknown"
    occupation: str = ""

    # Big Five人格特质 (0-1)
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5

    # 价值观 (Schwartz理论)
    value_self_transcendence: float = 0.5
    value_self_enhancement: float = 0.5
    value_openness_to_change: float = 0.5
    value_conservation: float = 0.5

    # 认知能力
    cognitive_ability: float = 0.5


@dataclass
class PersonState(AgentState):
    """Person Agent状态。

    定义仿真人的动态变化部分。
    """

    # 情绪状态
    primary_emotion: str = "neutral"
    emotion_intensity: float = 0.5
    emotion_valence: float = 0.0

    # 意图状态
    current_intention: str = ""
    intention_priority: float = 0.0
    intention_confidence: float = 0.0

    # 需求状态 (马斯洛层次)
    physiological_need: float = 0.8
    safety_need: float = 0.8
    belonging_need: float = 0.5
    esteem_need: float = 0.5
    self_actualization: float = 0.3

    # 活动状态
    current_activity: str = "idle"
    activity_duration: int = 0

    # 社会状态
    relationships: dict[str, float] = field(default_factory=dict)

    # 物理状态
    location: str = "home"
    energy: float = 1.0
    health: float = 1.0
    money: float = 100.0

    def get_current_need(self) -> tuple[str, float]:
        """获取当前最紧迫的需求。"""
        needs = {
            "physiological": self.physiological_need,
            "safety": self.safety_need,
            "belonging": self.belonging_need,
            "esteem": self.esteem_need,
            "self_actualization": self.self_actualization,
        }
        return min(needs.items(), key=lambda x: x[1])


class StateManager:
    """状态管理器。

    负责状态的持久化、恢复和历史追踪。
    """

    def __init__(self, workspace: Path, state_class: Type[AgentState]):
        self.workspace = workspace
        self.state_dir = workspace / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_class = state_class
        self._current: Optional[AgentState] = None

    @property
    def current(self) -> AgentState:
        """获取当前状态。"""
        if self._current is None:
            self._current = self.load()
        return self._current

    def load(self) -> AgentState:
        """从文件加载状态。"""
        path = self.state_dir / "current_state.json"
        if path.exists():
            return self.state_class.from_json(path.read_text(encoding="utf-8"))
        return self.state_class()

    def save(self, state: AgentState) -> None:
        """保存当前状态。"""
        self._current = state
        path = self.state_dir / "current_state.json"
        path.write_text(state.to_json(), encoding="utf-8")

    def snapshot(self, tick: int) -> Path:
        """创建状态快照。"""
        state = self.current
        state.update_timestamp(tick)
        path = self.state_dir / f"state_{tick}.json"
        path.write_text(state.to_json(), encoding="utf-8")
        return path

    def history(self, limit: int = 100) -> list[AgentState]:
        """获取历史状态。"""
        snapshots = sorted(self.state_dir.glob("state_*.json"))
        history = []
        for path in snapshots[-limit:]:
            history.append(self.state_class.from_json(path.read_text(encoding="utf-8")))
        return history
