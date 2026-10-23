from conftest import call, say

from jarvis.agent import Agent
from jarvis.llm import LLMReply, ToolCall, ToolResult
from jarvis.tools.base import ToolRegistry, tool


def make_agent(ctx, *tools, **kw):
    return Agent(name="test", system_prompt="be helpful", tools=ToolRegistry().add(*tools), ctx=ctx, **kw)


@tool("Add numbers.")
def add(a: int, b: int) -> int:
    return a + b


@tool("Dangerous.", sensitive=True)
def danger() -> str:
    return "boom"


@tool("Fails.")
def broken() -> str:
    raise RuntimeError("disk on fire")


def test_runs_tool_and_returns_final_text(make_ctx):
    ctx = make_ctx(replies=[call("add", a=2, b=3.0), say("2 + 3 = 5")])
    agent = make_agent(ctx, add)
    assert agent.run("what is 2+3?") == "2 + 3 = 5"
    sent = ctx.llm.sent
    assert sent[0] == "what is 2+3?"
    (result,) = sent[1]
    assert isinstance(result, ToolResult) and result.output == 5 and not result.error
    assert result.as_response() == {"result": 5}
    assert ctx.llm.sessions[0].tool_names == ["add"]
    assert ctx.llm.sessions[0].system_prompt == "be helpful"


def test_multiple_calls_in_one_turn(make_ctx):
    reply = LLMReply(tool_calls=[ToolCall("add", {"a": 1, "b": 1}), ToolCall("add", {"a": 2, "b": 2})])
    ctx = make_ctx(replies=[reply, say("done")])
    make_agent(ctx, add).run("go")
    assert [r.output for r in ctx.llm.sent[1]] == [2, 4]


def test_conversation_session_persists_until_reset(make_ctx):
    ctx = make_ctx(replies=[say("one"), say("two"), say("three")])
    agent = make_agent(ctx, add)
    agent.run("a")
    agent.run("b")
    assert len(ctx.llm.sessions) == 1
    agent.reset()
    agent.run("c")
    assert len(ctx.llm.sessions) == 2


def test_unknown_tool_and_errors_reported_not_raised(make_ctx):
    ctx = make_ctx(replies=[LLMReply(tool_calls=[ToolCall("nope"), ToolCall("broken"), ToolCall("add", {"a": 1})]),
                            say("sorry")])
    assert make_agent(ctx, add, broken).run("x") == "sorry"
    unknown, failed, bad_args = ctx.llm.sent[1]
    assert unknown.error and "unknown tool" in unknown.output
    assert failed.error and failed.as_response() == {"error": "RuntimeError: disk on fire"}
    assert bad_args.error and "bad arguments" in bad_args.output


def test_sensitive_tool_requires_confirmation(make_ctx):
    ctx = make_ctx(replies=[call("danger"), say("ok")], confirm=False)
    make_agent(ctx, danger).run("x")
    assert ctx.confirm.asked == [("danger", {})]
    (result,) = ctx.llm.sent[1]
    assert result.error and "declined" in result.output

    ctx = make_ctx(replies=[call("danger"), say("ok")], confirm=True)
    make_agent(ctx, danger).run("x")
    assert ctx.llm.sent[1][0].output == "boom"


def test_confirm_modes(make_ctx):
    ctx = make_ctx(replies=[call("add", a=1, b=1), say("ok")], confirm="always")
    ctx.config.confirm = "always"
    make_agent(ctx, add).run("x")
    assert [n for n, _ in ctx.confirm.asked] == ["add"]

    ctx = make_ctx(replies=[call("danger"), say("ok")])
    ctx.config.confirm = "never"
    make_agent(ctx, danger).run("x")
    assert ctx.confirm.asked == [] and ctx.llm.sent[1][0].output == "boom"

    ctx = make_ctx(replies=[call("danger"), say("ok")], dry_run=True)
    make_agent(ctx, danger).run("x")
    assert ctx.confirm.asked == []  # nothing real happens in dry-run, so no prompt


def test_max_steps_stops_loops(make_ctx):
    ctx = make_ctx(replies=[call("add", a=1, b=1)] * 10)
    out = make_agent(ctx, add, max_steps=3).run("loop forever")
    assert "Stopped after 3 steps" in out
    assert len(ctx.llm.sent) == 4  # request + 3 rounds of results


def test_as_tool_delegation_starts_fresh_each_time(make_ctx):
    ctx = make_ctx(replies=[say("sub done 1"), say("sub done 2")])
    sub = make_agent(ctx, add)
    delegate = sub.as_tool("Delegate math.")
    assert delegate.name == "delegate_to_test"
    assert delegate.parameters["required"] == ["task"]
    assert delegate(task="compute") == "sub done 1"
    assert delegate(task="again") == "sub done 2"
    assert len(ctx.llm.sessions) == 2


def test_nested_delegation_from_parent(make_ctx):
    ctx = make_ctx(replies=[
        call("delegate_to_test", task="add 2 and 2"),  # parent
        call("add", a=2, b=2),  # sub-agent
        say("sub: it is 4"),  # sub-agent final
        say("Jarvis: the answer is 4"),  # parent final
    ])
    sub = make_agent(ctx, add)
    parent = Agent("parent", "p", ToolRegistry().add(sub.as_tool("math")), ctx)
    assert parent.run("2+2?") == "Jarvis: the answer is 4"
    assert ctx.llm.sent[-1][0].output == "sub: it is 4"
