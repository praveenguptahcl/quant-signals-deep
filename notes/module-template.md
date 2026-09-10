# Module file template — v1.0.0

Machine-checkable spec for writing one module file (`S001–S100` signals,
`T001–T100` strategies, `R001–R050` regimes). Derived from
`MODULE_FORMAT_PROPOSAL.md` §3. Status: **normative** for the 250-module build.
`notes/chapter-template.md` is archived; this file supersedes it.

## 0. Orientation

- Every module file has the exact section order below. Section **numbers are
  frozen** (`§0, §1, §1.5, §S0/§T0/§R0, §S1–§S12, §T1–§T10, §R1–…`); new content
  lands in front-matter, the prepended contract block, or mandatory fixed-order
  **sub-blocks** inside existing sections — never as new section numbers.
- "M" = mandatory · "C" = conditional (only when the stated condition holds)
  · "O" = optional.
- A module file is **standalone**: it may import the 11 global appendices
  (`modules/appendices/`, by reference, never duplicated) and its own
  `§S0/§T0` + fixtures; it must not require MASTER.md, `notes/cost-model.md`,
  or another chapter to be understood or implemented.
- Numeric-tag law: **every numeric literal carries exactly one tag** from the
  unified enum — `[documented] [default] [example] [unverified] [internal-est]
  [measured]` (legend: appendix i). Untagged numbers fail validation.

## 1. File skeleton

```
§0    Front-matter (YAML, machine-parsed) .................. M
§1    5-minute reviewer card ............................... M
§1.5  Cheapest/least-build path .......................... M
§S0   Module contract (signals) .......................... M (kind=signal)
§T0   Module contract (strategies) ....................... M (kind=strategy)
§R0   Module contract (regimes) .......................... M (kind=regime)
§S1–§S12 / §T1–§T10 / §R1–§R10  frozen legacy sections ... M
      with mandatory fixed-order sub-blocks (see §4 below)
§S12/§T10 Source log + unverified leads .................. M
APP   AI build prompt (appendix to each file) ............ M
```

§S1/§T1 legacy content is subsumed by the §1 reviewer card; keep the §S1/§T1
header with a pointer row ("see §1") so numbering stays intact.

## 2. §0 Front-matter — exact key list

```yaml
---
id: S001                      # SID, e.g. S001 / T042 / R017
kind: signal                  # signal | strategy | regime
version: 1.0.0                # semver of this module file
template_version: 1.0.0       # must equal this template's version
status: draft                 # draft | review | approved | deprecated
batch: SB1                    # stage batch key (stage↔ID is the machine key)
family: A                     # microstructure & order flow, etc.
provenance_tier: D            # P | D | I (legend: appendix i §I.3)
sources:                      # citable sources used as facts
  - "Cont, Kukanov & Stoikov (2014), arXiv:1011.6402"
unverified_sources: []        # ALWAYS PRESENT, even if empty
consumes:                     # machine edge list (mirrors deps.yaml)
  - {id: S003, version_pin: 1.0.0, role: confirm}
regime_ids: []                # provisional until R001–R050 annotation pass
correlates_with: [S003]
shares_data_feed_with: [S003, T001]
seed: 42
rng: {algorithm: PCG64, lib_pin: "numpy==2.1.0"}
plot_script: scripts/plot_S001.py
test_cmd: "python -m pytest modules/tests/test_S001.py -q"
datasets:
  - name: US equities L1
    vendor: Databento
    product: MBP-1
    schema_version: "3"
    fingerprint: "sha256:…"
    vintage: "2026-09-09"
    rights: licensed
changelog:
  - "1.0.0 2026-09-10: initial module per template v1.0.0"
---
```

All keys above are mandatory. `unverified_sources: []` must be present even
when empty. `fee_schedule_as_of` lives in the COST block (§S2/§T2), not here.

## 3. Section specs

### §1 Reviewer card (M) — locked row schema

