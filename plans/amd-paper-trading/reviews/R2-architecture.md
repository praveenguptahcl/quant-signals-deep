# R2 — Systems Architecture Review: AMD Paper-Trading Plan v0.1

Reviewer role: systems architecture (red-team). Scope: the orchestrator,
signal→strategy→allocator→risk→execution data flow, the bar-close-driven
loop, failure modes, and integration points with the existing Meridian
codebase at `~/workspace/meridian`. Read-only review; no code or PLAN.md
modified.

References checked: `PLAN.md` §§1–10; `meridian/ARCHITECTURE.md` (§§1–8b,
19 invariants); `meridian/meridian/{research,execution,broker,app}.py`
(Signal contract, ExecutionEngine, PaperBroker, `paper` CLI);
`plugins/modules/_tools/{plugin_base,loader}.py`;
`plugins/modules/S001/S001_plugin.py`, `T001/T001_plugin.py`,
`R001/R001_plugin.py`.

## Headline

The plan's core data-flow diagram describes a system the built plug-ins do
not implement, and its "Execution layer (NEW)" routes around the execution
stack that 10 red-team iterations hardened. Those two are the high-severity
items; everything else is failure-mode and integration detail the plan
leaves unspecified.

---

## HIGH severity

### H1. The "signals → strategies consume signals" data flow does not match the built plug-ins
- **Flaw:** PLAN §3 shows "Strategy layer: 100 strategy plug-ins consume
  signals → candidate orders." The actual strategy plug-ins are
  self-contained: `T001Plugin.on_bar(bars, tenant_id, regime_state)` takes
  no signal inputs — it recomputes its own features (OFI proxy, imbalance)
  and emits a `Signal` intention directly, exactly like the signal
  plug-ins do. There is no signal-consumption contract anywhere in the
  plug-in set. An orchestrator built to the plan's diagram would look for
  a handoff that does not exist.
- **Fix:** Redefine the orchestrator contract honestly: signals and
  strategies are two parallel intention sources, both emitting
  `meridian.research.Signal`. Either (a) keep it that way and let the
  allocator treat all ~200 intention streams uniformly, or (b) define an
  explicit signal-consumption adapter interface for strategies — but do
  not ship the plan's diagram as drawn.

### H2. The new execution layer bypasses Meridian's hardened execution stack
- **Flaw:** PLAN §3/§6 propose an "Execution layer (NEW)": fresh IBKR/Alpaca
  connectors plus an order router. Meridian already owns this problem:
  `ExecutionEngine` (WAL INTENT → submit exactly-once, reconciliation by
  idempotency key, kill switch checked *inside* the submit path per inv. 3,
  `RiskEnvelope`, `FailoverBroker` that never retries explicit refusals per
  inv. 5, crash recovery that reconciles instead of resubmitting per
  inv. 4). A parallel order path silently discards all of it, including
  the exact-once and kill-switch guarantees the validation gates assume.
- **Fix:** No parallel path. Implement Alpaca/IBKR connectors behind the
  existing broker interface (extend/replace `LiveBrokerAdapter`, which
  currently raises by design) and route every order through
  `ExecutionEngine` with its WAL, kill switch, and refusal accounting.
  The "order router" becomes venue selection *inside* the engine's submit
  path, not a separate layer.

### H3. t→t+1 causality is unenforceable against live paper venues as specified
- **Flaw:** The backtester enforces "no fill before bar t+1's open"
  structurally (the event loop, not the signal — `Signal.decided_at` is
  explicitly advisory-only). Against a real paper broker, a market order
  submitted at bar-t close fills at approximately bar-t's close. Restating
  the invariant in PLAN §3/§10 does not make it true on a live venue.
- **Fix:** Define the execution policy explicitly, e.g.: intentions decided
  on bar t rest until bar t+1's open, then submit as limit-at-open (or
  market-on-open where the venue supports it) with the slippage model
  applied; fills timestamped and stamped PAPER. Extend validation gate 3's
  automated t→t+1 audit to the *live* loop (check fill timestamps vs. bar
  boundaries), not just the historical replay.

