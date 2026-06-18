import json
from datetime import datetime

import pytest

from agentsociety2.agent.person import PersonAgent


class _FakeEnv:
    def __init__(self, run_dir):
        self.run_dir = run_dir
        self.env_modules = []
        self.ask_calls = []

    async def get_world_description(self):
        return "Fake test world."

    async def ask(self, ctx, instruction, readonly=True, template_mode=False, **kwargs):
        self.ask_calls.append(
            {
                "ctx": ctx,
                "instruction": instruction,
                "readonly": readonly,
                "template_mode": template_mode,
                "extra": kwargs,
            }
        )
        return ctx, f"answered:{instruction}"


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name, arguments):
        self.id = f"call_{name}"
        self.type = "function"
        self.function = _FakeFunction(name, json.dumps(arguments))


class _FakeMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeChoice:
    def __init__(self, output):
        if isinstance(output, tuple):
            name, arguments = output
            self.message = _FakeMessage(tool_calls=[_FakeToolCall(name, arguments)])
        else:
            self.message = _FakeMessage(str(output))


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeLLMRouter:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.messages = []

    async def dispatch(self, **kwargs):
        self.messages.append(kwargs["messages"])
        self.calls = getattr(self, "calls", [])
        self.calls.append(kwargs)
        if not self.outputs:
            raise RuntimeError("no fake LLM outputs remaining")
        return _FakeResponse(self.outputs.pop(0))


def _tool(name, **arguments):
    return (name, arguments)


def _read_jsonl(path):
    paths = [path]
    if not path.exists() and path.name == "events.jsonl":
        run_dir = path.parents[3]
        paths = sorted((run_dir / "trace").glob("trace_*.jsonl"))
    return [
        json.loads(line)
        for item in paths
        for line in item.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_hook_skill(tmp_path, name="hooked"):
    skill_root = tmp_path / "custom" / "skills" / name
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        "description: test lifecycle hooks\n"
        "hooks:\n"
        "  pre_step: scripts/pre.py\n"
        "  post_step: scripts/post.py\n"
        "---\n"
        "# Hooked\n",
        encoding="utf-8",
    )
    (scripts / "pre.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "root = Path(os.environ['AGENT_WORK_DIR'])\n"
        "(root / 'state').mkdir(exist_ok=True)\n"
        "(root / 'state' / 'pre_hook.txt').write_text('pre', encoding='utf-8')\n"
        "print('pre ok')\n",
        encoding="utf-8",
    )
    (scripts / "post.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "root = Path(os.environ['AGENT_WORK_DIR'])\n"
        "(root / 'state').mkdir(exist_ok=True)\n"
        "(root / 'state' / 'post_hook.txt').write_text('post', encoding='utf-8')\n"
        "print('post ok')\n",
        encoding="utf-8",
    )
    return skill_root


def _write_sleep_guidance_story(workspace):
    story_dir = workspace / "state" / "daily_guidance" / "2000-01-01"
    story_dir.mkdir(parents=True, exist_ok=True)
    (story_dir / "story.yaml").write_text(
        "story_id: test\n"
        "date: '2000-01-01'\n"
        "status: ready\n"
        "segments:\n"
        "- id: sleep_night\n"
        "  start: 00:00\n"
        "  end: 07:00\n"
        "  activity: sleep\n"
        "  location_policy: home_aoi\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_person_agent_slice_a_workspace_and_trace(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=7,
        profile={"name": "Alice", "occupation": "tester"},
        max_react_turns=3,
        default_activated_skill_ids=["built-in@daily-guidance"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("write", path="state/react.txt", content="done"),
            _tool("finish", final="react done"),
        ]
    )

    await agent.init(env)
    agent._workspace.write_text(  # noqa: SLF001
        "state/custom.json",
        json.dumps({"status": "seeded"}),
    )
    agent._workspace.write_text("notes.txt", "hello")  # noqa: SLF001
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0007"
    assert result == "react done"
    assert not (workspace / "agent_config.json").exists()
    assert not (workspace / "profile.json").exists()
    assert not (workspace / "profile.md").exists()
    assert not (workspace / "state" / "agent_state.json").exists()
    agent_json = json.loads((workspace / "AGENT.json").read_text(encoding="utf-8"))
    assert agent_json["agent_id"] == 7
    assert agent_json["profile"]["occupation"] == "tester"
    assert agent_json["current_time"] == "2026-01-02T09:30:00"
    assert "state" not in agent_json
    assert "config" not in agent_json
    assert (workspace / "state" / "react.txt").read_text(encoding="utf-8") == "done"
    assert json.loads((workspace / "state" / "custom.json").read_text()) == {
        "status": "seeded"
    }
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "hello"

    events = _read_jsonl(workspace / ".runtime" / "events.jsonl")
    names = [event["name"] for event in events]
    assert "agent.init" in names
    assert "agent.step" in names
    assert "react.loop" in names
    assert names.count("react.turn") == 2
    assert "react.tool" in names
    assert "llm.completion" in names

    tool_span = next(
        event
        for event in events
        if event["name"] == "react.tool"
        and event["attributes"].get("react.action") == "write"
    )
    react_write = next(
        event
        for event in events
        if event["name"] == "workspace.write_text"
        and event["attributes"].get("workspace.path") == "state/react.txt"
    )
    assert react_write["parent_span_id"] == tool_span["span_id"]

    assert "built-in@daily-guidance" in agent_json["skills"]["visible"]

    llm_router = agent._dispatcher  # noqa: SLF001
    system_prompt = llm_router.messages[0][0]["content"]
    user_prompt = llm_router.messages[0][1]["content"]
    assert "<world>" in system_prompt
    assert "</agent>" not in system_prompt
    assert "<agent>" in user_prompt
    assert "<available_skills>" in system_prompt
    assert '<skill_content name="daily-guidance">' in system_prompt
    assert "You are Alice, a simulated person" in system_prompt
    assert "<identity>" in system_prompt
    assert "<prompt_guide>" in system_prompt
    assert "<decision_workflow>" in system_prompt
    assert "<behavior>" in system_prompt
    assert "<instruction>" not in system_prompt
    assert system_prompt.index("<identity>") < system_prompt.index("<world>")
    assert system_prompt.index("<world>") < system_prompt.index("<available_skills>")
    assert "<tool_policy>" not in system_prompt
    assert "<name>daily-guidance</name>" in system_prompt
    assert "<file>scripts/daily_guidance.py</file>" in system_prompt
    tool_names = {
        item["function"]["name"]
        for item in llm_router.calls[0]["tools"]
    }
    assert {"read", "write", "append", "list", "grep", "finish"} <= tool_names
    assert "workspace_read" not in tool_names
    assert "todo_list" in tool_names
    assert "<recent_observations>" in user_prompt
    assert "<memory_context>" in user_prompt
    assert "<todo_context>" in user_prompt
    assert "<workspace_files>" not in user_prompt
    assert user_prompt.strip().endswith("</agent>")
    todo_state = json.loads((workspace / "TODO.json").read_text())
    assert todo_state["todos"] == []
    assert (workspace / "MEMORY.md").exists()
    assert (workspace / "memory" / "episodes.jsonl").exists()


