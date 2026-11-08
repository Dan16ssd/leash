# Leash

**A provenance-aware firewall for AI agents on Injective.**

AI agents can now sign Injective trades and transfers from a single prompt. That makes
prompt injection a wallet-draining bug: an agent reads a webpage, a tweet or a token
description, and suddenly the recipient or the amount is the attacker's.

Wallet policies today check *how much*. Leash also checks *who decided it*.

Leash records every piece of text the agent saw and where it came from (the owner,
the agent itself, or untrusted content). Before anything is signed, it traces each field
of the transaction (recipient, amount, denom, side, price) back to its sources. If a
protected field was decided by untrusted content, Leash refuses to sign, no matter
how small the amount or how convincing the prompt.

```
 owner chat ─┐
 webpages  ──┤   ┌───────────┐  raw tx   ┌──────────────────────────────┐  signed tx
 tweets    ──┼──▶│  AI agent │─────────▶ │ Leash                         │──────────▶ Injective
 token meta──┘   └───────────┘           │ 1. context ledger (provenance)│
        │                                │ 2. policy: limits, allowlists │
        └──── every input recorded ────▶ │ 3. RWA holder rules           │
              with its source            │ 4. human approval / audit log │
                                         └──────────────────────────────┘
```

The agent is treated as a black box. Leash does not need to trust or inspect its reasoning.

## Status: prototype

| Stage | What | Status |
|---|---|---|
| Prototype | Context ledger, provenance checks, policy engine, RWA holder rule, approval flow, audit log, simulated signer | **done (this repo)** |
| Testnet | Proxy in front of Injective's MCP server; real `MsgSend` / spot orders on Injective testnet; oracle prices | next |
| On-chain guard | Agent key gets only `authz` grants; a CosmWasm guard contract enforces limits and RWA rules so a compromised agent *or* proxy still can't move funds | next |
| Mainnet | Policy dashboard, SDK for agent frameworks, open attack benchmark | later |

## Demo

```
python demo.py
```

The same agent makes the same proposals, judged by a limit-only wallet policy and by Leash:

```
#  scenario                                attack?  limit-only  Leash
1  Owner pays Alice                        no       ALLOW       ALLOW
2  Invoice page swaps the address          yes      APPROVE     BLOCK
3  Tweet triggers a dump at any price      yes      ALLOW       BLOCK
4  Token metadata 'airdrop verification'   yes      APPROVE     BLOCK
5  Owner sends T-bill token to non-holder  no       BLOCK       BLOCK
6  Owner pays a big invoice                no       APPROVE     APPROVE

Attacks auto-signed by limit-only policy:     1/3
Attacks left to a human click by limit-only: 2/3
Attacks blocked outright by Leash:           3/3
```

Scenario 3 is the one limit-based policies can't catch: the sale is small enough to pass
every limit, but the side, size and price all came from a tweet. Every decision is
written to `audit.log.jsonl` with the provenance of each field.

## Tests

```
python -m unittest -v
```

No dependencies beyond Python 3.10+.

## Layout

| File | What it does |
|---|---|
| `leash/ledger.py` | Context ledger: records agent inputs with their source, attributes tx fields back to sources |
| `leash/taint.py` | `Source` / `Tainted` value types |
| `leash/tx.py` | Injective-shaped messages (`MsgSend`, spot market order) |
| `leash/policy.py` | Owner policy loaded from JSON (`policy.example.json`) |
| `leash/guard.py` | Verdicts: ALLOW / NEEDS_APPROVAL / BLOCK, plus the audit log |
| `leash/proxy.py` | Glue: tag → evaluate → approve → sign |

## Known limitations (prototype)

- Attribution matches exact tokens (addresses, numbers, symbols). A value an attacker
  gets the agent to *compute* (for example "send half") shows up as agent-derived, not
  untrusted. The testnet version will require owner confirmation for agent-derived
  protected fields and track derivations explicitly.
- Prices are static in `policy.example.json`. The testnet version reads them from an oracle.
- Signing is simulated. No keys, no network.

## License

MIT