Table with exactly these rows, in order: Module · Edge verdict (enum:
`AFTER-COST-EDGE | PREDICTIVE-FEATURE-ONLY | NO-DOCUMENTED-EDGE |
INSUFFICIENT-EVIDENCE`) · after-cost token (`BEFORE-COST | COMM-ONLY |
FULL-COST`) + one-sentence verdict · Build cost (`Tier · h · $loaded`) · Data
cost $/mo (research + production) · `latency_class` · `risk_class` · Capacity
($ band) · Executability · Risk summary · "When it dies" triggers · Regime
gates (provisional) · Emits (`signal_vector | order_intents`). Every number
tagged. §S9/§T7 + §S8/§T6 are the evidence layer for these rows.

### §1.5 Cheapest/least-build path (M) — fixed sub-blocks, in order

1. **Prototype hour band** (e.g. `20–60 h [internal-est]`).
2. **Cheapest-source row**: `min_tier, latency_class, required_fields,
   price_band, build_or_buy` — structured, one row.
3. **Resource budget row** + compute pattern token (`per_event | per_bar |
   per_snapshot`).
4. **Skip list** — what the cheapest build explicitly skips.
5. **DO-NOT-CUT list** — causality assertions, COST block, kill/safe-mode,
   audit log, bona-fide-intent + self-trade prevention, provenance tags,
   fixtures, secrets-via-env. Never shortened.
6. **Escalation gate** — the observable conditions that force an upgrade from
   the cheapest path.

### §S0/§T0/§R0 Module contract (M) — fixed sub-blocks, in order

1. **Typed signature**: `signal(state, events, cfg) -> SignalVector` (S/R) or
   the T-module intent emitter `emit(state, signals, cfg) -> list[OrderTicket]`.
   The core function — not ingest code — and it handles documented edge cases.
2. **Config dataclass**: one table — parameter, type, default, range, status
   ∈ {fixed, default, calibrate, example, internal-est}.
3. **Canonical schema mapping**: vendor columns → Appendix A/B/C/D (as
   applicable), stated once here and never restated.
4. **Time contract**: clock domain, int64 ns, UTC, `max_skew`, jitter budget,
   bar-label rule, staleness TTL, gap policy (normative wording: appendix e
   §E.5); fixed-wording **Timing box**: ``signal@t (<cadence>, <TZ>) →
   earliest fill @open(t+1)``.
5. **Market-state table**: `CONTINUOUS_TRADING | HALTED | AUCTION | CLOSED` —
   what the module does in each (R: plus Lag contract).
6. **Module-state enum**: `OK | DEGRADED | UNKNOWN | OFF`; invalid input →
   `UNKNOWN`, never interpolate (appendices f, k). Error taxonomy maps every
   documented failure to one state; unmapped → `UNKNOWN` + alert.
7. **Risk contract (T only)**: fenced YAML (`per_trade_R, daily_loss_stop,
   max_gross, kill_conditions[], enforcement ∈ {intraday-hard, review-only}`);
   mandatory `max_adverse_per_trade` row; kill-switch state machine
   `ARMED → TRIPPED → RECOVERY → ARMED` + re-arm checklist.
8. **Ops tail**: schedule spec + owner, health checks, alert table, resource
   budget, runbook stub — in this section, not scattered.
9. **Secrets = env-only.** No secrets in the file; CI greps for them.
10. **May / must-NOT line** (doctrine): S emits SignalVector only, never
    orders; T emits OrderTicket intents only, never places orders; R emits
    regime labels + cost-interface adjustments.
11. R only: **"Cost interface: regime state → cost-function adjustment"** block.

### §S2/§T2 (M) — fixed-order mandatory sub-blocks

Universe · **Entry rule** (Boolean expressions, no prose-only conditions) ·
**Exits** (with post-exit cooldown) · **Position sizing** as a fenced function
``shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)`` ·
Risk limits · **COST block** (single source of truth: 4-component stack;
callable `expected_cost_bps(notional, adv_pct, venue, side, urgency)`;
`fee_schedule_as_of`; venue/tier/source; `side ∈ {taker, maker, mixed}`;
`borrow_bps_per_day` with a stated reason if `0`; all values tagged) ·
**Execution/fill model table** (latency, partial-fill, impact, adverse-fill) ·
**Robustness + Compliance sub-block** (§4.1) · **Parameter table**
(symbol, value, tag, sensitivity) · **Timing box** (fixed wording, §3 §S0.4).

