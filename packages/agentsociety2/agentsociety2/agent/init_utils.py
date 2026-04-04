"""PersonAgent 初始化工具。

提供动态的 Agent 创建工厂，自动发现可用技能及其 schema。

Example:
    from agentsociety2.agent.init_utils import (
        create_person_agent, PersonInitConfig, discover_skill_schemas
    )

    schemas = discover_skill_schemas()
    agent = create_person_agent(PersonInitConfig(
        agent_id=1, name="Alice", profile={"age": 25}
    ).set_state("needs", "needs.json", {"satiety": 0.3}))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from agentsociety2.agent.person import PersonAgent
from agentsociety2.agent.skills import SkillInfo, get_skill_registry


@dataclass
class PersonInitConfig:
    """PersonAgent 初始化配置。

    动态发现可用技能，支持任意技能的初始化。

    :ivar agent_id: Agent 唯一标识。
    :ivar name: 显示名称。
    :ivar profile: 画像信息。
    :ivar skill_states: 技能初始状态，格式为 {skill_name: {filename: content}}。
    :ivar capability_kwargs: 能力参数（max_tool_rounds, llm_model 等）。
    :ivar force_overwrite: 是否强制覆盖已存在的状态文件。
    """

    agent_id: int = 1
    name: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    skill_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    capability_kwargs: dict[str, Any] = field(default_factory=dict)
    force_overwrite: bool = False

    def set_state(self, skill_name: str, filename: str, content: Any) -> "PersonInitConfig":
        """设置单个技能的状态文件。

        :param skill_name: 技能名称。
        :param filename: 文件名（相对 workspace 根）。
        :param content: 文件内容（dict 会自动转 JSON）。
        :return: self，支持链式调用。
        """
        if skill_name not in self.skill_states:
            self.skill_states[skill_name] = {}
        self.skill_states[skill_name][filename] = content
        return self

    def to_init_state(self) -> dict[str, Any]:
        """转换为 PersonAgent 的 init_state 格式。

        :return: init_state 字典。
        :rtype: dict[str, Any]
        """
        workspace_seed: dict[str, Any] = {}
        for skill_name, files in self.skill_states.items():
            for filename, content in files.items():
                workspace_seed[filename] = content
        return {
            "init_state_force": self.force_overwrite,
            "workspace_seed": workspace_seed,
        }


def get_available_skills() -> list[SkillInfo]:
    """获取所有可用的技能列表。

    :return: 启用状态的技能列表。
    :rtype: list[SkillInfo]
    """
    return get_skill_registry().list_enabled()


def get_skill_outputs(skill_name: str) -> list[str]:
    """获取技能的输出文件列表。

    :param skill_name: 技能名称。
    :return: 输出文件名列表，技能不存在时返回空列表。
    :rtype: list[str]
    """
    info = get_skill_registry().get_skill_info(skill_name, load_content=False)
    return list(info.outputs) if info else []


def discover_skill_schemas() -> dict[str, list[str]]:
    """发现所有技能及其输出文件。

    :return: 字典 {skill_name: [output_files]}。
    :rtype: dict[str, list[str]]
    """
    return {
        info.name: list(info.outputs)
        for info in get_available_skills()
        if info.outputs
    }


def create_person_agent(config: PersonInitConfig) -> PersonAgent:
    """创建具有初始状态的 PersonAgent。

    :param config: 初始化配置。
    :type config: PersonInitConfig
    :return: 配置好的 PersonAgent 实例。
    :rtype: PersonAgent
    """
    return PersonAgent(
        id=config.agent_id,
        profile=config.profile,
        name=config.name or None,
        init_state=config.to_init_state(),
        **config.capability_kwargs,
    )


def init_needs_state(
    satiety: float = 0.7,
    energy: float = 0.3,
    safety: float = 0.9,
    social: float = 0.8,
) -> dict[str, Any]:
    """生成 needs.json 内容。

    自动计算 current_need 和默认阈值。

    :param satiety: 饱腹感 (0-1)。
    :param energy: 精力 (0-1)。
    :param safety: 安全感 (0-1)。
    :param social: 社交满足 (0-1)。
    :return: needs.json 格式的字典。
    :rtype: dict[str, Any]
    """
    values = {"satiety": satiety, "energy": energy, "safety": safety, "social": social}
    return {
        **values,
        "current_need": min(values, key=values.get),
        "thresholds": {"satiety": 0.2, "energy": 0.2, "safety": 0.2, "social": 0.3},
        "can_interrupt": {"satiety": True, "energy": True, "safety": False, "social": False},
    }


def init_personality_state(
    openness: float = 0.5,
    conscientiousness: float = 0.5,
    extraversion: float = 0.5,
    agreeableness: float = 0.5,
    neuroticism: float = 0.3,
    description: str = "",
) -> dict[str, Any]:
    """生成 personality.json 内容。

    :param openness: 开放性 (0-1)。
    :param conscientiousness: 尽责性 (0-1)。
    :param extraversion: 外向性 (0-1)。
    :param agreeableness: 宜人性 (0-1)。
    :param neuroticism: 神经质 (0-1)。
    :param description: 人格描述，为空时自动生成。
    :return: personality.json 格式的字典。
    :rtype: dict[str, Any]
    """
    traits = {
        "openness": openness,
        "conscientiousness": conscientiousness,
        "extraversion": extraversion,
        "agreeableness": agreeableness,
        "neuroticism": neuroticism,
    }
    if not description:
        parts = []
        if extraversion > 0.6:
            parts.append("outgoing")
        elif extraversion < 0.4:
            parts.append("reserved")
        if neuroticism > 0.5:
            parts.append("emotionally sensitive")
        elif neuroticism < 0.3:
            parts.append("calm and stable")
        if openness > 0.6:
            parts.append("curious")
        description = f"A person who is {', '.join(parts) or 'balanced'}."
    return {"traits": traits, "personality_description": description}


def init_emotion_state(
    primary: str = "Neutral",
    valence: float = 0.0,
    arousal: float = 0.5,
    intensities: Optional[dict[str, int]] = None,
    mood_valence: float = 0.0,
    mood_arousal: float = 0.5,
    mood_stability: float = 0.7,
) -> dict[str, Any]:
    """生成 emotion.json 内容（含 Mood 层）。

    :param primary: 主要情绪标签。
    :param valence: 情绪效价 (-1 到 1)。
    :param arousal: 情绪唤醒度 (0-1)。
    :param intensities: 情绪强度字典，默认为中性值。
    :param mood_valence: 心境效价 (-1 到 1)。
    :param mood_arousal: 心境唤醒度 (0-1)。
    :param mood_stability: 心境稳定性 (0-1)。
    :return: emotion.json 格式的字典。
    :rtype: dict[str, Any]
    """
    return {
        "primary": primary,
        "valence": valence,
        "arousal": arousal,
        "mood": {
            "valence": mood_valence,
            "arousal": mood_arousal,
            "stability": mood_stability,
        },
        "intensities": intensities or {
            "sadness": 3, "joy": 3, "fear": 2,
            "disgust": 1, "anger": 1, "surprise": 2,
        },
        "note": "",
    }


def create_agent_with_needs(
    agent_id: int,
    satiety: float,
    energy: float,
    name: str = "",
    profile: Optional[dict[str, Any]] = None,
) -> PersonAgent:
    """创建具有特定需求状态的 Agent。

    仅当 needs 技能可用时才设置。

    :param agent_id: Agent ID。
    :param satiety: 饱腹感。
    :param energy: 精力。
    :param name: 显示名称。
    :param profile: 画像信息。
    :return: PersonAgent 实例。
    :rtype: PersonAgent
    """
    config = PersonInitConfig(
        agent_id=agent_id,
        name=name,
        profile=profile or {},
    )
    if "needs" in discover_skill_schemas():
        config.set_state("needs", "needs.json", init_needs_state(satiety=satiety, energy=energy))
    return create_person_agent(config)


def create_agent_with_personality(
    agent_id: int,
    extraversion: float,
    neuroticism: float,
    name: str = "",
    profile: Optional[dict[str, Any]] = None,
) -> PersonAgent:
    """创建具有特定人格的 Agent。

    仅当 personality 技能可用时才设置。

    :param agent_id: Agent ID。
    :param extraversion: 外向性。
    :param neuroticism: 神经质。
    :param name: 显示名称。
    :param profile: 画像信息。
    :return: PersonAgent 实例。
    :rtype: PersonAgent
    """
    config = PersonInitConfig(
        agent_id=agent_id,
        name=name,
        profile=profile or {},
    )
    schemas = discover_skill_schemas()

    if "personality" in schemas:
        config.set_state(
            "personality", "personality.json",
            init_personality_state(extraversion=extraversion, neuroticism=neuroticism),
        )

    if "cognition" in schemas:
        emotion_valence = 0.3 if extraversion > 0.5 else -0.1
        config.set_state(
            "cognition", "emotion.json",
            init_emotion_state(
                primary="Hope" if extraversion > 0.5 else "Distress",
                valence=emotion_valence,
                mood_valence=emotion_valence * 0.5,
            ),
        )

    return create_person_agent(config)
