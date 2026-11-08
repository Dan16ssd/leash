"""Leash proxy: sits between an agent and the signer (later: Injective's MCP server / chain).

The agent proposes a raw message; the proxy attributes every field through the ledger,
asks the guard, and only forwards to the signer on ALLOW (or on human approval).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .guard import Decision, Guard, Verdict
from .ledger import ContextLedger
from .tx import Msg, MsgSend, MsgSpotMarketOrder

Signer = Callable[[Msg], str]          # returns a tx hash
Approver = Callable[[Msg, Decision], bool]


@dataclass
class Result:
    msg: Msg
    decision: Decision
    tx_hash: str | None


class LeashProxy:
    def __init__(self, guard: Guard, signer: Signer, approver: Approver | None = None):
        self.guard = guard
        self.signer = signer
        self.approver = approver or (lambda m, d: False)

    def tag(self, raw: dict, ledger: ContextLedger) -> Msg:
        kind = raw["type"]
        if kind == "MsgSend":
            return MsgSend(
                to_address=ledger.attribute(raw["to_address"]),
                denom=ledger.attribute(raw["denom"]),
                amount=ledger.attribute(raw["amount"]),
            )
        if kind == "MsgSpotMarketOrder":
            return MsgSpotMarketOrder(
                market=ledger.attribute(raw["market"]),
                side=ledger.attribute(raw["side"]),
                quantity=ledger.attribute(raw["quantity"]),
                worst_price=ledger.attribute(raw["worst_price"]),
            )
        raise ValueError(f"unsupported message type {kind}")

    def submit(self, raw: dict, ledger: ContextLedger) -> Result:
        msg = self.tag(raw, ledger)
        d = self.guard.evaluate(msg)
        tx_hash = None
        if d.verdict is Verdict.ALLOW:
            tx_hash = self.signer(msg)
            self.guard.commit(msg)
        elif d.verdict is Verdict.NEEDS_APPROVAL:
            if self.approver(msg, d):
                tx_hash = self.signer(msg)
                self.guard.commit(msg, approved_by_owner=True)
            else:
                self.guard.reject(msg)
        return Result(msg, d, tx_hash)