### §S3/§T3 (M)

Precise math + **normative pseudocode** (pseudocode is normative; prose is
commentary). Every prose guard appears in the pseudocode. Includes:
- **Cost gate as executable predicate**:
  `expected_cost_bps(...) <= k * edge_bps` (default `k = 0.5 [default]`
  unless the chapter calibrates otherwise).
- **Causality assertions inline**: `assert fill_event > signal_event`;
  no-signal-bar-fills is a mandatory unit test.
- Consumed formulas: pinned verbatim excerpts ≤10 lines, with provider ID +
  version + spec-hash (CI hash-checked).

### §S4/§T4 (M)

Worked example shipped as `modules/fixtures/<SID>_tape.csv` + expected outputs
+ tolerance. CSV carries a **TYPE header** comment
(`# TYPE: accounting-demo | validation-run`). T4 rows show the cost-function
call (inputs → bps → $), not just a cost column. 3–5 acceptance tests in
`modules/tests/test_<SID>.py`; `test_cmd` in §0 runs them.

### §S5–§S11 / §T5–§T9 (M)

- S5/T3 tables generated from `deps.yaml` where applicable — never
  hand-written; CI asserts symmetry.
- Regime gates as machine records:
  `{regime_id, direction ∈ amplifies/degrades/inverts, mechanism, condition,
  action ∈ veto/halve/double/widen_stops/pause_entry, min_lag,
  unknown_behavior}` (restrictive default).
- Failure modes as trigger → detect → action → recovery rows, each with a
  `check:` line.
- Evidence tables with mandatory **before/after-cost column + cost-level token
  + selection disclosure**; `[measured]` provenance on observed cost figures.
- Conditional domain extensions (C on `§0` domain field): options → Pricing &
  Greeks / expiry-assignment blocks; crypto → funding interval / margin &
  self-liquidation blocks. Shared material in appendices, never duplicated.
- Data rights row per dataset (appendix j) in §S6/§T5.

### §S12/§T10 Source log + unverified leads (M)

- Numbered source list (citable facts only).
- **Chatbot source log**: which bot, which questions, date; chatbot output is
  leads, never facts.
- **Unverified leads**: chatbot-only material segregated here — never in
  evidence tables, never promoted to documented facts.
- Per-chapter process metadata collapsed/moved out of the reference tail.

### AI build prompt (M, appendix to each file)

Copy-paste prompt for any chat agent: module ID, §0 summary, cheapest path
(§1.5), fixture/test commands, and the definition of done:
**`test_cmd` exits 0.**

## 4. Special sub-block specs

### 4.1 Compliance sub-block (mandatory inside §S2/§T2-Robustness for T; §S2 for S)

Minimum **10 coded rules**, numbered C1–C10+:

| Code | Rule |
|---|---|
| C1 | STP + self-match prevention: no order intent that could match our own resting interest; self-trade prevention flag on every ticket |
| C2 | Bona-fide intent: every intent must be passable by the cost gate and sized within risk limits; no quote entered without intent to trade |
| C3 | Message-rate / cancel-to-trade ratio cap with venue thresholds and throttle action |
| C4 | Pre-trade fat-finger trio: price collar vs reference, max notional per ticket, max tickets per interval |
| C5 | Decision-log schema compliance (appendix g): every material action logged, hash-chained |
| C6 | Halt/auction state table: module behavior in HALTED/AUCTION/CLOSED per the market-state table |
| C7 | Locate check (short sales): easy-to-borrow list or locate obtained before SHORT intent; Reg-SHO threshold securities blocked |
| C8 | Public-dissemination gate: no signal/intent data published externally without review |
| C9 | Data-entitlement assertions per dataset (appendix j) |
| C10 | Post-exit cooldown: no re-entry for the chapter's cooldown interval after an exit or compliance block |

