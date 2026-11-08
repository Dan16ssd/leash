"""Bridge to the Injective testnet signer (testnet/signer.mjs).

Leash calls this only after a message got ALLOW or the owner's approval, so the key
never sits behind an unchecked path.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .tx import Msg, MsgSend

SIGNER_DIR = Path(__file__).resolve().parents[1] / "testnet"


class SignerError(RuntimeError):
    pass


def _node(args: list[str], payload: dict | None = None, timeout: int = 90) -> dict:
    proc = subprocess.run(
        ["node", "signer.mjs", *args], cwd=SIGNER_DIR, timeout=timeout,
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True, text=True, encoding="utf-8",
    )
    line = (proc.stdout.strip().splitlines() or ["{}"])[-1]
    data = json.loads(line)
    if proc.returncode != 0 or "error" in data:
        raise SignerError(data.get("error") or proc.stderr.strip() or "signer failed")
    return data


def addresses() -> dict:
    return _node(["address"])


def balance(address: str | None = None) -> str:
    return _node(["balance"] + ([address] if address else []))["inj"]


class InjectiveTestnetSigner:
    """Callable signer for LeashProxy. Set simulate=True to dry-run without spending gas."""

    def __init__(self, simulate: bool = False):
        self.simulate = simulate
        self.last: dict | None = None

    def __call__(self, msg: Msg) -> str:
        if not isinstance(msg, MsgSend):
            raise SignerError(f"{type(msg).__name__} not wired to testnet yet")
        payload = {"to_address": msg.to_address.value, "denom": msg.denom.value,
                   "amount": str(msg.amount.value)}
        self.last = _node(["send"] + (["--simulate"] if self.simulate else []), payload)
        return self.last.get("tx_hash", "simulated")
