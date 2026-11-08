"""The Leash guard: decides ALLOW / NEEDS_APPROVAL / BLOCK for each proposed message, and logs why.

Limits come from the agent's tier when a ReputationBook is attached, otherwise from the policy.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path

from .policy import Policy
from .reputation import (APPROVED, INJECTION, POLICY, REJECTED, SIGNED, ReputationBook,
                         Tier)
from .tx import Msg, MsgSend, MsgSpotMarketOrder


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    BLOCK = "BLOCK"


@dataclass
class Decision:
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    usd_value: Decimal | None = None
    injection: bool = False
    tier: str | None = None
    score: int | None = None


class Guard:
    def __init__(self, policy: Policy, audit_log: str | Path | None = None,
                 provenance: bool = True, reputation: ReputationBook | None = None,
                 agent_id: str = "default-agent"):
        self.policy = policy
        self.audit_log = Path(audit_log) if audit_log else None
        self.provenance = provenance  # False = behave like a plain limit-based wallet policy
        self.reputation = reputation
        self.agent_id = agent_id
        self.spent_today = Decimal("0")

    # ---- checks -----------------------------------------------------------------
    def _provenance(self, msg: Msg) -> list[str]:
        reasons = []
        for fname in self.policy.protected_fields.get(type(msg).__name__, []):
            val = getattr(msg, fname)
            for src in val.untrusted_sources:
                reasons.append(f"{fname}={val.value!r} was influenced by untrusted content {src}")
        return reasons

    def _usd(self, msg: Msg) -> Decimal | None:
        if isinstance(msg, MsgSend):
            return self.policy.usd(msg.denom.value, Decimal(msg.amount.value))
        if isinstance(msg, MsgSpotMarketOrder):
            # Value at the oracle price of the base asset, never at the agent's worst_price,
            # otherwise a sell at a near-zero limit price would look harmless.
            base = msg.market.value.split("/")[0].lower()
            return self.policy.usd(base, Decimal(msg.quantity.value))
        return None

    def _limits(self) -> tuple[Decimal, Decimal, Decimal, str | None]:
        p = self.policy
        if self.reputation is None:
            return p.max_tx_usd, p.approval_above_usd, p.daily_limit_usd, None
        tier = self.reputation.tier(self.agent_id)
        lim = self.reputation.limits(self.agent_id)
        if lim is None:  # revoked
            return Decimal("0"), Decimal("0"), Decimal("0"), tier.value
        # The owner's policy is always the ceiling; the tier can only tighten it.
        return (min(lim.max_tx_usd, p.max_tx_usd), min(lim.approval_above_usd, p.approval_above_usd),
                min(lim.daily_limit_usd, p.daily_limit_usd), tier.value)

    def evaluate(self, msg: Msg) -> Decision:
        block: list[str] = []
        approve: list[str] = []
        p = self.policy
        max_tx, approval_above, daily, tier = self._limits()

        injection = self._provenance(msg) if self.provenance else []
        block += injection

        if tier == Tier.REVOKED.value:
            block.append(f"agent {self.agent_id} is revoked (repeated injection attempts)")

        if isinstance(msg, MsgSend):
            to, denom = msg.to_address.value, msg.denom.value
            if p.allowed_denoms and denom not in p.allowed_denoms:
                block.append(f"denom {denom} not in allowlist")
            if denom in p.rwa_holders and to not in p.rwa_holders[denom]:
                block.append(f"RWA rule: {to} is not a whitelisted holder of {denom}")
            if p.allowed_recipients and to not in p.allowed_recipients:
                approve.append(f"recipient {to} is not in the address book")
        elif isinstance(msg, MsgSpotMarketOrder):
            if p.allowed_markets and msg.market.value not in p.allowed_markets:
                block.append(f"market {msg.market.value} not in allowlist")

        usd = self._usd(msg)
        tier_note = f" for tier {tier}" if tier else ""
        if usd is None:
            block.append("no price for asset; cannot value the transaction")
        elif tier != Tier.REVOKED.value:
            if usd > max_tx:
                block.append(f"${usd:.2f} exceeds per-tx max ${max_tx}{tier_note}")
            elif self.spent_today + usd > daily:
                block.append(f"daily limit ${daily}{tier_note} would be exceeded")
            else:
                if usd > approval_above:
                    approve.append(f"${usd:.2f} is above the auto-approve threshold ${approval_above}{tier_note}")
                if self.reputation is not None:
                    jump = self.reputation.anomaly(self.agent_id, usd)
                    if jump:
                        approve.append(jump)

        score = self.reputation.score(self.agent_id) if self.reputation else None
        if block:
            d = Decision(Verdict.BLOCK, block, usd, bool(injection), tier, score)
        elif approve:
            d = Decision(Verdict.NEEDS_APPROVAL, approve, usd, False, tier, score)
        else:
            d = Decision(Verdict.ALLOW, ["all checks passed"], usd, False, tier, score)
        if d.verdict is Verdict.BLOCK:
            self._event(INJECTION if injection else POLICY, msg, d)
        self._log(msg, d)
        return d

    def commit(self, msg: Msg, approved_by_owner: bool = False) -> None:
        """Call after the transaction is actually signed/broadcast."""
        usd = self._usd(msg)
        if usd is not None:
            self.spent_today += usd
        self._event(APPROVED if approved_by_owner else SIGNED, msg, None, usd)

    def new_day(self) -> None:
        self.spent_today = Decimal("0")

    def reject(self, msg: Msg) -> None:
        """The owner said no to a NEEDS_APPROVAL transaction."""
        self._event(REJECTED, msg, None)

    # ---- logging ----------------------------------------------------------------
    def _event(self, kind: str, msg: Msg, d: Decision | None, usd: Decimal | None = None) -> None:
        if usd is None and d is not None:
            usd = d.usd_value
        if self.reputation is not None:
            self.reputation.add(self.agent_id, kind, usd)
        self._write({"ts": time.time(), "agent_id": self.agent_id, "event": kind,
                     "summary": msg.summary(), "usd": str(usd) if usd is not None else None})

    def _log(self, msg: Msg, d: Decision) -> None:
        self._write({
            "ts": time.time(),
            "agent_id": self.agent_id,
            "type_url": msg.type_url,
            "summary": msg.summary(),
            "verdict": d.verdict.value,
            "reasons": d.reasons,
            "usd": str(d.usd_value) if d.usd_value is not None else None,
            "tier": d.tier,
            "score": d.score,
            "provenance": {
                f: sorted(str(s) for s in getattr(msg, f).sources)
                for f in msg.__dataclass_fields__
            },
        })

    def _write(self, entry: dict) -> None:
        if not self.audit_log:
            return
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