### H4. Real network connectors break v1's "no code path reaches a venue" safety story
- **Flaw:** Meridian v1's central safety claim is that live trading cannot
  happen by accident (`LIVE_ENABLED=False`, `LiveBrokerAdapter` raises on
  every method, §8 roadmap defers live behind a gate that does not exist).
  Adding real HTTPS connectors with real credentials — even to paper
  endpoints — punches a hole in that story with no replacement boundary.
  Paper credentials on a compromised box are still credentials.
- **Fix:** Define the new boundary in the plan: a `PAPER_VENUES_ONLY`
  guard that allowlists paper base URLs (e.g.
  `https://paper-api.alpaca.markets`, the IBKR paper gateway) and refuses
  anything else at connector construction; credentials via Secure Vault,
  scoped paper-only; document the revised threat model (what a leaked
  paper credential can and cannot do).

### H5. No per-plug-in fault isolation in the bar loop
- **Flaw:** The loop will call 100+ stateful plug-ins per bar. The plan
  never says what happens when one throws (or hangs) mid-bar. One bad
  plug-in currently kills the whole session's trading. `Backtester` has an
  *opt-in* `strategy_timeout_s` (default off — the settrace deadline costs
  ~6×); the live loop needs liveness by default.
- **Fix:** Per-plug-in try/except with quarantine: exception → plug-in
  excluded for the bar, ledgered; N consecutive failures (e.g. 3) →
  quarantined for the session with an alert. Per-plug-in wall-clock budget
  per bar (armed by default, sized from measured p99); timeout →
  treated as a failure, never as a silent skip.

### H6. Plug-in state is RAM-only; crash recovery is undefined
- **Flaw:** Plug-ins carry mutable state (`_ofi_hist`, `position`,
  `cooldown_until_idx`, regime hysteresis in `R001._state`). A process
  restart wipes it: strategies re-enter immediately, cooldowns reset,
  regime states snap to defaults. Meridian already documents this shape
  as a residual (M10: serve-time council/BarStore state is RAM-only).
  The plan's kill-switch drill (gate 4) does not cover restart recovery.
