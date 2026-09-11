# R5 — Grok independent verification (2026-09-11)

Source: signed-in Grok chat (plain Fast chat, new thread), prompt sent verbatim
as first message, full reply captured verbatim via browser task. Grok read
`plans/amd-paper-trading/PLAN-v1.0.md` and all four review reports via its
GitHub connector (18 sources cited). The prompt asked for: verdict
(APPROVE / APPROVE-WITH-FIXES / REJECT), numbered findings with severity
(no repeats of the 63), and "what's sound".

Verbatim reply follows.

---

APPROVE-WITH-FIXES

The 63 reconciled items are real work. The pipeline shape, trial ledger, holdout, paper-only interlock, and ExecutionEngine routing are good enough to run an AMD paper book. What is still wrong is mostly reconciliation residue (the plan absorbed R1 and R2 without making them consistent) plus a few load-bearing holes the four reviews never named.

1. HIGH — Stage 1 still assumes strategies consume signals. Architecture §2 says they do not.

§2 (R2-H1): strategies are self-contained parallel intention sources; no handoff. §3 Stage 1 still says strategies are "scored against the full post-Stage-0 signal universe" and "RE-SCORED on the pruned signal set," and P3 still caps "per-signal look-through attribution ≤ 40%."

Those sentences describe a graph that does not exist. If you run Stage 1 as written, strategy DSR is fiction. If you run architecture as written, P3 and the re-score step are unenforceable.

Fix: Pick one and freeze it in one paragraph. Recommended: treat S and T as two parallel intention families; Stage 1 scores each module on its own on_bar output only; Stage 2 clusters on daily P&L of those outputs; drop look-through P3 or replace it with a cap on intention-family concentration (e.g. no single module_id > 25%, already P3-strategy). Delete every "pruned signal set" sentence. Do not ship both.

This is a disagreement with the v1.0 reconciliation: R1-M1 and R2-H1 were both "fixed" and they contradict.

2. HIGH — Opening-auction execution policy is not what a standard Alpaca paper account can do.

Policy: rest until t+1 open, then "limit-at-open (market-on-open where supported)." Alpaca documents opg/cls TIF for equities, and separately states that opg/cls are only available to Elite Smart Router users. OPG submitted after 09:28 ET is rejected. Paper 24/5 also accepts overnight DAY/GTC limits the plan's NYSE calendar does not model.

Gate 5 can pass on DAY market orders at 10:00 and the first real rest-until-open bar still rejects.

Fix: Pin the phase-1 order: limit + day (or gtc) submitted in a defined pre-open window, or confirm Elite Smart Router on the paper account and test opg in a market-hours drill before Gate 5. Add a calendar rule: no submit 09:28–09:35 ET if using OPG; reject extended-hours bars unless an extended-hours policy is written. Do not write "MOO where supported" as if Alpaca paper supports it by default.

3. HIGH — Single-name earnings gaps walk through the drawdown breaker.

P6: halt entries at −10% from WAL peak, flatten-and-review at −20%. AMD gaps double-digit on prints. A book at −8% that gaps to −22% never hits the −10% entry halt; flatten is after the damage. No earnings/ex-div blackout exists. Vol scaling increases gross when realized vol is below its trailing median — i.e. into the quiet week before the print.

Reviewers added a breaker. They did not add an event calendar.

Fix: Hard book-level veto: no new entries from T−2 through T+1 around AMD earnings (and known extra-div dates). Size the flatten trigger on open-to-open equity as well as marked peak. Optionally cap vol-scaler upside (e.g. size multiplier ≤ 1.25×) so a vol crush cannot lever the next event.

4. MED — DSR is honest for AMD selection. It is not a license to reuse SURVIVORS.json on ARM/INTC/SNPS/AAPL.

N = ledger rows, stratified, one frozen evaluation on 2024–2025 — that is the correct Bailey–López de Prado use of DSR/PSR for this name. Transferring the AMD survivor list to four other names is a new uncorrected selection (same modules, new series, no new N). Four of five names share a semiconductor factor; AAPL does not, SNPS is EDA. Pairwise equity correlation in that complex is high enough that five "60% net / 75% gross" books are one sector bet.

This is not a phase-1 block. It is a phase-3 block if left implicit.

Fix (phase 3, write it now so nobody "just adds tickers"): (a) re-run Stages 0–3 per name or a joint panel with N counting every name×config; (b) a book-level sector net cap (e.g. |sum of semi-name nets| ≤ 60% of firm equity, not per-name); (c) prune on cross-sectional residual correlation, not only same-name P&L ρ; (d) new SURVIVORS.json (or a multi-name registry) — AMD hashes do not travel; (e) rename client_order_id / tenant away from amd-paper/. Frozen decision 2 already says AMD-only until the loop is validated; put the above in the same freeze list so phase 3 cannot ignore it.

