"""The Leash guard: decides ALLOW / NEEDS_APPROVAL / BLOCK for each proposed message, and logs why."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path

from .policy import Policy
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


class Guard:
    def __init__(self, policy: Policy, audit_log: str | Path | None = None,
                 provenance: bool = True):
        self.policy = policy
        self.audit_log = Path(audit_log) if audit_log else None
        self.provenance = provenance  # False = behave like a plain limit-based wallet policy
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

    def evaluate(self, msg: Msg) -> Decision:
        block: list[str] = []
        approve: list[str] = []
        p = self.policy

        if self.provenance:
            block += self._provenance(msg)

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
        if usd is None:
            block.append("no price for asset; cannot value the transaction")
        else:
            if usd > p.max_tx_usd:
                block.append(f"${usd:.2f} exceeds per-tx max ${p.max_tx_usd}")
            elif self.spent_today + usd > p.daily_limit_usd:
                block.append(f"daily limit ${p.daily_limit_usd} would be exceeded")
            elif usd > p.approval_above_usd:
                approve.append(f"${usd:.2f} is above the auto-approve threshold ${p.approval_above_usd}")

        if block:
            d = Decision(Verdict.BLOCK, block, usd)
        elif approve:
            d = Decision(Verdict.NEEDS_APPROVAL, approve, usd)
        else:
            d = Decision(Verdict.ALLOW, ["all checks passed"], usd)
        self._log(msg, d)
        return d

    def commit(self, msg: Msg) -> None:
        """Call after the transaction is actually signed/broadcast."""
        usd = self._usd(msg)
        if usd is not None:
            self.spent_today += usd

    def _log(self, msg: Msg, d: Decision) -> None:
        if not self.audit_log:
            return
        entry = {
            "ts": time.time(),
            "type_url": msg.type_url,
            "summary": msg.summary(),
            "verdict": d.verdict.value,
            "reasons": d.reasons,
            "usd": str(d.usd_value) if d.usd_value is not None else None,
            "provenance": {
                f: sorted(str(s) for s in getattr(msg, f).sources)
                for f in msg.__dataclass_fields__
            },
        }
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
