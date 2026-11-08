"""Provenance tracking: every value an agent uses carries the set of sources it came from."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class Trust(str, Enum):
    OWNER = "owner"          # typed or signed by the wallet owner
    AGENT = "agent"          # produced by the agent's own reasoning/arithmetic
    UNTRUSTED = "untrusted"  # anything read from the outside world


@dataclass(frozen=True)
class Source:
    trust: Trust
    origin: str  # e.g. "owner:chat", "web:https://...", "token-metadata:factory/..."

    def __str__(self) -> str:
        return f"{self.trust.value}<{self.origin}>"


OWNER_CHAT = Source(Trust.OWNER, "owner:chat")
AGENT_REASONING = Source(Trust.AGENT, "agent:reasoning")


@dataclass(frozen=True)
class Tainted:
    """A value plus the sources that influenced it."""

    value: Any
    sources: frozenset[Source] = field(default_factory=frozenset)

    @staticmethod
    def of(value: Any, *sources: Source) -> "Tainted":
        return Tainted(value, frozenset(sources))

    def derive(self, value: Any, *others: "Tainted") -> "Tainted":
        """A new value computed from this one (and others) inherits all their sources."""
        srcs = set(self.sources)
        for o in others:
            srcs |= o.sources
        srcs.add(AGENT_REASONING)
        return Tainted(value, frozenset(srcs))

    @property
    def untrusted_sources(self) -> list[Source]:
        return sorted((s for s in self.sources if s.trust is Trust.UNTRUSTED), key=str)

    @property
    def is_untrusted(self) -> bool:
        return bool(self.untrusted_sources)

    @property
    def has_owner_origin(self) -> bool:
        return any(s.trust is Trust.OWNER for s in self.sources)


def merge(values: Iterable[Tainted]) -> frozenset[Source]:
    out: set[Source] = set()
    for v in values:
        out |= v.sources
    return frozenset(out)