- **Fix:** Checkpoint plug-in state per bar into the state dir (serialize
  each plug-in's `__dict__`, versioned), or deterministically rebuild by
  replaying bars from a known-good snapshot on restart. Define which one;
  add "restart mid-session, verify state continuity" to validation gate 4.

### H7. Module-level `notional` vs. allocator % allocations — who wins is undefined
- **Flaw:** Every `Signal` carries `notional` (plug-ins use fixed
  `[example]` values: $10k in S001, $25k in T001). The allocator (§5)
  computes percentage-of-equity allocations per strategy. When the two
  disagree — and they will, on every bar — nothing in the plan says which
  governs the order sent to the venue.
- **Fix:** Pin the rule: the allocator's allocation overrides module
  notional (module notional treated as a sizing hint, ignored at order
  construction), and the risk layer enforces
  `sum(order notionals) ≤ allocator budget` as a hard check. Or the
  inverse — but it must be stated and enforced, not emergent.

---

## MEDIUM severity

### M1. No order netting across strategies
- **Flaw:** ~200 intention streams per bar with no netting step means up to
  ~200 orders per bar: IBKR paper rate limits (which the plan itself flags
  as strict), fee multiplication, and partial-fill reconciliation
  complexity. Worse, §6's "explicit per-strategy venue mapping" actively
  conflicts with netting — you cannot both net to one portfolio order and
  keep per-strategy venue assignment.
- **Fix:** Add a netting stage between allocator and execution: net
  intentions to portfolio-level orders per venue per bar (net within
  venue; define the rule for the single-venue-per-bar vs. split case).
  Resolve the venue-mapping tension explicitly: either venue is a
  portfolio-level decision per bar, or per-strategy mapping survives and
  netting happens within (strategy, venue) buckets.

### M2. Regime→strategy binding is missing
- **Flaw:** 50 regime modules each emit a state string via
  `classify(bars)` (e.g. R001 returns hysteresis-smoothed bucket labels,
  plus a `"warming"` state during warmup). Strategy `on_bar` accepts a
  single `regime_state: str | None`. The plan's "50 regime modules →
  current regime state → gates" never defines how 50 outputs collapse
  into per-strategy gate inputs.
- **Fix:** The survivor registry must include a regime-binding table:
  per strategy, (regime module id, allowed states, gate behavior).
  The orchestrator evaluates bindings per bar; unbound strategies run
  ungated (stated explicitly), and non-terminal regime states
  (`"warming"`, unknown labels) gate closed.

### M3. SURVIVORS.md is not machine-readable and pins nothing
- **Flaw:** §4 freezes survivors in a markdown file. The allocator needs
  machine-readable inputs (DSR, cluster id, regime gates), and selection
  results are only valid for the exact plug-in code tested — plug-in
  versions on disk (`S001 v1.1.0`, `T001 v1.0.2`) can change underneath
  the frozen list.
- **Fix:** `SURVIVORS.json` (or YAML): per module
  `(module_id, version, sha256_of_plugin_file, dsr, cluster_id,
  regime_binding)`. The orchestrator refuses to load a plug-in whose hash
  differs from the registry. Keep the .md as the human-readable render.

### M4. Data-feed gap handling is unspecified
- **Flaw:** Bar-close-driven loop assumes bars arrive. A missing or delayed
  bar (holiday calendar bug, feed outage) leaves the loop with nothing to
  close on — and intentions decided on bar t−1 must not execute late
  against bar t+1's prices.
- **Fix:** Gap detector (expected bar schedule vs. received; wall-clock
  staleness alarm). Invariant-11 fail-closed: no bar → no signals → no
  orders. Intention TTL of exactly one bar: an intention not acted on by
  its target bar is discarded, ledgered, never carried forward.

### M5. Cross-venue netting policy is missing
- **Flaw:** Two paper venues with per-strategy venue mapping can produce
  offsetting legs: long AMD on Alpaca, short AMD on IBKR. Portfolio gross
  exposure and the §5 caps (gross ≤ 100%, single-strategy ≤ 25%) are
  ambiguous when the book is split across venues.
- **Fix:** State whether cross-venue legs net at the portfolio level or
  each venue is margined as a separate book; make the allocator's
  exposure math and the reconciliation loop (which compares
  broker-reported vs. internal positions) venue-aware accordingly.

### M6. Idempotency key scheme is missing
- **Flaw:** `ExecutionEngine`'s crash recovery reconciles by
  `client_order_id` instead of resubmitting (inv. 4). The orchestrator
  must therefore mint deterministic client order IDs; the plan never
  defines the scheme, so a crash between venue-accept and response-receipt
  risks either double-submit or a stuck intention.
- **Fix:** Specify `client_order_id = f"amd-paper/{bar_ts}/{module_id}/{side}/{seq}"`
  (or equivalent), persisted in the WAL intent record, so recovery is
  reconcile-by-key.

### M7. Short-locate plumbing is absent
- **Flaw:** Module compliance blocks (C7) forbid SHORT without
  consumer-asserted `locate_ok` (e.g. S003's review promoted
  `state.locate_ok`, default False). If any shorting strategy survives
  selection, the live loop must supply locate attestation per bar; the
  plan never mentions it.
- **Fix:** Either the orchestrator provides an explicit (paper-labeled)
  locate attestation feed per bar, or the risk layer hard-vetoes all
  short sides. Decide before selection, since it changes which modules
  can survive.

### M8. Bar-type impedance mismatch at the orchestrator boundary
- **Flaw:** Plug-ins speak their own `Bar` dataclass (`plugin_base.Bar`
  with `provenance: "REAL" | "SYNTHETIC"`); Meridian core speaks
  `meridian.data.Bar` / `BarStore`. Neither the selection harness nor the
  live feed has a defined conversion point, and plug-ins ship with
  CSV loaders pointed at sample files (`_data/amd_daily_real.csv`,
  `_data/amd_intraday_synthetic.csv`) that must never be used in
  production.
- **Fix:** Define the canonical bar type at the orchestrator boundary and
  a validated converter (types, finiteness per inv. 11, provenance
  stamping REAL for the live feed with rejection of SYNTHETIC bars).
  Production code paths must not import the plug-ins' CSV loaders —
  enforce with an import check in CI.

### M9. Reconciliation "halt and alert" should trip the existing KillSwitch
- **Flaw:** §6 defines a separate halt on broker-vs-book mismatch. A
  second halt flag alongside the KillSwitch is exactly the kind of
  parallel safety machinery inv. 3's defense-in-depth was built to avoid;
  two flags can disagree about whether trading is stopped.
- **Fix:** Reconciliation mismatch calls `ExecutionEngine.trip_and_cancel`
  on the shared KillSwitch (one flag, already checked inside the submit
  path). "Alert" stays as specified.

### M10. Backtest/live fill-policy parity gap
- **Flaw:** Selection (Stage 1) scores modules on `PaperBroker` fills
  against historical bars; the live loop gets real paper-venue fills with
  different slippage/queue behavior. A module selected on simulated fills
  can look materially different on venue fills, and no validation gate
  measures the divergence.
- **Fix:** Add a calibration gate: run the survivor portfolio against
  both simulated fills and the paper venue over a calibration window;
  record the fill-statistic divergence (mean/std of slippage vs. model)
  and set an alert threshold for live drift.

---

## LOW severity

### L1. Corporate actions
- **Flaw:** Inv. 16 discloses corporate actions are not modeled. A
  multi-year AMD backtest on unadjusted data, or a split during the live
  phase, silently corrupts both selection and sizing.
- **Fix:** Require split/dividend-adjusted feed bars; assert against a
  corporate-action calendar at ingest; ledger the adjustment basis.

### L2. Loop cadence is underspecified
- **Flaw:** "Bar-close-driven" needs a schedule: daily-close loop,
  5-minute intraday loop, or both? Weekends/holidays produce no bars.
- **Fix:** State the cadence (e.g. daily loop after close + optional
  5-min intraday entry gating per §5), the market calendar source, and
  that no-bar means no-action (not an error).

### L3. Single-tenant operation should be stated
- **Flaw:** Meridian v1 is single-tenant per process (`TENANT_DEFAULT`);
  dashboard reads are not tenant-filtered. The plan never names the
  tenant the AMD loop runs as.
- **Fix:** Run the loop as one explicit tenant id (e.g. `amd-paper`);
  note the v1 tenancy limits in the plan so nobody reads multi-tenant
  isolation into it.

### L4. Whose confidence feeds the allocator
- **Flaw:** §5 weights by "confidence × DSR_rank_weight" but §3 has
  strategies emitting the intentions — is the allocator using
  strategy-level confidence, the underlying signal confidences, or both?
- **Fix:** One sentence: allocator consumes the *strategy-emitted*
  `Signal.confidence` (the only confidence on the intention the
  allocator sees).

### L5. Per-bar intention cap
- **Flaw:** `Backtester.run` has `max_signals_per_bar`; the live loop has
  no equivalent backstop against an intention flood.
- **Fix:** Cap intentions accepted per bar (e.g. 2× survivor count);
  excess → ledgered refusal, alert.

---

## What's sound (not findings)

- The selection pipeline's stage order (applicability → walk-forward →
  redundancy → regime conditioning → frozen survivors) is the right
  shape, and mandatory DSR over 250 candidates is correctly identified
  as the #1 methodological defense.
- The frozen rules (§10) are the right iteration-stopper, particularly
  "no hand-overrides" on survivors.
- Validation gates 1–5 are well chosen; H6/M4/M10 propose additions,
  not replacements.
- Paper-only, single-ticker, no-leverage scoping is the correct
  blast-radius discipline for phase 1.
