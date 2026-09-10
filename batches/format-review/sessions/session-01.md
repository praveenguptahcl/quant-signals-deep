# Session 01 — Module/API/data contracts + machine-readable metadata
Date: 2026-09-10 · Facilitator: K (subagent) · Voices: R14, R13 (agent-architects), R07 (quant-dev), R11 (portfolio), R16 (MLOps), R09 (data-eng)

## D1 — YAML front-matter: one schema, required fields (convergence of R14#1, R07#5, R09#5/#15, R11#8, R13#8)
Every chapter file carries:
```yaml
---
id: S003                # machine key; Stage N = S0NN / Stage 100+M = T0MM kept
kind: signal            # signal | strategy | regime
version: 1.2.0          # semver; contract version, NOT evidence tier
status: verified        # draft | verified | deprecated
batch: SB1              # family: Family A  (signals only; strategies omit family)
provenance_tier: [D]    # legend once in compendium header, never redefined in-chapter
sources: [...]          # peer-reviewed / measured evidence IDs
unverified_sources: []  # chatbot-sourced rows; must exist even if empty
regime_ids: []          # R001–R050, provisional; wired now, annotation starts before R-chapters land
correlates_with: []     # crowding-proxy IDs (R11#8)
shares_feed_with: []    # shared-input feed IDs (R11#8)
seed: 42
rng: "numpy.random.default_rng / numpy 2.x"   # algorithm + lib pin (R07#7)
plot_script: "batches/SB1/plot_S003.py"       # repo-relative from documented root (R09#14)
test_cmd: "pytest tests/test_S003.py"         # one acceptance command (R07#3)
datasets:                       # lineage fingerprints (R09#5)
  - {vendor: "Databento", product: "MBP-1", schema_version: "…", adjustments: "…", vintage: "…"}
changelog: "1.2.0 — pinned S008@v2.1 contract"   # one-liner per version bump
---
```
Rules: provenance tier ≠ version (R07#5). Numeric-literal convention fixed compendium-wide: backticked `example` / `fixed` on every literal, plus `rule` for non-example exact rules (R13#2, R09#10); lint-enforced, no square-bracket variant.

## D2 — Module interface contract: strict on the block, light on internals (R07#1/#4/#9, R16#6/#9, R14#3, R09#3, R13#11)
New mandatory section "S0/T0 Module contract" in all 250 chapters:
- Typed signature: `signal(state, events: EventBar[], cfg: Config) -> SignalVector` — core function, not ingest code; covers empty book, zero denominator, stale input (R07#9).
- `Config` dataclass in one block: every parameter with type, default, allowed range, status ∈ {calibrated-OOS, literature, placeholder} (R07#6, R07#12).
- Canonical input schema: chapter maps its fields to the single compendium-wide Event/Bar schema; timestamp block mandatory — authoritative clock, units, zone, which ts drives causality, bar open-vs-close label (R09#1/#2/#6).
- State semantics: pure by default; any carried state is an explicit `state` object passed in (idempotent: same inputs ⇒ same outputs, byte-identical from (seed, inputs) — R07#7).
- Error/UNKNOWN taxonomy (shared, compendium-level): module-state enum `OK | DEGRADED | UNKNOWN | OFF` (R16#9). Invalid/missing/stale input ⇒ emit UNKNOWN — never interpolate, never silently carry forward (R09#3: RB-list F1–F5 ported as "Data fail-safes" with explicit state transitions; extends existing "flatten on feed outage" discipline — R16 good-to-keep).
- Self-check: `tests/test_<SID>.py` with fixture (`fixtures/<SID>_tape.csv` + expected outputs); the §S4/§T4 worked example IS the fixture, machine-asserted (R14#4/#8, R13#11).
- Ops tail in same section (R16#1/#4/#8/#10): cadence, schedule spec (trigger, timezone, calendar owner), health checks, alert table (metric/threshold/severity/destination), resource budget per symbol-day, runbook rows (trigger → action → verify → escalate); no hardcoded secrets — env-only, Gate-grepped (R16#2).

## D3 — Canonical signal output vector (R11#1, R16#3/#16)
```python
SignalVector = {
  "module_id": "S003", "estimator_version": "1.2.0",   # which contract produced this
  "symbol": "AAPL", "timestamp": "2026-09-10T13:30:00-05:00",  # per §D2 timestamp contract
  "direction": 1,            # ∈ {-1, 0, +1}
  "score": 0.62,             # ∈ [-1, 1]; documented normalization
  "confidence": 0.71,        # ∈ [0, 1]
  "capital_scale": 0.5,       # ≥ 0 sizing multiplier
  "state": "OK",             # OK | DEGRADED | UNKNOWN | OFF
  "regime_id": "R007", "regime_state": "…",   # RSV fields consumed (R11#7)
  "data_vintage": "…", "computed_at": "…",    # freshness + lineage (R16#16)
}
```
All 200 existing heterogeneous emissions (z-score, probability, ±1 side, Ψ) map into this in the new S0/T0 subsection; canonical mermaid edge label `signal_vector[t]` (R11#11). No module invents its own output shape.

## D4 — Dependency manifest + versioning: edge list is the single source (R07#2/#14, R11#2/#6, R14#2/#7)
- One machine edge list (repo-level `deps.yaml`): `{from, to, function, arg_types, return_types, version_pin, role}`. Consumers pin the provider's CONTRACT version (semver), not the evidence tier.
- S5 (signals) / T3 (strategies) tables are GENERATED from the edge list, never hand-written; CI asserts S5↔T3 symmetry and that the chapter's table ID set == edge-list ID set (kills R11's 82/18 header split and 23 asymmetric links).
- Formula single-sourcing resolved (R14#7 vs R16#12): formulas live once in the provider's contract block; consumers cite them and inline ONLY the 2–3 decisive constants verbatim with version pin (R14#9). Cross-refs always carry a one-line recap (R13#4).
- S-chapters get the same dependency header T-chapters have (R07#14); S→S edges included.

## D5 — Cheapest build: what the contract layer minimally costs
Minimum viable = YAML block + `deps.yaml` + S0/T0 interface block + one fixture+test per chapter + Gate QC lint (tag audit, header symmetry, secrets grep, fixture presence). Per R09's "cheapest high-leverage" read: the schema-block + fail-safes retrofit applied AT MERGE TIME via the existing 22-item Gate QC — no separate migration project. Rough bound: ~one new section + one YAML block + one fixture per chapter; the one-time cost is the template + CI checks, the per-chapter cost is bounded and mechanical. Everything else (capacity/impact models R11#3, portfolio-assembly capstone R11#5, cloud cost annex R16#5) is session-02+ scope and must not inflate this layer.

## Open items for later sessions
- R-chapters (Part III): RSV stamp schema finalization; provisional `regime_ids[]` placeholders now, full wiring when R001–R050 land (Stages 201–250, gated on 200/200).
- Section-label collision "S3 vs S003" (R16#14): rename chapter-section refs to `§S003.3` style.
- One-line `rule` vs `fixed` boundary definition; global unverified-leads index (R07#18).
