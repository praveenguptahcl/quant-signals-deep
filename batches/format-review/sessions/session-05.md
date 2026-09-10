# Session 05 — Human-review IA, cheapest-build path, final convergence

NOTE: sessions/ held no session-01..04 summaries (dir empty); all decisions below are S5
synthesis directly from R01–R20.

## 1. Human-review IA (decisions)

**§S1/T1 — the 5-minute reviewer card (canonical row schema, locked).** Fixed rows, no prose
paragraphs: Module (ID/kind/version/maturity) · Edge verdict enum (AFTER-COST-EDGE /
PREDICTIVE-FEATURE-ONLY / NO-DOCUMENTED-EDGE / INSUFFICIENT-EVIDENCE) · After-cost token
(BEFORE-COST / COMM-ONLY / FULL-COST) + one-sentence honest verdict (no numbers) · Build cost
(`Tier M · 20–60 h · $3k–9k loaded`; links §1.5 bands) · Data cost ($/mo research + $/mo
production; min data tier) · Latency class / risk class · Capacity ($ band; signals and
options-pillar depth included) · Executability (live-executable | simulated-only) · Risk summary
(per-trade R, daily stop, kill triggers) · "When it dies" (trigger phrases only) · Regime gates
(R-IDs + direction; provisional) · Emits (signal-vector | orders).
Rule: §1 shows tokens and one-liners only; every number lives in its canonical section and is
linked, never restated. (Resolves R09-M9 "one verdict location" vs R01-M11/R05-M9 "promote
verdict to T1": §1 = summary layer, §S9/§T7 + §S8/T6 = evidence layer.)

**Single source of truth per threshold/rule.** One rule stated once, in its canonical section;
prose, pseudocode, and ledgers reference parameter/block names only. §S0/T0 config block (YAML)
is the parameter source of truth; normative pseudocode is the rule source of truth ("pseudocode
is normative; prose is commentary"). §T3 must include the cost gate as an executable predicate
(expected_cost_bps(...) <= k * edge_bps). Consumed formulas are never re-derived by hand:
consumer embeds a pinned verbatim excerpt (≤10 lines, source ID + version + spec-hash) in an
annex; CI hash-checks it against the pinned version. (Resolves R04/R14-C7 self-containment vs
R16-M12 single-source.)

**Where things live (resolved).**
- After-cost verdict: canonical in §S9/§T7 (mandatory Before/after-cost column, cost-level
  token, selection-disclosure field: variants tested + DSR or "not computed"); §S1/T1 = token
  + one-sentence verdict; §S8/T6 links to §S9/§T7, never restates numbers.
- Kill conditions: single "Safe-mode & kill contract" in §T5 (signals: §S6-adjacent OPS block):
  ARMED→TRIPPED→RECOVERY state machine, trigger conditions, TRIPPED actions, re-arm checklist;
  module-state enum OK / DEGRADED / UNKNOWN / OFF; RB-list F1–F5 ported into every S/T chapter.
  §T2 Risk limits references it by name only.
- Failure modes: §S10/T8 only (title normalized to "Failure modes"); ranked table (condition,
  how detected, action, recovery) sorted by expected-P&L-impact × likelihood; every mitigation
  carries a `check:` line (invariant + where to assert).
- Compliance: NOT a new numbered section — T1–T10 / S1–S12 numbering frozen (merge keys,
  22-item QC, stage mapping depend on it; resolves R12-C1 against renumbering risk). Mandatory
  "Compliance" sub-block inside §T2-Robustness (bona-fide-intent rule, self-trade prevention,
  message-rate/cancel-to-trade guard, Reg-SHO locate, MNPI gate, pre-trade collar/notional/dup
  checks) + "Data rights" row in §S6/T5 (entitlement, redistribution flag, display-only,
  expiry, audit field).

**Legend/glossary/cross-refs (resolved).** Document head (single global): glossary, provenance
taxonomy, numeric-tag enum ([documented]/[default]/[example]/[unverified]/[internal-est]/
[measured]), cost levels L0–L3, latency classes, module-state enum, internal taxonomy key
(SB1, Family A, …). In-chapter: expand acronym at first use, bare after; T030-style "Jargon,
defined once" block for nonstandard terms; one-line provenance legend in every chapter header
block; per-section provenance tags for mixed-evidence chapters. Every numeric literal carries
exactly one tag; [default] = recommended starting config (folds R10-M9 two-tier tagging into
R18-C2's single enum). Every S###/T###/R### mention is a Markdown link to its stage anchor —
never plain text; notes/ refs always full repo-root paths; bare refs get a one-line recap;
machine edge list in front-matter (`consumes: [{id, version}]`); §S5/§T3 tables generated
from that edge list (CI symmetry check).

## 2. Cheapest-build path (decisions)
New mandatory block §S1.5/§T1.5 "Cheapest build path (prototype)", immediately after §S1/T1,
before §S2/T2. Fixed contents: (1) Prototype band: canonical line
`Tier M · 20–60 h · $3k–9k loaded` + staging label (prototype → research-grade → production,
each with hour band). (2) Minimal data: structured cheapest-source row — min_tier,
latency_class, required_fields, price_band, build_or_buy; crypto mapping: free venue
websocket = Tier-0-equivalent. (3) Minimal compute: resource-budget row (CPU/RAM/disk per
symbol-day at stated cadence, reference hardware) + one-line compute pattern ("streaming
O(1)/event" vs "vectorized batch recompute" + throughput envelope); full 5-row COMPUTE
contract mandatory for intraday/HFT, optional for daily-bar. (4) Skip list: enumerated
deferrals (second estimator, cloud deployment, maker variant, multi-venue). (5) DO-NOT-CUT
list (normative even in prototype): causality contract, single COST block, kill/safe-mode
contract, audit decision-log, bona-fide-intent + self-trade rules, provenance tagging,
fixture-based acceptance test, secrets-via-env. (6) Escalation gate: what evidence unlocks
research-grade/production (acceptance checklist: walk-forward + embargo, min OOS trades,
declared cost level).

## 3. Final section outline (M = mandatory, O = optional)
**§0 front-matter (M, all):** id, kind, version x.y.z + one-line changelog, template_version,
provenance, family, emits (signal-vector|orders), tier, hours_lo/hi, data_tier,
latency_class, risk_class, maturity enum, edge_verdict enum, consumes [{id, version}],
regime_ids[], seed, plot_script path.
**SIGNALS (S0–S12):** §1 reviewer card (M) · §1.5 cheapest build path (M) · §2 idea (M) ·
§3 math (M): Timing-contract box at top, S3a Formula-frozen / S3b Parameters&defaults
(Status FIXED|CALIBRATE|EXAMPLE, edge-case row, units/return/day-count rows), Label contract
+ Validation protocol · §4 worked example (M): Repro header (TYPE=accounting-demo|
validation-run, script, seed, lib pins, vintage), S4a signal-computation / S4b
illustrative-economics split, fixture pointer · §5 dependencies (M, generated from edge
list) · §6 data (M): Timestamps block, canonical schema (field/dtype/units/nullable/enum/
partition/sort), dataset fingerprint, Data rights row, F1–F5 fail-safes, session calendar ·
§7 build & compute (M; Live-pipeline vs Research-feasibility split) · §8 buy-vs-build verdict
(M; single location; structured cheapest-source row) · §9 evidence (M): verdict-first box,
Before/after-cost column, fixed-label honest-bottom-line last paragraph; chatbot rows only in
Unverified-leads · §10 failure modes (M; ranked table + check: lines + Regime-gate table) ·
§11 figures (M; synthetic-data caption every figure) · §12 sources (M; verified only; process
logs → appendix).
**STRATEGIES (T0–T10):** §0–§1.5 as signals (M; T1 adds Capacity row) · §2 Full mechanics (M;
mandatory labeled sub-blocks in fixed order: Universe · Entry · Exits · Sizing (fenced sizing
function) · Risk limits (RISK CONTRACT YAML: per_trade_R, daily_loss_stop, max_gross,
max_adverse_per_trade, kill_conditions[], enforcement intraday-hard|review-only) · Costs
(single COST block: callable expected_cost_bps(notional, adv_pct, venue, side, urgency),
4-component stack, fee_schedule_as_of/venue/tier/source, side taker|maker|mixed,
borrow_bps_per_day — 0 needs reason, cost level L0–L3) · Execution (OrderTicket fields:
order_type, TIF, venue/router, fallback; child-order state machine; partial-fill policy) ·
Robustness (incl. Compliance sub-block; Margin & self-liquidation for leveraged) · Parameter
table (S3-style) · Fill-model table) · §3 combination logic (M; normative pseudocode, helpers
defined first, cost-gate predicate, causality assert, signal-row columns
units/cadence/annualization/staleness/R-ids) · §4 worked example (M; Repro header;
cost-function calls inputs→bps→$; known-optimistic checklist in bps; one case where the
mechanism backfires) · §5 infra & safe-mode (M; kill state machine + re-arm checklist;
halt/auction/closed state table; alert table; venue-definition snapshot for crypto) ·
§6 build-or-buy & venue economics (M; venue rows carry taker/maker fee) · §7 evidence (M;
acceptance checklist walk-forward+embargo/min-OOS/cost-level; scope banner on meta chapters) ·
§8 failure modes (M) · §9 figures (M) · §10 sources (M).
**REGIMES (R):** RB-list format retained; R chapters add §R0 front-matter + reviewer card lite
+ mandatory Lag contract (indicator_ts, decision_ts, min_bar_offset, vintage_field, compatible
frequencies) + fifth "Cost interface" block (regime state → cost-function adjustment).

## 4. Migration (decisions)
**Template:** `notes/module-template.md` v1.0.0 succeeds `notes/chapter-template.md` (archived,
not deleted); single template with S/T/R conditional blocks; chapters record
`template_version` in §0. **Versioning:** chapter `version: x.y.z` + one-line changelog in
§0; consumes pinned (`S001@1.2.3` or spec-hash); frozen MASTER commit hash in dependencies
manifest. **CI (merge-protocol QC additions):** front-matter lint (required fields + enums) ·
S5↔T3 symmetry vs edge list · example-tag lint (every numeric literal tagged; unlabeled cost
numbers fail) · cost-block single-source (one COST block; numbers appear once, T4/T6/T7/T8
reference by name; T2/T4 arithmetic cross-check) · §T2 mandatory sub-block presence ·
§S1/T1 canonical row schema · "Failure modes" title normalization · secrets grep (no
hardcoded API-key literals; env-only) · cross-ref link lint (S###/T###/R### must be links) ·
Repro-block + seed-convention check · version-pin lint on consumes[].
**Retrofit priority at merge time:** §0 front-matter + schema block + F1–F5 fail-safes first;
pinned formula excerpts and Regime-gate tables land with the R001–R050 annotation pass.
