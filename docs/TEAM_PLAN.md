# Leash: Team Plan

**Injective Hacker House Bangkok** · Dec 1–10, 2026 · Demo Day Dec 9
**Applications close: Nov 10, 2026.** Every team member submits their own form (project "Leash", team size 4).

Form: https://xsxo494365r.typeform.com/to/zeKuqtdg

---

## 1. What Leash is

A firewall for AI agents on Injective.

- **Provenance check:** if the recipient, amount or price came from untrusted content (webpage, tweet, token metadata), block it.
- **Agent tiers:** trust score built from Leash's own audit log. New agents start Untrusted with small limits.
- **Policy:** spend limits, address book, allowed tokens, RWA holder whitelist, human approval for big tx.
- **Next:** CosmWasm guard contract on-chain, so even a hacked agent or proxy can't bypass the rules.

---

## 2. Status

| Stage | What | Status |
|---|---|---|
| Prototype | Ledger, provenance check, policy, RWA rule, tiers, audit log, 2 demos, 17 tests | ✅ done |
| Testnet | Real transfers on Injective testnet through Leash | ✅ done (first tx 2026-11-08) |
| Agent integration | Real LLM agent via Injective MCP server, spot orders | ⬜ next |
| On-chain guard | CosmWasm contract + authz enforces tier limits and RWA rules | ⬜ hacker house |
| Mainnet | SDK, dashboard, pilot users | ⬜ later |

---

## 3. Project score (reviewer view)

| Criterion | Score /10 |
|---|---|
| Fit with themes (AI, RWA, privacy) | 9.5 |
| Problem / need | 9 |
| Originality | 8.5 |
| Doable in 10 days | 8 |
| Business potential | 7.5 |
| Team credibility | 7 |
| Current progress | 7.5 |
| **Overall** | **~8.8 (≈9 once repo is public)** |

### How to raise the score

- [x] Real Injective testnet transaction (+0.7)
- [ ] Public GitHub repo + 60-second demo video (+0.4)
- [ ] One Injective builder says "we'd use this" (+0.3)
- [ ] Privacy shown in the prototype, e.g. private limits (+0.2)

---

## 4. Difficulty score (how hard to build)

| Part | Difficulty | Time | Owner |
|---|---|---|---|
| Prototype (ledger, policy, tiers) | done | done | Danny |
| Testnet transfers via Injective TS SDK | 4/10 | 0.5–1 day | Danny |
| Proxy in front of Injective MCP server + real LLM agent | 6/10 | 2–3 days | Danny |
| Agent-computed values ("send half") | 7/10 | 2 days | Danny |
| CosmWasm guard contract + authz (**needs Rust**) | 8/10 | 4–6 days | Teammate 2 |
| Attack suite / benchmark | 4/10 | 2–3 days | Teammate 3 |
| Dashboard + demo video + pitch | 3/10 | 2–3 days | Teammate 4 |
| ZK proof of AI model inference | 10/10, **don't do it** | n/a | n/a |

**Overall difficulty: ~6/10.** Biggest risk: the CosmWasm contract. Start learning it now.

---

## 5. Team roles

| Who | Owns | Start now |
|---|---|---|
| **Danny** | Ledger + proxy + testnet integration | Injective TS SDK testnet transfer |
| **Teammate 2** | On-chain guard (CosmWasm + authz) | Rust + CosmWasm tutorial, Injective testnet deploy |
| **Teammate 3** | Red team: poisoned invoices, tweets, token names → benchmark | Write 20 attack cases |
| **Teammate 4** | Dashboard, demo video, Demo Day pitch | 60-second demo video of `demo.py` + `tiers_demo.py` |

---

## 6. Agent tiers

| Tier | How to get there | Max per tx | Auto-approve up to | Daily |
|---|---|---|---|---|
| Untrusted | every new agent (score 20) | $50 | $20 | $100 |
| Verified | score ≥ 40 | $500 | $100 | $1,000 |
| Elite | score ≥ 80, ≥ 30 signed tx, no recent injection | $5,000 | $1,000 | $20,000 |
| Revoked | 3 blocked injection attempts | $0 | n/a | $0 |

| Event | Score |
|---|---|
| Signed tx | +2 (max +60 total) |
| Owner approved flagged tx | +3 |
| Owner rejected flagged tx | −5 |
| Blocked by policy | −2 |
| Blocked: injection | −15 |

Extra rule: any tx more than 3× the agent's biggest past tx needs the owner's approval, even for Elite.

---

## 7. Demo results

**`python demo.py`**

| Scenario | Attack? | Limit-only wallet | Leash |
|---|---|---|---|
| Owner pays Alice 40 USDT | no | ALLOW | ALLOW |
| Invoice page swaps the address | yes | APPROVE | BLOCK |
| Tweet triggers a dump at any price | yes | **ALLOW** | BLOCK |
| Fake airdrop in token metadata | yes | APPROVE | BLOCK |
| Owner sends T-bill token to non-holder | no | BLOCK | BLOCK |
| Owner pays big invoice 300 USDT | no | APPROVE | APPROVE |

Leash blocks 3/3 attacks. A limit-only wallet auto-signs 1 and leaves 2 to a human click.

**`python tiers_demo.py`**

- `yield-bot`: Untrusted → Verified → falls for poisoned notice 3 times → **Revoked**
- `rebal-bot`: reaches **Elite** → asks to move 50× its usual amount → owner says no → drops to Verified

---

## 8. Form answers (draft)

- **Project name:** Leash
- **Description (≤250 chars):** Leash tracks where every number in an AI agent's Injective transaction came from. If the amount or recipient traces back to a tweet, webpage or token metadata instead of the owner, it won't sign. Rules are enforced on-chain, not by trust.
- **Category:** AI & agents
- **Stage:** Prototype
- **What have you shipped:** Working prototype: Leash traces every field of an agent's proposed Injective transaction back to what the agent read and blocks 3/3 prompt-injection attacks in our demo (poisoned invoice, tweet, token metadata), while a limit-only wallet auto-signs 1. Agent tiers built from audit history: new agents start with small limits, repeated injection attempts revoke them. Includes RWA holder whitelist, approval flow and audit log. Live on Injective testnet: owner's payment broadcast, injected payment blocked before reaching the chain. Next: real LLM agent via Injective's MCP server, then on-chain CosmWasm guard.
- **Team size:** 4 · **In person:** 4
- **Need help with:** Injective Integration, Technical Mentorship, Ecosystem Partnerships
- **Anything else:** AI agents can now sign trades on Injective from a single prompt. One prompt injection can drain a wallet or send a permissioned RWA token to the wrong holder. Leash lets funds and RWA issuers trust autonomous agents with real assets. Free SDK for agent builders; paid hosted policy + audit for funds and RWA issuers.

---

## 9. Checklist before Nov 10

- [ ] Push repo public: `github.com/Dan16ssd/leash`
- [ ] Add 3 teammates as collaborators
- [ ] Record 60-second demo video
- [ ] Danny submits form
- [ ] Teammate 2 submits form
- [ ] Teammate 3 submits form
- [ ] Teammate 4 submits form
- [ ] Check Dec 1–10 attendance for everyone