@pytest.mark.asyncio
async def test_person_agent_read_maps_same_agent_absolute_workspace_path(tmp_path):
    env = _FakeEnv(tmp_path)
    stale_path = tmp_path / "old_run" / "agents" / "agent_0007" / "AGENT.json"
    agent = PersonAgent(
        id=7,
        profile={"name": "Alice", "occupation": "tester"},
        max_react_turns=2,
        default_activated_skill_ids=["built-in@daily-guidance"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("read", path=str(stale_path)),
            _tool("finish", final="done"),
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert result == "done"
    workspace = tmp_path / "agents" / "agent_0007"
    events = _read_jsonl(workspace / ".runtime" / "events.jsonl")
    read_span = next(
        event for event in events if event["name"] == "workspace.read_text"
    )
    assert read_span["attributes"]["workspace.path"] == str(stale_path)
    assert read_span["attributes"]["workspace.normalized_path"] == "AGENT.json"
    assert read_span["attributes"]["result.size"] > 0


@pytest.mark.asyncio
async def test_person_agent_ask_uses_react_finish(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=3, profile={"name": "Bob"})
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("finish", final="agent answer")]
    )
    await agent.init(env)

    answer = await agent.ask("status?", readonly=True)

    assert answer == "agent answer"
    assert env.ask_calls == []
    workspace = tmp_path / "agents" / "agent_0003"
    names = [
        event["name"]
        for event in _read_jsonl(workspace / ".runtime" / "events.jsonl")
    ]
    assert "agent.ask" in names
    assert "react.loop" in names
    system_prompt = agent._dispatcher.messages[0][0]["content"]  # noqa: SLF001
    user_prompt = agent._dispatcher.messages[0][1]["content"]  # noqa: SLF001
    assert "You are Bob, a simulated person" in system_prompt
    assert "<instruction>" not in system_prompt
    tool_names = {
        item["function"]["name"]
        for item in agent._dispatcher.calls[0]["tools"]  # noqa: SLF001
    }
    assert "todo_list" in tool_names
    assert "memory_recent" in tool_names
    assert "memory_search" in tool_names
    assert "memory_range" in tool_names
    assert "memory_read" in tool_names
    assert "write" not in tool_names
    assert "append" not in tool_names
    assert "todo_add" not in tool_names
    assert "deactivate_skill" in tool_names
    assert "execute_skill_script" in tool_names
    assert "<question>" in user_prompt
    assert "<memory_context>" in user_prompt
    assert "<todo_context>" in user_prompt
    assert "status?" in user_prompt
    assert '"readonly": true' in user_prompt


