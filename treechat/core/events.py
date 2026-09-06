"""事件模型 —— 7 种事件 + 严格序列化。

type 字符串（snake_case）与 dataclass 一一对应；from_dict 严格校验
字段集（缺字段/多余字段/未知类型一律 EventFormatError），不做隐式补全。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields as dc_fields
from typing import Any

from .errors import EventFormatError


@dataclass
class SessionMeta:
    name: str
    created_at: str
    system: str = ""


@dataclass
class UserMsg:
    parent: int | None
    text: str


@dataclass
class AssistantMsg:
    parent: int
    text: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class SystemUpdate:
    text: str


@dataclass
class CardCreate:
    card_id: str
    title: str
    body: str
    from_path: list[int]
    instruction: str = ""


@dataclass
class Pin:
    card_id: str


@dataclass
class Unpin:
    card_id: str


_EVENT_TYPES: dict[str, type] = {
    "session_meta": SessionMeta,
    "user_msg": UserMsg,
    "assistant_msg": AssistantMsg,
    "system_update": SystemUpdate,
    "card_create": CardCreate,
    "pin": Pin,
    "unpin": Unpin,
}


def event_to_dict(seq: int, event: object) -> dict[str, Any]:
    """事件 → {"seq", "type", **字段}。未知事件对象抛 EventFormatError。"""
    for type_name, cls in _EVENT_TYPES.items():
        if isinstance(event, cls):
            d: dict[str, Any] = {"seq": seq, "type": type_name}
            d.update(asdict(event))
            return d
    raise EventFormatError(f"未知事件对象: {event!r}")


def event_from_dict(d: dict[str, Any]) -> tuple[int, object]:
    """dict → (seq, event)。严格校验字段集。"""
    if not isinstance(d, dict) or "seq" not in d or "type" not in d:
        raise EventFormatError(f"事件缺 seq/type 字段: {d!r}")
    type_name = d["type"]
    cls = _EVENT_TYPES.get(type_name)
    if cls is None:
        raise EventFormatError(f"未知事件类型: {type_name!r} (seq={d['seq']})")
    names = {f.name for f in dc_fields(cls)}
    kwargs = {k: v for k, v in d.items() if k not in ("seq", "type")}
    missing = names - kwargs.keys()
    if missing:
        raise EventFormatError(f"事件 {type_name} 缺字段 {sorted(missing)} (seq={d['seq']})")
    extra = kwargs.keys() - names
    if extra:
        raise EventFormatError(f"事件 {type_name} 多余字段 {sorted(extra)} (seq={d['seq']})")
    return d["seq"], cls(**kwargs)
