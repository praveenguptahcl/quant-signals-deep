# Session 03 — Risk / regimes / portfolio / compliance
## Decisions for the standalone-module format (driven by R01, R12, R15, R11, R03; corroborated by R04, R07, R13, R16, R17)

### 1. Risk contract (R01 C1–C5, C8, R13 item 2, R16 items 1/4)
- Every T chapter gets a fenced YAML `RISK CONTRACT` block: `per_trade_R`, `daily_loss_stop`,
  `max_gross`, `kill_conditions[]`, `enforcement`, `calibration_recipe` (data window / objective /
  shrinkage — R01 C16). Every numeric literal carries exactly one machine tag: `example` or `fixed`.
- `enforcement` is a closed enum: `intraday-hard` | `review-only` (next-day trigger), ending the
  divergent "daily loss stop" semantics R01 found across chapters.
- Risk contract includes a `max_adverse_per_trade` row = stop distance + commissions + assumed slippage;
  a chapter whose worked examples ever exceed 1.0× this bound fails the template CI gate (R01 C5, R03 M11).
- One canonical `PositionState` JSON schema defined once (shared §0, imported by reference); all T
  chapters reference it; paper-ledger schema is not re-declared per chapter (R01 C2).

### 2. Kill-switch state machine (R01 C3, C13; R16 item 1)
- Mandatory four-state machine per strategy module: `ARMED` → `TRIPPED` → `RECOVERY` → `ARMED`;
  prose triggers become named transitions with thresholds; `RECOVERY` requires a mandatory re-arm
  checklist (feed healthy, sequence gap closed, book re-snapshot, manual confirm) — no silent re-arm.
- Per-chapter alert table: metric / threshold / severity / destination / expected response (R16 item 4).

### 3. F1–F5 extended to S/T modules (R01 C4, C12; R03 M7; R12 C10; R16 item 3)
- Adopt: RB-list fail-safes ported as a mandatory per-chapter fail-safe contract — S chapters get
  estimator-disagreement block (second estimator + tolerance + `UNKNOWN` rule); T chapters get the
  fail-safe contract with trigger → action → re-arm rows.
- `UNKNOWN` is the single canonical degradation token across all 250 chapters: stale input → emit
  `UNKNOWN` → downstream restricts. `UNKNOWN` currently appears 0× in the corpus; gate QC checks it (R01 C4, R16).
- Feed-outage safe mode mandatory in every T chapter: flatten immediately, never interpolate (R16).

### 4. Regime gates (R01 C8, R11 M7, R03 C14, R04 item 13, R07 item 10, R15 C6)
- Machine-readable record per gate:
  `{regime_id, direction, mechanism, condition, action, min_lag, unknown_behavior}`
- `direction` ∈ `amplifies | degrades | inverts`; `action` ∈ `veto | halve | double | widen_stops | pause_entry`;
  `unknown_behavior` required on every gate (default `restrictive`).
- `applicable_regimes: [R###, …]` becomes part of the YAML header; each gate carries a one-line impact
  note. 0/200 chapters currently reference any R-ID — annotation starts after the schema lands (R15 C6).
- RSV provenance stamp required on every regime value consumed: `{regime_id, state, value,
  estimator_version, data_vintage, computed_at}` (R16 item 3).

### 5. Compliance section — new mandatory S13/T11 (R12 C1–C6, M7–M9, m14–m15)
- New mandatory section S13/T11 "Regulatory & venue-compliance contract" in all 200 chapters; zero
  compliance QC items in merge-protocol today — add a compliance gate before any chapter merges.
- Required coded rules (minimum, in the normative pseudocode, not prose):
  1. `stp_flag` + pre-trade self-match check on every order path (wash/self-trade prevention).
  2. Bona-fide-intent rule on every chapter posting passive orders (min quote life, cancel-to-trade ceiling).
  3. Per-venue message-rate ceiling + cancel-to-trade guard.
  4. 3-line pre-trade control: price collar, notional ceiling, duplicate-order window (fat-finger).
  5. Decision-log schema with mandatory fields: `event, order_id, ack_id, nbbo_snapshot, rule_id_fired`;
     append-only store; stated retention.
  6. Halt/auction state table: `CONTINUOUS_TRADING / HALTED / AUCTION / CLOSED` × allowed action per
     state (covers mid-position halts, not just backtest exclusion).
  7. Locate/availability assertion in every chapter with a short leg (Reg-SHO).
  8. Public-dissemination gate for news ingestion: story must match a public wire print with
     timestamp ≤ t₀ before arming (MNPI).
  9. Data-entitlement assertions at startup: entitlement key present, redistribution allowed/denied,
     display-only flag per licensed feed.
  10. Post-exit cooldown or max-flips-per-window on every exit rule (whipsaw bound).
- Doctrine: "pseudocode is normative; prose is commentary" — every prose guard must appear in the code
  block; guardrail numbers are `fixed`, illustration numbers `example` (R12 C11–C12).

### 6. Triage card (R15 C1, C4; R11 M16)
- Fixed 5-field card directly under the chapter header (also mirrored in YAML frontmatter):
  `edge_verdict · build_cost · data_cost · latency_class · risk_class`.
- Enums: `edge_verdict` ∈ `strong | marginal | unproven | negative`; `latency_class` ∈
  `µs | ms | sec | min | daily`; `risk_class` ∈ `low | medium | high | critical`.
- `build_cost`: three hour bands `prototype / research-grade / production` (R15 C3); `data_cost`:
  one line with research $/mo + production $/mo (R15 M11); header block also carries `maturity`
  (`concept | research-grade | paper-validated | production-ready`) and `tier, hours_lo/hi` (R15 C1, M12).

### 7. Capacity / impact & correlation metadata (R11 C1, C3, M8; R17 item 7; R15 C2)
- Mandatory "Capacity & impact" subsection per chapter: `max_notional` as a function
  `f(participation_cap, ADV, spread_regime)` — parameterized, not prose; `impact_function` reference
  (e.g. Kyle λ, Amihud); decay half-life.
- Module output contract per chapter (R11 C1, R01 C12): canonical `SIGNAL_VECTOR =
  {symbol, timestamp, direction ∈ {−1,0,+1}, score ∈ [−1,1], confidence ∈ [0,1], capital_scale,
  estimator_version, data_vintage}`; output schema + units + freshness SLA + stale (`UNKNOWN`) behavior.
- Sizing as a fenced function, stable formula / example numbers (R11 C4):
  `shares = f(risk_budget_R, stop_distance, vol_estimate, ADV_cap, cost)`.
- Correlation metadata in header: `correlated_with: [IDs]` + `shares_data_feed_with: [IDs]` +
  `crowding_proxy` field (R11 M8).
- Dependency DAG from one machine edge list as single source of truth; S5/T3 tables generated from it;
  CI asserts S5↔T3 symmetry (fixes 64 unreciprocated T→S links; R15 C2, R11 C2).

### Cross-cutting conventions adopted
- Strategy chapters are T1–T10 (not T1–T12); schema docs reconciled; T8 title normalized to
  "Failure modes"; T1/S1 verdict tables get one canonical schema including a Capacity row (R01 meta,
  R11 m12/m16, R15 M8/M9).
- One canonical `example` token for illustrative literals (replaces the ≥5 current variants; R03 C4);
  `example` never on load-bearing guardrails.