5. MED — After netting, client_order_id = amd-paper/{bar_ts}/{module_id}/{side}/{seq} is ill-defined.

Netting (R2-M1) collapses many modules into one venue order. The id still keys on module_id. Crash recovery then cannot reconcile one broker order to many intentions, or it invents a dummy module_id and loses attribution.

Fix: Two ids: intention-id (per module, WAL only) and client_order_id at netted grain: amd-paper/{bar_ts}/{venue}/{side}/{net_seq}. Map many-to-one in the WAL. Test restart between net and ack.

6. MED — Holdout PSR on one name, two years, one regime is weak power, not a leak.

2024–2025 AMD is a single-asset AI-chip path. ~500 daily points, one ticker, no multiplicity left if they truly evaluate once. PSR can easily fail to reject a lucky survivor. That does not invalidate the split; it means "validation PSR is the only number near the paper loop" must not be read as "we proved edge."

Fix: Pre-register the decision rule: paper loop starts if validation PSR > X or if PSR is inconclusive the loop still starts but with conviction floor raised and size halved. State that paper P&L is plumbing. Do not treat a noisy holdout pass as license to expand the universe.

7. LOW — "Automated day trading" in the expansion note is not what v1.0 builds.

The loop is daily-close rebalance plus optional 5-min entry gates, no mid-day resize, shorts vetoed, rest-until-next-open. That is a daily swing book. Calling the five-name phase "automated day trading" will drag in PDT, auction, and 24/5 assumptions the risk block does not cover.

Fix: Strike "day trading" from the expansion sentence. If someone later wants true intraday, that is a new plan (cadence, PDT, locate, SIP).

8. LOW — IEX history vs IEX live adjustment basis still needs a dated pin, not a slogan.

R4-4 is reconciled as "stamp REAL-IEX, assert adjustment basis." Assert against what file, as-of what date, including cash dividends? AMD's last split is 2000, so the holdout is dividend/adjustment noise, not a split. A silent raw-vs-adjusted mismatch still wrecks Stage 1 vs live.

Fix: Checksum the exact historical extract used for Stages 0–3 and the live adjuster against the same corporate-action calendar. Fail ingest on mismatch. Already implied; make it a Gate 2 abort, not a log line.

What's sound
• Pre-registration + append-only trial ledger + stratified DSR + one frozen 2024–2025 evaluation is the right defense against 250-module snooping. N is no longer "250."
• Causality doctrine (bars through t, rest to t+1 open, REAL/PAPER stamps, PAPER_VENUES_ONLY, no parallel order path) matches how you stop a research stack from becoming an accidental live router.
• Portfolio block P1–P10 plus fail-closed allocator assertions and shared KillSwitch is the correct layer once module YAML cannot see net exposure.
• Phase-1 Alpaca-only, shorts vetoed, IBKR deferred, is the only timeline that does not lie about gateway risk.
• Frozen "no hand-overrides / ≤2 re-admissions per quarter on new data or cumulative N" is the actual iteration stopper. Keep it.

Phase 1 AMD paper: go, after findings 1–3 and 5 are written into the freeze list. Do not treat v1.0 as a 5-ticker plan.

[18 sources]

---

## Reconciliation (K, 2026-09-11)

All 8 findings accepted as genuine and written into v1.1:

- Finding 1: genuine — and matches the inconsistency I had already flagged
  before Grok ran. Struck the "pruned signal set" sentences; S/T scored
  standalone; look-through P3 replaced with no-single-module_id > 25%.
- Finding 2: verified against Alpaca's own order docs (2026-09-11):
  "opg and cls orders are only available to Elite Smart Router users."
  Phase-1 order pinned to limit+day, 08:00–09:28 ET window.
- Finding 3: genuine — P6b earnings blackout T−2→T+1, open-to-open equity
  flatten trigger, vol-scaler upside capped 1.25×.
- Finding 4: genuine — frozen decision 11, phase-3 amendment requirements.
- Finding 5: genuine — two-level ids (intention_id WAL-only,
  client_order_id at netted grain), Gate 4 restart-between-net-and-ack.
- Finding 6: genuine — pre-registered validation decision rule
  (PSR > 0.5, else raised conviction floor + halved size).
- Finding 7: accepted as a labeling correction — §9 "cadence honesty" note.
  The user's five-ticker day-trading goal stands; true intraday is a later
  phase with its own plan.
- Finding 8: genuine — checksum extract vs live adjuster against the same
  dated corporate-action calendar; ingest failure = Gate 2 abort.

v1.0 preserved untouched as `PLAN-v1.0.md`; v1.1 is the operative plan.
Iteration stops here: build starts.