@pytest.mark.asyncio
async def test_questionnaire_routes_through_agent_ask(tmp_path):
    """Questionnaire must use the standard ask() ReAct loop and read finish(answer=...)."""
    from agentsociety2.society.models import QuestionItem
    from agentsociety2.society.questionnaire import Questionnaire, QuestionnaireRunner

    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=5, profile={"name": "Eve"})
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("finish", answer='{"reason": "tired", "answer": "sleep"}')]
    )
    await agent.init(env)

    questionnaire = Questionnaire(
        questionnaire_id="survey_1",
        title="Sleep survey",
        questions=[
            QuestionItem(
                id="q1",
                prompt="What are you doing right now?",
                response_type="choice",
                choices=["sleep", "work", "leisure"],
            )
        ],
    )
    result = await QuestionnaireRunner().run(
        questionnaire,
        [agent],
        t=datetime(2026, 1, 2, 1, 0, 0),
        step_count=0,
    )

    answer = result.responses[0].answers[0]
    assert answer.parse_success
    assert answer.parsed_value == "sleep"
    assert answer.reason == "tired"
    # Routed through agent.ask (one ReAct completion), with the question as <question>.
    assert len(agent._dispatcher.calls) == 1  # noqa: SLF001
    user_content = agent._dispatcher.messages[0][1]["content"]  # noqa: SLF001
    assert "<question>" in user_content
    assert "What are you doing right now?" in user_content


@pytest.mark.asyncio
async def test_questionnaire_retries_run_in_parallel(tmp_path):
    """Failed choice answers for multiple agents are retried concurrently."""
    import asyncio
    from agentsociety2.society.models import QuestionItem
    from agentsociety2.society.questionnaire import Questionnaire, QuestionnaireRunner

    env = _FakeEnv(tmp_path)
    # Shared across both agents' dispatchers to measure retry-phase concurrency.
    state = {"retry_inflight": 0, "peak_retry": 0}

    class _CountingRouter:
        def __init__(self, outputs):
            self.outputs = list(outputs)

        async def dispatch(self, **kwargs):
            is_retry = any(
                "INVALID PREVIOUS ANSWER" in str(m)
                for m in kwargs.get("messages", [])
            )
            if is_retry:
                state["retry_inflight"] += 1
                state["peak_retry"] = max(
                    state["peak_retry"], state["retry_inflight"]
                )
                await asyncio.sleep(0.05)  # widen the overlap window
                state["retry_inflight"] -= 1
            if not self.outputs:
                raise RuntimeError("no fake outputs remaining")
            return _FakeResponse(self.outputs.pop(0))

    def make_agent(aid, name):
        ag = PersonAgent(id=aid, profile={"name": name})
        # initial ask -> invalid choice ("maybe"); retry ask -> valid "sleep"
        ag._dispatcher = _CountingRouter(  # noqa: SLF001
            [
                _tool("finish", answer="maybe"),
                _tool("finish", answer='{"reason":"r","answer":"sleep"}'),
            ]
        )
        return ag

    agents = [make_agent(1, "A"), make_agent(2, "B")]
    for a in agents:
        await a.init(env)

    questionnaire = Questionnaire(
        questionnaire_id="daily_mobility_intention_slot_0",
        title="t",
        questions=[
            QuestionItem(
                id="primary_intention",
                prompt="What are you doing right now?",
                response_type="choice",
                choices=["sleep", "work", "leisure"],
            )
        ],
    )
    result = await QuestionnaireRunner().run(
        questionnaire,
        agents,
        t=datetime(2026, 1, 2, 1, 0, 0),
        step_count=0,
    )

    assert [r.answers[0].parsed_value for r in result.responses] == ["sleep", "sleep"]
    # Both agents' retries overlapped (gathered together), not run sequentially.
    assert state["peak_retry"] >= 2


@pytest.mark.asyncio
async def test_person_agent_todo_feature_gate_can_disable_prompt_and_tools(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=16,
        profile={"name": "Nora"},
        enable_todo_list=False,
        max_react_turns=1,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("finish", final="done")]
    )

    await agent.init(env)
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0016"
    system_prompt = agent._dispatcher.messages[0][0]["content"]  # noqa: SLF001
    user_prompt = agent._dispatcher.messages[0][1]["content"]  # noqa: SLF001
    tool_names = {
        item["function"]["name"]
        for item in agent._dispatcher.calls[0]["tools"]  # noqa: SLF001
    }
    assert "todo_list" not in tool_names
    assert "<todo_context>" not in user_prompt
    assert "<todo_context>" not in system_prompt
    assert "todo_add" not in system_prompt
    assert not (workspace / "TODO.json").exists()


@pytest.mark.asyncio
async def test_person_agent_memory_feature_gate_can_disable_prompt_and_tools(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=20,
        profile={"name": "Rae"},
        enable_memory=False,
        max_react_turns=1,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("finish", final="done")]
    )

    await agent.init(env)
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0020"
    system_prompt = agent._dispatcher.messages[0][0]["content"]  # noqa: SLF001
    user_prompt = agent._dispatcher.messages[0][1]["content"]  # noqa: SLF001
    tool_names = {
        item["function"]["name"]
        for item in agent._dispatcher.calls[0]["tools"]  # noqa: SLF001
    }
    assert "memory_recent" not in tool_names
    assert "memory_search" not in tool_names
    assert "<memory_context>" not in user_prompt
    assert "<memory_context>" not in system_prompt
    assert "memory_recent" not in system_prompt
    assert not (workspace / "memory" / "episodes.jsonl").exists()