Chapters add C11+ as needed. Each rule states: trigger → check → action →
log record.

## 5. Per-section MANDATORY-vs-conditional checklist

| Section | S | T | R | Notes |
|---|---|---|---|---|
| §0 front-matter | M | M | M | all keys; `unverified_sources` always present |
| §1 reviewer card | M | M | M | locked row schema |
| §1.5 cheapest path | M | M | M | DO-NOT-CUT list never shortened |
| §S0/§T0/§R0 contract | M | M | M | typed signature, Config, time, states, ops, env-only secrets |
| §S2/§T2 sub-blocks | M | M | M | includes COST block + Compliance (10 rules) |
| §S3/§T3 math+pseudocode | M | M | M | cost-gate predicate + causality asserts |
| §S4/§T4 fixtures+tests | M | M | M | CSV with TYPE header + `test_<SID>.py` |
| §S5–§S11/§T5–§T9 | M | M | M | deps-generated tables, regime gates, failure rows, evidence tables |
| §S12/§T10 source log | M | M | M | unverified leads segregated |
| AI build prompt | M | M | M | definition of done = `test_cmd` exits 0 |
| Options Pricing & Greeks | C | C | — | only if `§0` domain = options |
| Crypto funding/margin | C | C | — | only if `§0` domain = crypto |
| §R0 Lag contract | — | — | M | min_lag, unknown_behavior |
| §R0 Cost interface | — | — | M | regime state → cost-function adjustment |

## 6. Mechanical validation checklist (CI)

A module file passes iff **all** of the following hold:

1. [ ] YAML front-matter parses with `yaml.safe_load` (no tabs, no duplicate keys).
2. [ ] Every mandatory `§` header is present with exact numbering and order:
    `§0, §1, §1.5, §S0|§T0|§R0, §S2…§S12` (or T/R equivalents).
3. [ ] `template_version: 1.0.0` in §0.
4. [ ] §S3/§T3 pseudocode contains the cost-gate predicate
    `expected_cost_bps(...) <= k * edge_bps` verbatim (modulo whitespace).
5. [ ] §S2/§T2-Robustness contains a Compliance sub-block with ≥10 coded
    rules (C1–C10+).
6. [ ] **Every numeric literal in prose** carries one tag from
    `[documented] [default] [example] [unverified] [internal-est] [measured]`
    (example-tag lint; unlabeled cost numbers fail). Machine-parsed `§0` data
    fields, section numbers (`§S2`), appendix letters, rule codes (`C1`),
    fail-safe codes (`F1`), and module IDs (`S001`) are identifiers, not
    literals, and are exempt.
7. [ ] COST block is the single source of truth: no cost number restated
    outside it (cost-block single-source check).
8. [ ] `modules/fixtures/<SID>_tape.csv` exists with TYPE header;
    `modules/tests/test_<SID>.py` exists and `test_cmd` exits 0.
9. [ ] `assert fill_event > signal_event` (no-signal-bar-fills) present in
    pseudocode and enforced in tests.
10. [ ] Fixed wording present: Timing box
    ``signal@t (<cadence>, <TZ>) → earliest fill @open(t+1)``.
11. [ ] No secrets in the file (secrets grep); secrets referenced env-only.
12. [ ] Cross-references use `Appendix <letter> (v<version>)` pins; S5/T3
    tables match `deps.yaml` (symmetry check).
13. [ ] Unverified-lead material appears only in §S12/§T10, never in evidence
    tables.
14. [ ] `unverified_sources` key present in §0 (empty list allowed).

## 7. Do-not-regress list (carried from the proposal §4)

t→t+1 causality discipline · `(example)` honesty tagging extended to the
unified enum · synthetic-data labeling + named seeds · "simulated only —
requires MBO/ITCH" honesty · S12/T10 source-log + unverified-leads segregation
· "Where the example is optimistic" sections · before/after-cost distinction ·
RB-list F1–F5 fail-safes · strategy-emits-intentions-only doctrine · on-disk
ledger discipline · stage↔ID mapping as machine key.
