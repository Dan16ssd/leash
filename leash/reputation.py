"""Agent tiers: a reputation score built only from what Leash itself observed.

The score is not self-reported and not a model proof. It is replayed from Leash's audit
log: signed transactions raise it, blocked injection attempts and rejections lower it.
The tier then decides how much the agent may move. A fresh identity always starts at the
bottom tier, so minting a new ID never buys trust.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from pathlib import Path


class Tier(str, Enum):
    REVOKED = "revoked"
    UNTRUSTED = "untrusted"
    VERIFIED = "verified"
    ELITE = "elite"


@dataclass(frozen=True)
class TierLimits:
    max_tx_usd: Decimal
    approval_above_usd: Decimal
    daily_limit_usd: Decimal


@dataclass
class TierRules:
    start_score: int = 20
    verified_at: int = 40
    elite_at: int = 80
    elite_min_signed: int = 30
    elite_clean_window: int = 20       # no injection blocks in the last N events
    revoke_after_injections: int = 3
    anomaly_multiple: Decimal = Decimal("3")  # tx > 3x the largest past tx -> ask owner
    limits: dict[Tier, TierLimits] = field(default_factory=lambda: {
        Tier.UNTRUSTED: TierLimits(Decimal("50"), Decimal("20"), Decimal("100")),
        Tier.VERIFIED: TierLimits(Decimal("500"), Decimal("100"), Decimal("1000")),
        Tier.ELITE: TierLimits(Decimal("5000"), Decimal("1000"), Decimal("20000")),
    })

    @staticmethod
    def from_dict(raw: dict) -> "TierRules":
        r = TierRules()
        for k in ("start_score", "verified_at", "elite_at", "elite_min_signed",
                  "elite_clean_window", "revoke_after_injections"):
            if k in raw:
                setattr(r, k, int(raw[k]))
        if "anomaly_multiple" in raw:
            r.anomaly_multiple = Decimal(str(raw["anomaly_multiple"]))
        if "limits" in raw:
            r.limits = {Tier(t): TierLimits(*(Decimal(str(v[k])) for k in
                        ("max_tx_usd", "approval_above_usd", "daily_limit_usd")))
                        for t, v in raw["limits"].items()}
        return r


# Event kinds Leash records per agent.
SIGNED = "signed"              # tx passed and was signed
APPROVED = "approved"          # owner approved a NEEDS_APPROVAL tx
REJECTED = "rejected"          # owner rejected a NEEDS_APPROVAL tx
INJECTION = "injection_block"  # blocked because a protected field came from untrusted content
POLICY = "policy_block"        # blocked by limits / allowlists / RWA rules

WEIGHTS = {SIGNED: 2, APPROVED: 3, REJECTED: -5, INJECTION: -15, POLICY: -2}
SIGNED_POINTS_CAP = 60  # routine activity alone can't push past elite_at; no farming to 100


@dataclass
class AgentRecord:
    agent_id: str
    events: list[str] = field(default_factory=list)
    max_signed_usd: Decimal = Decimal("0")

    def count(self, kind: str) -> int:
        return self.events.count(kind)


class ReputationBook:
    def __init__(self, rules: TierRules | None = None):
        self.rules = rules or TierRules()
        self.agents: dict[str, AgentRecord] = {}

    def record_for(self, agent_id: str) -> AgentRecord:
        return self.agents.setdefault(agent_id, AgentRecord(agent_id))

    # ---- scoring ----------------------------------------------------------------
    def score(self, agent_id: str) -> int:
        rec = self.record_for(agent_id)
        signed_pts = min(rec.count(SIGNED) * WEIGHTS[SIGNED], SIGNED_POINTS_CAP)
        other = sum(WEIGHTS[e] for e in rec.events if e != SIGNED)
        return max(0, min(100, self.rules.start_score + signed_pts + other))

    def tier(self, agent_id: str) -> Tier:
        rec = self.record_for(agent_id)
        r = self.rules
        if rec.count(INJECTION) >= r.revoke_after_injections:
            return Tier.REVOKED
        s = self.score(agent_id)
        recent_clean = INJECTION not in rec.events[-r.elite_clean_window:]
        if s >= r.elite_at and rec.count(SIGNED) >= r.elite_min_signed and recent_clean:
            return Tier.ELITE
        if s >= r.verified_at:
            return Tier.VERIFIED
        return Tier.UNTRUSTED

    def limits(self, agent_id: str) -> TierLimits | None:
        return self.rules.limits.get(self.tier(agent_id))

    def anomaly(self, agent_id: str, usd: Decimal) -> str | None:
        """Anti rug-pull: a sudden jump far beyond anything this agent has done needs a human."""
        rec = self.record_for(agent_id)
        if rec.max_signed_usd > 0 and usd > rec.max_signed_usd * self.rules.anomaly_multiple:
            return (f"${usd:.2f} is more than {self.rules.anomaly_multiple}x this agent's "
                    f"largest past tx (${rec.max_signed_usd:.2f})")
        return None

    # ---- events -----------------------------------------------------------------
    def add(self, agent_id: str, kind: str, usd: Decimal | None = None) -> None:
        rec = self.record_for(agent_id)
        rec.events.append(kind)
        if kind in (SIGNED, APPROVED) and usd is not None:
            rec.max_signed_usd = max(rec.max_signed_usd, usd)

    @staticmethod
    def from_audit_log(path: str | Path, rules: TierRules | None = None) -> "ReputationBook":
        """Rebuild every agent's score by replaying Leash's audit log."""
        book = ReputationBook(rules)
        p = Path(path)
        if not p.exists():
            return book
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("event") and e.get("agent_id"):
                usd = Decimal(e["usd"]) if e.get("usd") else None
                book.add(e["agent_id"], e["event"], usd)
        return book

    def snapshot(self, agent_id: str) -> dict:
        rec = self.record_for(agent_id)
        return {"agent_id": agent_id, "score": self.score(agent_id),
                "tier": self.tier(agent_id).value, "signed": rec.count(SIGNED),
                "injection_blocks": rec.count(INJECTION),
                "max_signed_usd": str(rec.max_signed_usd)}