@pytest.mark.asyncio
async def test_person_agent_todo_tool_disabled_by_feature_gate(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=17,
        profile={"name": "Omar"},
        enable_todo_list=False,
        max_react_turns=1,
    )

    await agent.init(env)
    result = await agent.dispatch_react_tool(  # noqa: SLF001
        "todo_add",
        {"title": "should not write"},
    )

    workspace = tmp_path / "agents" / "agent_0017"
    assert result.ok is False
    assert result.observation == "todo_list feature is disabled"
    assert not (workspace / "TODO.json").exists()


@pytest.mark.asyncio
async def test_person_agent_memory_tools(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=21, profile={"name": "Sol"})

    await agent.init(env)
    store = agent._ensure_memory_store()  # noqa: SLF001
    written = store.append_episodes(
        [
            {
                "type": "commitment",
                "importance": 0.8,
                "keywords": ["Alice", "proposal"],
                "text": "Promised Alice to review her proposal.",
            }
        ],
        tick=5,
        t=datetime(2026, 1, 2, 9, 30),
        step_count=1,
    )

    search = await agent.dispatch_react_tool(  # noqa: SLF001
        "memory_search",
        {"query": "Alice", "limit": 5},
    )
    read = await agent.dispatch_react_tool(  # noqa: SLF001
        "memory_read",
        {"ids": [written[0]["id"]]},
    )
    ranged = await agent.dispatch_react_tool(  # noqa: SLF001
        "memory_range",
        {"start_step": 1, "end_step": 1},
    )

    assert search.ok is True
    assert search.data["episodes"][0]["id"] == written[0]["id"]
    assert read.data["episodes"][0]["text"].startswith("Promised Alice")
    assert ranged.data["episodes"][0]["id"] == written[0]["id"]


@pytest.mark.asyncio
async def test_person_agent_workspace_cannot_mutate_core_memory_files(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=211, profile={"name": "Sol"})

    await agent.init(env)
    workspace = tmp_path / "agents" / "agent_0211"
    before = (workspace / "MEMORY.md").read_text(encoding="utf-8")
    write = await agent.dispatch_react_tool(  # noqa: SLF001
        "write",
        {"path": "MEMORY.md", "content": "# broken"},
    )
    append = await agent.dispatch_react_tool(  # noqa: SLF001
        "append",
        {"path": "./memory/episodes.jsonl", "content": "broken\n"},
    )

    assert write.ok is True
    assert write.data["core_owned"] is True
    assert write.data["noop"] is True
    assert append.ok is True
    assert append.data["core_owned"] is True
    assert append.data["noop"] is True
    assert (workspace / "MEMORY.md").read_text(encoding="utf-8") == before
    assert (workspace / "memory" / "episodes.jsonl").read_text(encoding="utf-8") == ""


@pytest.mark.asyncio
async def test_person_agent_workspace_cannot_mutate_runtime_state_files(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=212, profile={"name": "Mira"})

    await agent.init(env)
    workspace = tmp_path / "agents" / "agent_0212"
    agent_json_before = (workspace / "AGENT.json").read_text(encoding="utf-8")
    state_path = workspace / "state" / "daily_guidance" / "2000-01-01" / "story.yaml"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("runtime: true\n", encoding="utf-8")

    write = await agent.dispatch_react_tool(  # noqa: SLF001
        "write",
        {"path": "AGENT.json", "content": "{}"},
    )
    append = await agent.dispatch_react_tool(  # noqa: SLF001
        "append",
        {
            "path": "state/daily_guidance/2000-01-01/story.yaml",
            "content": "model: should-not-write\n",
        },
    )

    assert write.ok is True
    assert write.data["core_owned"] is True
    assert write.data["noop"] is True
    assert append.ok is True
    assert append.data["core_owned"] is True
    assert append.data["noop"] is True
    assert (workspace / "AGENT.json").read_text(encoding="utf-8") == agent_json_before
    assert state_path.read_text(encoding="utf-8") == "runtime: true\n"


@pytest.mark.asyncio
async def test_person_agent_todo_add_preserves_metadata_location(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=18, profile={"name": "Pia"})

    await agent.init(env)
    result = await agent.dispatch_react_tool(  # noqa: SLF001
        "todo_add",
        {
            "title": "go to work",
            "kind": "work",
            "priority": 0.9,
            "metadata": {"location": {"type": "aoi", "id": "work_aoi"}},
        },
    )

    assert result.ok is True
    todo = result.data["todo"]
    assert todo["metadata"]["location"]["id"] == "work_aoi"
    workspace = tmp_path / "agents" / "agent_0018"
    state = json.loads((workspace / "TODO.json").read_text())
    assert state["todos"][0]["metadata"]["location"]["type"] == "aoi"


@pytest.mark.asyncio
async def test_person_agent_todo_add_normalizes_short_due_time(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=180, profile={"name": "Pia"})

    await agent.init(env)
    agent._current_time = datetime(2000, 1, 1, 0, 0, 0)  # noqa: SLF001
    result = await agent.dispatch_react_tool(  # noqa: SLF001
        "todo_add",
        {"title": "wake up", "kind": "sleep", "due": "07:00"},
    )

    assert result.ok is True
    assert result.data["todo"]["due"] == "2000-01-01T07:00:00"


