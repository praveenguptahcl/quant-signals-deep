# Reviewer 16 — Cloud / MLOps engineer (read S003, T001 full; skimmed T003, T095; RB-list.md; notes/cost-model.md; notes/merge-protocol.md; corpus greps)

## CRITICAL (a)

1. No per-chapter OPS block anywhere. 0 hits for runbook/health check/prometheus/docker/k8s. T001 §T5 has pipeline inventory + kill-switch thresholds (heartbeat > 2 s, clock skew > 50 ms) but no deployment contract. Fix: mandatory S0/T0 OPS block — cadence, runtime, schedule spec, health checks, alert routing, runbook stub, resource budget.
2. Credentials hardcoded in flagship chapter. S001 §S6: cli = db.Historical("API_KEY") — literal placeholder an agent will copy-paste. 0 mentions of env vars/dotenv/vault/secrets in MASTER.md. Fix: secrets convention in merge-protocol QC — env only (os.environ["DATABENTO_API_KEY"]); gate merges on grep rejecting hardcoded "API_KEY"-style strings.
3. RB-list Sentinel/Verifier/Gate fail-safe machinery wired into zero chapters. UNKNOWN/Sentinel/Verifier 0× in MASTER.md; 22-item Gate QC never surfaced in chapters. Fix: fold F1–F5 into every chapter's safe-mode section (or shared §0 imported by reference) incl. RSV provenance stamp {regime_id, state, value, estimator_version, data_vintage, computed_at}.
4. Kill-switch thresholds exist; monitoring/alerting does not. "alert" (19 hits) all trading alerts or estimates, never ops. Fix: per-chapter alert table — metric, threshold, severity, destination, expected response.
5. No per-module cost-of-compute budget. notes/cost-model.md is local-Mac model only ("Marginal compute cost ≈ $0"); every chapter cites it for RAM/storage only. Fix: per-chapter resource-budget row (CPU/RAM/disk per symbol-day at stated cadence) + cloud-deployment cost annex.

## MAJOR

6. Module boundaries are prose, not contracts. T001 §T3 ≤25-line pseudocode with no signature/schema/error contract/idempotency; S003 §S6 polars sketch with no named module interface. Fix: per-chapter interface block — function signature, I/O schema, error/UNKNOWN contract, idempotency note.
7. S-series chapters have zero operational content. No schedule/health/alerting/resource sections at all. Fix: S0 OPS block (evaluation cadence, staleness/timeout semantics, resource budget) mirroring T5.
8. Schedule exists only as prose, owned by nobody. Session windows in narrative; "cron job could run this" never becomes scheduler spec; no scheduler, clock source, or holiday-calendar owner. Fix: per-chapter schedule block — trigger spec (cron/interval), timezone, calendar source, owner.
9. Health-state taxonomy inconsistent: T001/T002 DEGRADED, T003 UNTRUSTED_FLAT, RB-list UNKNOWN. Fix: standardize module-state enum (OK / DEGRADED / UNKNOWN / OFF).
10. Failure modes are design caveats, not runbooks. "Mitigation: stand down on a spread-multiple trip" — what command, what verification, what rollback? Fix: runbook rows — trigger signal → action steps → verification → escalation.
11. Ops-critical thresholds scattered across three sections (T001 heartbeat rule in T2 and T5; VPIN staleness only in T003 T2). Fix: consolidate degrade/fail behavior into single OPS section; T2/T8 reference it.
12. T-chapters restate signal formulas instead of referencing them. T001 §T2 re-derives S001 OFI sum, S003 imbalance, S004 microprice deviation. Fix: cite signal contracts (S003 §S3) without restating; single-source formulas.

## MINOR

13. example-tagged thresholds are unactionable defaults. Fix: split config table — required (defaults shipped) vs recalibrate (example starting points).
14. Section IDs collide with chapter IDs ("S3" vs "S003"). Fix: rename section labels (e.g. §A1…A12) or prefix chapter refs consistently.
15. Deploy constraints are inline prose ("simulated only — requires MBO/ITCH"), not a box. Fix: "Deploy constraints" box at top of infra section.
16. Estimator versioning not specified at module level. Fix: every module output carries estimator_version, data_vintage, computed_at.

## What's already good (don't break)
Feed-outage safe mode in every T-chapter ("flatten immediately, never interpolate"); crash discipline uniform ("on-disk ledger is source of truth, never RAM"); kill-switch numeric thresholds; 22-item Gate QC + quarantine-never-silent-drop policy — add ops/secrets/deployment items to it.
