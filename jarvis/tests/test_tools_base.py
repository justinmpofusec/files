from jarvis.tools.base import ToolRegistry, coerce_args, tool

import pytest


def test_schema_from_signature():
    @tool("Does things.", sensitive=True, a="first", flags="some flags")
    def thing(a: str, b: int, c: float = 1.0, d: bool = False, flags: list[str] | None = None, e: str | None = None):
        return a

    assert thing.name == "thing"
    assert thing.description == "Does things."
    assert thing.sensitive
    props = thing.parameters["properties"]
    assert props["a"] == {"type": "string", "description": "first"}
    assert props["b"]["type"] == "integer"
    assert props["c"]["type"] == "number"
    assert props["d"]["type"] == "boolean"
    assert props["flags"] == {"type": "array", "items": {"type": "string"}, "description": "some flags"}
    assert props["e"]["type"] == "string"
    assert thing.parameters["required"] == ["a", "b"]
    assert thing(a="x", b=1) == "x"


def test_param_named_description_and_name_allowed():
    @tool("Find.", description="what to find", name="a name")
    def find(description: str, name: str = "") -> str:
        return description + name

    assert find.parameters["properties"]["description"]["description"] == "what to find"
    assert find.parameters["properties"]["name"]["description"] == "a name"


def test_no_params_schema():
    @tool("Nothing.")
    def nothing() -> str:
        return "ok"

    assert nothing.parameters == {"type": "object", "properties": {}}


def test_registry_rejects_duplicates():
    @tool("x")
    def a() -> str:
        return ""

    reg = ToolRegistry().add(a)
    assert "a" in reg and len(reg) == 1 and reg.get("a") is a
    with pytest.raises(ValueError):
        reg.add(a)


def test_coerce_args():
    @tool("x")
    def f(n: int, x: float, flag: bool, s: str) -> str:
        return ""

    out = coerce_args(f, {"n": 3.0, "x": "2.5", "flag": "true", "s": "hi", "extra": 1})
    assert out == {"n": 3, "x": 2.5, "flag": True, "s": "hi", "extra": 1}
    assert isinstance(out["n"], int)
    assert coerce_args(f, {"n": "-4"})["n"] == -4
    assert coerce_args(f, {"n": 2.5})["n"] == 2.5  # not silently truncated