@pytest.mark.asyncio
async def test_person_agent_todo_start_and_complete(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(id=19, profile={"name": "Quinn"})

    await agent.init(env)
    first = (
        await agent.dispatch_react_tool("todo_add", {"title": "first"})  # noqa: SLF001
    ).data["todo"]
    second = (
        await agent.dispatch_react_tool("todo_add", {"title": "second"})  # noqa: SLF001
    ).data["todo"]

    await agent.dispatch_react_tool("todo_start", {"todo_id": first["id"]})  # noqa: SLF001
    started = await agent.dispatch_react_tool(  # noqa: SLF001
        "todo_start",
        {"todo_id": second["id"]},
    )
    state = started.data["state"]
    statuses = {todo["id"]: todo["status"] for todo in state["todos"]}
    assert state["active_todo_id"] == second["id"]
    assert statuses[first["id"]] == "pending"
    assert statuses[second["id"]] == "active"

    completed = await agent.dispatch_react_tool(  # noqa: SLF001
        "todo_complete",
        {"todo_id": second["id"], "outcome": "finished"},
    )
    assert completed.data["state"]["active_todo_id"] is None
    assert completed.data["todo"]["status"] == "done"
    assert completed.data["todo"]["notes"] == "finished"


@pytest.mark.asyncio
async def test_person_agent_react_ask_env_supports_template_mode(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=5,
        profile={"name": "Dana"},
        max_react_turns=2,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool(
                "ask_env",
                instruction="move to {place}",
                readonly=False,
                template_mode=True,
                ctx={"variables": {"place": "library"}},
                variables={"speed": "slow"},
            ),
            _tool("finish", final="env asked"),
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert result == "env asked"
    assert env.ask_calls[-1]["instruction"] == "move to {place}"
    assert env.ask_calls[-1]["readonly"] is False
    assert env.ask_calls[-1]["template_mode"] is True
    assert env.ask_calls[-1]["ctx"]["variables"] == {
        "place": "library",
        "speed": "slow",
    }
    assert env.ask_calls[-1]["ctx"]["agent_id"] == 5


@pytest.mark.asyncio
async def test_person_agent_react_ask_env_readonly_defaults_false(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=6,
        profile={"name": "Evan"},
        max_react_turns=2,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("ask_env", instruction="do something"),
            _tool("finish", final="done"),
        ]
    )

    await agent.init(env)
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert env.ask_calls[-1]["readonly"] is False


@pytest.mark.asyncio
async def test_person_agent_react_ask_env_force_template_mode_default(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=15,
        profile={"name": "Mina"},
        max_react_turns=2,
        force_template_mode=True,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("ask_env", instruction="move to {place}", variables={"place": "park"}),
            _tool("finish", final="done"),
        ]
    )

    await agent.init(env)
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert env.ask_calls[-1]["template_mode"] is True
    system_prompt = agent._dispatcher.messages[0][0]["content"]  # noqa: SLF001
    assert "Defaults template_mode to true for this agent" in system_prompt
    ask_env_tool = next(
        item for item in agent._dispatcher.calls[0]["tools"]  # noqa: SLF001
        if item["function"]["name"] == "ask_env"
    )
    assert ask_env_tool["function"]["parameters"]["properties"]["template_mode"]["default"] is True


@pytest.mark.asyncio
async def test_person_agent_react_ask_env_can_disable_template_mode(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=24,
        profile={"name": "Vic"},
        max_react_turns=2,
        allow_template_mode=False,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("ask_env", instruction="move to {place}", template_mode=True),
            _tool("finish", final="done"),
        ]
    )

    await agent.init(env)
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert env.ask_calls[-1]["template_mode"] is False


@pytest.mark.asyncio
async def test_person_agent_react_ask_env_requires_instruction(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=8,
        profile={"name": "Finn"},
        max_react_turns=1,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("ask_env", readonly=False)]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert result == "max_react_turns_reached"
    assert [item["instruction"] for item in env.ask_calls] == ["<observe>"]


@pytest.mark.asyncio
async def test_person_agent_does_not_auto_finish_from_tool_observation(tmp_path):
    """Ensure ReAct termination is controlled by LLM finish calls."""

    class _CompletionLikeEnv(_FakeEnv):
        async def ask(self, ctx, instruction, readonly=True, template_mode=False, **kwargs):
            self.ask_calls.append(
                {
                    "ctx": ctx,
                    "instruction": instruction,
                    "readonly": readonly,
                    "template_mode": template_mode,
                    "extra": kwargs,
                }
            )
            return (
                ctx,
                "Successfully retrieved the current event. The person is currently "
                "in progress, movement was initiated, and no state change was required.",
            )

    env = _CompletionLikeEnv(tmp_path)
    agent = PersonAgent(
        id=18,
        profile={"name": "Noah"},
        max_react_turns=2,
        enable_memory=False,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("ask_env", instruction="Check current event for person 18"),
            _tool("ask_env", instruction="Check current event for person 18 again"),
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 0, 0, 0))

    assert result == "max_react_turns_reached"
    assert len(agent._dispatcher.outputs) == 0  # noqa: SLF001
    assert [call["instruction"] for call in env.ask_calls] == [
        "<observe>",
        "Check current event for person 18",
        "Check current event for person 18 again",
    ]


