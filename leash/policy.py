"""Owner-defined rules. Loaded from JSON so the same policy can later be mirrored into the on-chain guard contract."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


@dataclass
class Policy:
    # Provenance rules: which fields must never be decided by untrusted content.
    protected_fields: dict[str, list[str]] = field(default_factory=lambda: {
        "MsgSend": ["to_address", "amount", "denom"],
        "MsgSpotMarketOrder": ["market", "side", "quantity", "worst_price"],
    })
    # Per-transaction caps in USD (prices supplied by an oracle; static in the prototype).
    max_tx_usd: Decimal = Decimal("500")
    approval_above_usd: Decimal = Decimal("100")
    daily_limit_usd: Decimal = Decimal("1000")
    allowed_recipients: dict[str, str] = field(default_factory=dict)  # address -> label
    allowed_denoms: list[str] = field(default_factory=list)
    allowed_markets: list[str] = field(default_factory=list)
    # RWA: permissioned denoms may only be sent to whitelisted holders.
    rwa_holders: dict[str, list[str]] = field(default_factory=dict)   # denom -> addresses
    prices_usd: dict[str, Decimal] = field(default_factory=dict)      # denom -> price

    @staticmethod
    def load(path: str | Path) -> "Policy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for k in ("max_tx_usd", "approval_above_usd", "daily_limit_usd"):
            if k in raw:
                raw[k] = Decimal(str(raw[k]))
        raw["prices_usd"] = {d: Decimal(str(p)) for d, p in raw.get("prices_usd", {}).items()}
        return Policy(**raw)

    def usd(self, denom: str, amount: Decimal) -> Decimal | None:
        price = self.prices_usd.get(denom)
        return None if price is None else (Decimal(amount) * price)
