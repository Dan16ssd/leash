"""Context ledger: records every piece of text the agent saw, tagged with its source,
then attributes each field of a proposed transaction back to the sources that contain it.

This treats the LLM as a black box: we don't need to trust its reasoning, only to know
what it read. If a recipient address or amount only appears in a webpage, tweet or token
description - and never in what the owner said - it was decided by untrusted content.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .taint import AGENT_REASONING, Source, Tainted, Trust

_ADDR = re.compile(r"\binj1[0-9a-z]{38,58}\b")  # wallets (38) and contracts (58)
_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\w)(?!\.\d)")


def _norm(value) -> str:
    if isinstance(value, Decimal) or isinstance(value, (int, float)):
        return str(Decimal(str(value)).normalize())
    return str(value).strip().lower()


def _tokens(text: str) -> set[str]:
    toks = {t.lower() for t in _ADDR.findall(text)}
    for n in _NUM.findall(text):
        try:
            toks.add(str(Decimal(n).normalize()))
        except InvalidOperation:
            pass
    # Words, denoms, markets. Trailing sentence punctuation must not hide a value:
    # "send to inj1abc." has to match "inj1abc".
    toks |= {w.lower().rstrip(".:-/") for w in re.findall(r"[A-Za-z][\w/.:-]*", text)}
    return toks


@dataclass
class Entry:
    source: Source
    text: str
    tokens: set[str]


class ContextLedger:
    def __init__(self) -> None:
        self.entries: list[Entry] = []

    def add(self, text: str, source: Source) -> None:
        self.entries.append(Entry(source, text, _tokens(text)))

    def attribute(self, value) -> Tainted:
        key = _norm(value)
        owner = {e.source for e in self.entries if e.source.trust is Trust.OWNER and key in e.tokens}
        if owner:
            # The owner said it themselves: untrusted repetitions don't change who decided it.
            return Tainted(value, frozenset(owner))
        untrusted = {e.source for e in self.entries if key in e.tokens}
        if untrusted:
            return Tainted(value, frozenset(untrusted))
        return Tainted(value, frozenset({AGENT_REASONING}))