@pytest.mark.asyncio
async def test_person_agent_does_not_block_actions_from_observed_state(tmp_path):
    """Ensure the harness does not apply domain-specific conflict rules."""

    class _StatefulEnv(_FakeEnv):
        async def ask(self, ctx, instruction, readonly=True, template_mode=False, **kwargs):
            self.ask_calls.append(
                {
                    "ctx": ctx,
                    "instruction": instruction,
                    "readonly": readonly,
                    "template_mode": template_mode,
                    "extra": kwargs,
                }
            )
            if instruction == "<observe>":
                return ctx, "The person is currently in an ongoing event."
            return ctx, f"answered:{instruction}"

    env = _StatefulEnv(tmp_path)
    agent = PersonAgent(
        id=6,
        profile={"name": "Generic"},
        max_react_turns=2,
        enable_memory=False,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("ask_env", instruction="Find nearby resources"),
            _tool("ask_env", instruction="Start another event"),
        ]
    )

    await agent.init(env)
    result = await agent.step(900, datetime(2000, 1, 1, 0, 30, 0))

    assert result == "max_react_turns_reached"
    assert [call["instruction"] for call in env.ask_calls] == [
        "<observe>",
        "Find nearby resources",
        "Start another event",
    ]


@pytest.mark.asyncio
async def test_person_agent_ask_env_record_activity_is_not_redirected(tmp_path):
    """Ensure ask_env instructions are not parsed into skill calls by the harness."""

    skill_root = tmp_path / "custom" / "skills" / "daily-guidance"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: daily-guidance\n"
        "description: test daily guidance\n"
        "script: scripts/daily_guidance.py\n"
        "---\n",
        encoding="utf-8",
    )
    (scripts / "daily_guidance.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "root = Path(os.environ['AGENT_WORK_DIR'])\n"
        "(root / 'state').mkdir(exist_ok=True)\n"
        "(root / 'state' / 'daily_args.txt').write_text('called', encoding='utf-8')\n",
        encoding="utf-8",
    )

    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=6,
        profile={"name": "Generic"},
        max_react_turns=2,
        enable_memory=False,
        default_activated_skill_ids=["custom@daily-guidance"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool(
                "ask_env",
                instruction='record_activity activity=sleep location=home_aoi note="still sleeping"',
            ),
            _tool("finish", final="done"),
        ]
    )

    await agent.init(env)
    result = await agent.step(900, datetime(2000, 1, 1, 1, 0, 0))

    assert result == "done"
    assert [call["instruction"] for call in env.ask_calls] == [
        "<observe>",
        'record_activity activity=sleep location=home_aoi note="still sleeping"',
    ]
    workspace = tmp_path / "agents" / "agent_0006"
    assert not (workspace / "state" / "daily_args.txt").exists()


@pytest.mark.asyncio
async def test_person_agent_skill_script_result_requires_llm_finish(tmp_path):
    """Ensure skill script success does not end the ReAct loop automatically."""

    skill_root = tmp_path / "custom" / "skills" / "daily-guidance"
    scripts = skill_root / "scripts"
    scripts.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: daily-guidance\n"
        "description: test daily guidance\n"
        "---\n",
        encoding="utf-8",
    )
    (scripts / "daily_guidance.py").write_text(
        "print('ok: true')\n"
        "print('mode: record')\n",
        encoding="utf-8",
    )
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=18,
        profile={"name": "Noah"},
        max_react_turns=2,
        enable_memory=False,
        default_activated_skill_ids=["custom@daily-guidance"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool(
                "execute_skill_script",
                skill_name="daily-guidance",
                script_path="scripts/daily_guidance.py",
                argv=["record", "--activity", "sleep"],
            ),
            _tool(
                "execute_skill_script",
                skill_name="daily-guidance",
                script_path="scripts/daily_guidance.py",
                argv=["record", "--activity", "sleep"],
            ),
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 0, 15, 0))

    assert result == "max_react_turns_reached"
    assert len(agent._dispatcher.outputs) == 0  # noqa: SLF001


@pytest.mark.asyncio
async def test_person_agent_redirects_env_skill_script_to_ask_env(tmp_path):
    class _EnvModuleWithSkill:
        def __init__(self, skills_dir):
            self._skills_dir = skills_dir

        def skill_dirs(self):
            return [self._skills_dir]

    skills_root = tmp_path / "env_skills"
    skill_root = skills_root / "event"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\n"
        "name: event\n"
        "description: event status and lifecycle operations\n"
        "---\n",
        encoding="utf-8",
    )
    env = _FakeEnv(tmp_path)
    env.env_modules = [_EnvModuleWithSkill(skills_root)]
    agent = PersonAgent(id=23, profile={"name": "Uma"})

    await agent.init(env)
    result = await agent.dispatch_react_tool(  # noqa: SLF001
        "execute_skill_script",
        {"skill_name": "event", "argv": ["status"], "readonly": True},
    )

    assert result.ok is True
    assert result.data["redirected_to"] == "ask_env"
    assert result.data["skill_id"].startswith("env:")
    assert result.data["skill_id"].endswith("@event")
    assert env.ask_calls[-1]["readonly"] is True
    assert "status" in env.ask_calls[-1]["instruction"]


