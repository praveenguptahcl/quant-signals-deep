---
appendix: marker-taxonomy-legend
appendix_version: 1.0.0
title: Marker taxonomy legend (numeric tags, cost tokens, provenance tiers)
scope: global — the unified tag enum; every numeric literal in every chapter carries one tag
---

# Appendix I — Marker-taxonomy legend

## I.1 Numeric-literal tags (unified enum)

**Every numeric literal in every module file carries exactly one tag.**
Untagged numbers fail CI (example-tag lint). Compendium-wide numeric-literal
convention from the proposal: backticked `` `example` `` / `` `fixed` `` /
`` `rule` `` for role-marking, lint-enforced; provenance comes from the tag.

| Tag | Meaning | When to use |
|---|---|---|
| `[documented]` | From a cited source in §S12/§T10 with page/section pinpoint | Paper results, vendor-published specs, measured exchange figures |
| `[default]` | A chosen default, not measured; safe to override during calibration | Config defaults, gate thresholds like cost-gate `k` |
| `[example]` | Illustrative number, not a recommendation | Worked examples, toy tapes, "e.g." figures |
| `[unverified]` | Claimed by a source not yet independently checked | Chatbot-sourced figures promoted with caution, vendor claims unverified |
| `[internal-est]` | Our own estimate, method stated in the chapter | Engineering-hour bands, throughput estimates we computed |
| `[measured]` | Observed by us in a logged run/fixture with seed + date | Fixture outputs, backtest stats from our own harness |

Placement: the tag follows the number it qualifies, e.g.
`` `500` [example] ``, `k = 0.5 [default]`.

## I.2 Cost-level tokens

Every reported performance number carries one cost-level token; the
before/after-cost column in §S9/§T7 is mandatory.

| Token | Includes |
|---|---|
| `BEFORE-COST` | Gross of all trading costs |
| `COMM-ONLY` | Commissions/fees only; no spread, borrow, or impact |
| `FULL-COST` | Full 4-component stack: spread + fees + borrow + impact |

## I.3 Provenance tiers

| Tier | Meaning |
|---|---|
| `[P]` | Peer-reviewed publication |
| `[D]` | Documented industry source (vendor docs, exchange specs, reputable practitioner texts) |
| `[I]` | Internal: our derivation, chatbot-assisted research, or unverified lead promoted with `[unverified]` tag |

## I.4 The COST block contract (summary)

The §S2/§T2 COST sub-block is the single source of truth for costs in the
chapter; re-stating cost numbers elsewhere is a validation failure. Required:
4-component stack (spread / fees / borrow / impact), `fee_schedule_as_of`,
venue/tier/source, `side ∈ {taker, maker, mixed}`, `borrow_bps_per_day`
(0 requires a stated reason), callable reference implementation
`expected_cost_bps(notional, adv_pct, venue, side, urgency)`, and the
executable entry predicate `expected_cost_bps(...) <= k * edge_bps`.
All cost values tagged per §I.1; `[measured]` on observed cost figures.
