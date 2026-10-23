"""Tool definitions: plain Python functions the LLM can call, with a JSON schema built from the signature."""

from __future__ import annotations

import inspect
import types
import typing
from dataclasses import dataclass, field
from typing import Any, Callable

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any]
    sensitive: bool = False  # needs user confirmation (sends messages, runs commands, ...)

    def __call__(self, **kwargs: Any) -> Any:
        return self.func(**kwargs)


def _schema_for(func: Callable, param_docs: dict[str, str]) -> dict[str, Any]:
    hints = typing.get_type_hints(func)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in inspect.signature(func).parameters.items():
        annotation = hints.get(name, str)
        origin = typing.get_origin(annotation)
        if origin in (typing.Union, types.UnionType):
            args = [a for a in typing.get_args(annotation) if a is not type(None)]
            annotation = args[0] if args else str
            origin = typing.get_origin(annotation)
        if origin is list:
            (item,) = typing.get_args(annotation) or (str,)
            prop: dict[str, Any] = {"type": "array", "items": {"type": _JSON_TYPES.get(item, "string")}}
        else:
            prop = {"type": _JSON_TYPES.get(annotation, "string")}
        if name in param_docs:
            prop["description"] = param_docs[name]
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def tool(summary: str, /, *, sensitive: bool = False, tool_name: str | None = None, **param_docs: str):
    """Decorator turning a function into a Tool. Keyword args document each parameter."""

    def wrap(func: Callable) -> Tool:
        return Tool(
            name=tool_name or func.__name__,
            description=summary,
            func=func,
            parameters=_schema_for(func, param_docs),
            sensitive=sensitive,
        )

    return wrap


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, *tools: Tool) -> "ToolRegistry":
        for t in tools:
            if t.name in self.tools:
                raise ValueError(f"duplicate tool name: {t.name}")
            self.tools[t.name] = t
        return self

    def __iter__(self):
        return iter(self.tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self.tools

    def __len__(self) -> int:
        return len(self.tools)

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)


def coerce_args(t: Tool, args: dict[str, Any]) -> dict[str, Any]:
    """LLMs often send 3.0 for an integer or "true" for a boolean; fix those up using the schema."""
    props = t.parameters.get("properties", {})
    fixed = {}
    for key, value in args.items():
        kind = props.get(key, {}).get("type")
        if kind == "integer" and isinstance(value, float) and value.is_integer():
            value = int(value)
        elif kind == "integer" and isinstance(value, str) and value.strip().lstrip("-").isdigit():
            value = int(value)
        elif kind == "number" and isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                pass
        elif kind == "boolean" and isinstance(value, str):
            value = value.strip().lower() in ("true", "1", "yes")
        fixed[key] = value
    return fixed