@pytest.mark.asyncio
async def test_person_agent_prompt_includes_activated_skill_docs(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=4,
        profile={"name": "Cara"},
        default_activated_skill_ids=["built-in@daily-guidance"],
    )
    await agent.init(env)

    messages = agent.build_react_messages(  # noqa: SLF001
        tick=60,
        t=datetime(2026, 1, 2, 9, 30, 0),
        observations=[],
    )

    system_prompt = messages[0]["content"]
    assert '<skill_content name="daily-guidance">' in system_prompt
    assert "# Daily Guidance" in system_prompt
    assert "<skill_resources>" in system_prompt


@pytest.mark.asyncio
async def test_person_agent_react_retries_invalid_schema_once(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=9,
        profile={"name": "Gina"},
        max_react_turns=1,
        enable_memory=False,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("finish"),
            _tool("finish", final="schema fixed"),
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert result == "schema fixed"
    assert len(agent._dispatcher.messages) == 2  # noqa: SLF001
    assert "<schema_error>" in agent._dispatcher.messages[1][-1]["content"]  # noqa: SLF001


@pytest.mark.asyncio
async def test_person_agent_react_deactivates_skill_docs(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=10,
        profile={"name": "Hank"},
        max_react_turns=2,
        default_activated_skill_ids=["built-in@daily-guidance"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("deactivate_skill", skill_name="daily-guidance"),
            _tool("finish", final="deactivated"),
        ]
    )
    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert result == "deactivated"
    assert "built-in@daily-guidance" not in agent.skill_runtime.activated_skill_ids()  # noqa: SLF001
    first_system = agent._dispatcher.messages[0][0]["content"]  # noqa: SLF001
    second_system = agent._dispatcher.messages[1][0]["content"]  # noqa: SLF001
    assert '<skill_content name="daily-guidance">' in first_system
    assert '<skill_content name="daily-guidance">' not in second_system


@pytest.mark.asyncio
async def test_person_agent_workspace_files_are_listed_on_demand(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=11,
        profile={"name": "Iris"},
        max_react_turns=2,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("list", path="."),
            _tool("finish", final="listed"),
        ]
    )

    await agent.init(env)
    agent._workspace.write_text("notes.txt", "hello")  # noqa: SLF001
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    assert result == "listed"
    first_user = agent._dispatcher.messages[0][1]["content"]  # noqa: SLF001
    second_user = agent._dispatcher.messages[1][1]["content"]  # noqa: SLF001
    assert "<workspace_files>" not in first_user
    assert "notes.txt" in second_user


@pytest.mark.asyncio
async def test_person_agent_runs_activated_lifecycle_hooks(tmp_path):
    _write_hook_skill(tmp_path)
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=12,
        profile={"name": "June"},
        max_react_turns=1,
        default_activated_skill_ids=["custom@hooked"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("finish", final="done")]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0012"
    assert result == "done"
    assert (workspace / "state" / "pre_hook.txt").read_text(encoding="utf-8") == "pre"
    assert (workspace / "state" / "post_hook.txt").read_text(encoding="utf-8") == "post"
    first_user = agent._dispatcher.messages[0][1]["content"]  # noqa: SLF001
    # pre_step hook output is injected as a dedicated <skill_hooks> block.
    assert "<skill_hooks>" in first_user
    assert 'hook="pre_step"' in first_user
    assert "pre ok" in first_user
    names = [
        event["name"]
        for event in _read_jsonl(workspace / ".runtime" / "events.jsonl")
    ]
    assert "skill.lifecycle_hooks.pre_step" in names
    assert "skill.lifecycle_hooks.post_step" in names
    assert names.count("script.run_hook") == 2


