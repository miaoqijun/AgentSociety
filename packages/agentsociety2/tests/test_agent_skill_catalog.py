from pathlib import Path

from agentsociety2.agent.base.registry import SkillDescriptor
from agentsociety2.agent.base.runtime import AgentSkillRuntime
from agentsociety2.agent.base.tool_schema import react_tool_schemas
from agentsociety2.env.router_base import _empty_env_skill_catalog, _env_skill_catalog_row


class _Registry:
    def __init__(self) -> None:
        self.skill = SkillDescriptor(
            skill_id="env:MobilitySpace@mobility",
            name="mobility",
            namespace="env:MobilitySpace",
            description="Move around the city.",
            root=Path("."),
            source="env",
            source_label="test",
            script=None,
            hooks={},
        )

    def list_all(self):
        return [self.skill]

    def get(self, skill_id: str):
        return self.skill if skill_id == self.skill.skill_id else None

    def find_by_name(self, name: str):
        return [self.skill] if name == self.skill.name else []

    def read_skill_doc(self, skill_id: str):
        return ""

    def read_skill_file(self, skill_id: str, relative_path: str):
        return ""

    def list_hooks(self, hook_type: str):
        return []


def _tool_schema(name: str) -> dict:
    for tool in react_tool_schemas():
        if tool["function"]["name"] == name:
            return tool["function"]
    raise AssertionError(f"tool not found: {name}")


def test_skill_catalog_exposes_only_skill_name_to_model():
    runtime = AgentSkillRuntime(agent_id=1, registry=_Registry())
    runtime.set_visible_skills(["env:MobilitySpace@mobility"])

    catalog = runtime.skill_catalog()

    assert catalog == [{"name": "mobility", "description": "Move around the city."}]
    assert "skill_id" not in catalog[0]


def test_env_skill_catalog_rows_hide_registry_skill_id(tmp_path: Path):
    skill_dir = tmp_path / "mobility"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: mobility\ndescription: Move around the city.\n---\n",
        encoding="utf-8",
    )

    row = _env_skill_catalog_row(skill_md, module_name="MobilitySpace")

    assert "env:MobilitySpace@mobility" not in row
    assert row == "| mobility | MobilitySpace | Move around the city. |"
    assert "skill_id" not in _empty_env_skill_catalog()


def test_ask_env_schema_requires_variables_for_forced_template_mode():
    ask_env = _tool_schema("ask_env")
    params = ask_env["parameters"]
    variables = params["properties"]["variables"]

    assert "variables" in params["required"]
    assert "template/cache mode" in ask_env["description"]
    assert "Required mapping" in variables["description"]
