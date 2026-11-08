"""Injective-shaped transaction proposals. Field values are Tainted so the guard can see provenance."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .taint import Tainted


@dataclass(frozen=True)
class MsgSend:
    """Mirrors cosmos.bank.v1beta1.MsgSend (single coin)."""

    to_address: Tainted   # str, bech32 "inj1..."
    denom: Tainted        # str, e.g. "inj", "peggy0xdAC1...", "factory/inj1.../tbill"
    amount: Tainted       # Decimal, human units

    type_url = "/cosmos.bank.v1beta1.MsgSend"

    def summary(self) -> str:
        return f"send {self.amount.value} {self.denom.value} -> {self.to_address.value}"


@dataclass(frozen=True)
class MsgSpotMarketOrder:
    """Mirrors injective.exchange.v1beta1.MsgCreateSpotMarketOrder (simplified)."""

    market: Tainted       # str, e.g. "INJ/USDT"
    side: Tainted         # "buy" | "sell"
    quantity: Tainted     # Decimal, base units
    worst_price: Tainted  # Decimal, quote per base

    type_url = "/injective.exchange.v1beta1.MsgCreateSpotMarketOrder"

    def summary(self) -> str:
        return (f"{self.side.value} {self.quantity.value} on {self.market.value} "
                f"(worst price {self.worst_price.value})")

    @property
    def notional(self) -> Decimal:
        return Decimal(self.quantity.value) * Decimal(self.worst_price.value)


Msg = MsgSend | MsgSpotMarketOrder