@pytest.mark.asyncio
async def test_person_agent_step_extracts_memory_and_consolidates(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=22,
        profile={"name": "Tara"},
        max_react_turns=1,
    )
    extraction_json = json.dumps(
        {
            "memories": [
                {
                    "type": "commitment",
                    "importance": 0.86,
                    "keywords": ["Alice", "proposal"],
                    "text": "Promised Alice to review her proposal later.",
                    "source": "step_result",
                    "refs": [],
                }
            ]
        }
    )
    consolidation_markdown = (
        "# Memory\n\n"
        "## Relationships\n"
        "- Alice: asked for proposal review help.\n\n"
        "## Durable Goals And Commitments\n"
        "- Keep Alice's proposal review context in mind.\n"
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("finish", final="talked with Alice"),
            _tool("record_step_memories", **json.loads(extraction_json)),
            # Consolidation now returns Markdown directly as message content
            # (no tool call), and that text is written verbatim to MEMORY.md.
            consolidation_markdown,
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0022"
    assert result == "talked with Alice"
    episodes = _read_jsonl(workspace / "memory" / "episodes.jsonl")
    assert len(episodes) == 1
    assert episodes[0]["type"] == "commitment"
    assert episodes[0]["keywords"] == ["Alice", "proposal"]
    memory_md = (workspace / "MEMORY.md").read_text(encoding="utf-8")
    assert "Alice: asked for proposal review help" in memory_md
    assert len(agent._dispatcher.messages) == 3  # noqa: SLF001
    assert "memory_extraction_input" in agent._dispatcher.messages[1][1]["content"]  # noqa: SLF001
    assert "memory_consolidation_input" in agent._dispatcher.messages[2][1]["content"]  # noqa: SLF001
    assert agent._dispatcher.calls[1]["tool_choice"]["function"]["name"] == "record_step_memories"  # noqa: SLF001
    # Consolidation no longer uses a tool call — the refreshed Markdown is the
    # LLM message content, so no tool_choice is sent for the third call.
    assert "tool_choice" not in agent._dispatcher.calls[2] or not agent._dispatcher.calls[2].get("tool_choice")  # noqa: SLF001


@pytest.mark.asyncio
async def test_person_agent_memory_extraction_rejects_invalid_tool_args(tmp_path):
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=23,
        profile={"name": "Uma"},
        max_react_turns=1,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("finish", final="ordinary step"),
            _tool(
                "record_step_memories",
                memories=[
                    {
                        "type": "not-a-valid-type",
                        "importance": 2.0,
                        "keywords": ["bad"],
                        "text": "Invalid memory.",
                    }
                ],
            ),
        ]
    )

    await agent.init(env)
    result = await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0023"
    assert result == "ordinary step"
    assert _read_jsonl(workspace / "memory" / "episodes.jsonl") == []


@pytest.mark.asyncio
async def test_person_agent_skips_unactivated_lifecycle_hooks(tmp_path):
    _write_hook_skill(tmp_path)
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=13,
        profile={"name": "Kara"},
        max_react_turns=1,
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [_tool("finish", final="done")]
    )

    await agent.init(env)
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))

    workspace = tmp_path / "agents" / "agent_0013"
    assert not (workspace / "state" / "pre_hook.txt").exists()
    assert not (workspace / "state" / "post_hook.txt").exists()
    names = [
        event["name"]
        for event in _read_jsonl(workspace / ".runtime" / "events.jsonl")
    ]
    assert names.count("script.run_hook") == 0
    assert not (
        workspace / "state" / "daily_guidance" / "2026-01-02" / "story.yaml"
    ).exists()


@pytest.mark.asyncio
async def test_person_agent_deactivate_stops_next_step_hooks(tmp_path):
    _write_hook_skill(tmp_path)
    env = _FakeEnv(tmp_path)
    agent = PersonAgent(
        id=14,
        profile={"name": "Liam"},
        max_react_turns=2,
        enable_memory=False,
        default_activated_skill_ids=["custom@hooked"],
    )
    agent._dispatcher = _FakeLLMRouter(  # noqa: SLF001
        [
            _tool("deactivate_skill", skill_name="hooked"),
            _tool("finish", final="first"),
            _tool("finish", final="second"),
        ]
    )

    await agent.init(env)
    workspace = tmp_path / "agents" / "agent_0014"
    await agent.step(60, datetime(2026, 1, 2, 9, 30, 0))
    assert (workspace / "state" / "pre_hook.txt").exists()
    (workspace / "state" / "pre_hook.txt").unlink()
    if (workspace / "state" / "post_hook.txt").exists():
        (workspace / "state" / "post_hook.txt").unlink()

    result = await agent.step(60, datetime(2026, 1, 2, 9, 31, 0))

    assert result == "second"
    assert "custom@hooked" not in agent.skill_runtime.activated_skill_ids()  # noqa: SLF001
    assert not (workspace / "state" / "pre_hook.txt").exists()
    assert not (workspace / "state" / "post_hook.txt").exists()


def test_build_react_messages_stable_section_cache_reuses():
    from agentsociety2.agent.person_prompt import build_react_messages

    cache: dict = {}
    key = (frozenset({"a"}), frozenset({"b"}), "world")
    msgs1 = build_react_messages(
        name="A",
        force_template_mode=False,
        world_description="world",
        skill_catalog=[{"name": "a", "description": "d"}],
        activated_skill_content="<skill_content name='b'>x</skill_content>",
        observations=[],
        agent_json={"id": 1},
        stable_cache=cache,
        stable_cache_key=key,
    )
    msgs2 = build_react_messages(
        name="A",
        force_template_mode=False,
        world_description="world",
        skill_catalog=[{"name": "a", "description": "d"}],
        activated_skill_content="<skill_content name='b'>x</skill_content>",
        observations=[{"turn": 1}],
        agent_json={"id": 1},
        stable_cache=cache,
        stable_cache_key=key,
    )
    assert len(cache) == 1
    assert msgs1[0]["content"] == msgs2[0]["content"]  # system prompt reused
    assert msgs1[1]["content"] != msgs2[1]["content"]  # user (observations) differs
