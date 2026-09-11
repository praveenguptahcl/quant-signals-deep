# Deep-review pass 2 (REVIEW2) — status

Coordinator: deep-review subagent. Started 2026-09-10 (UTC 2026-09-11).
Rule: one worker per module ID; workers touch ONLY their own .md + fixtures + tests.
Commits: every ~25 modules done, `git status` + fetch first, stage ONLY modules/ files.

## Completed waves

| Wave | Modules | Commit | Result |
|---|---|---|---|
| REVIEW2 wave 1 (signals) | S001–S100 | `4d281e6` | All 100 signal modules deep-reviewed; fixtures regenerated; 7–18 gaps fixed per module (real bugs: wrong formula S004, MBP-1→MBP-10 S002/S005, wrong imbalance values S003, PIN premium stat S009, SEC-31 fee re-pin S001 FY2026); GROK-NEEDED sections added where web evidence insufficient |
| REVIEW2 wave 2 (signals, 2nd pass subset) | S001, S026–S049, S051–S066, S068, S072–S075 | `e70eae5` | 46 modules bumped 1.1.0/1.0.1; real bugs: S001 SEC-31 fee re-pin, S034 leak-veto inconsistency, S053 raw-vs-demeaned zero crossings, S059 edge_bps x10000, S060 rho_min units, S061 FX convention, S074 bogus Danilova/Julliard citation quarantined, stale-cost gates/TTLs corrected |
| ROUND 2 (strategies) | T001–T100 | _(in progress below)_ | |
| ROUND 2 (regimes) | R001–R050 | _(pending)_ | |

## Progress (rounds coordinated by this agent)

| Module | Worker | Gaps found | Filled | Unverifiable | GROK-NEEDED | Tests | Status |
|---|---|---|---|---|---|---|---|
| _(rows appended as workers report)_ | | | | | | | |

## Commits pushed

| Commit | Modules | Notes |
|---|---|---|
| `e70eae5` | S001, S026–S049, S051–S066, S068, S072–S075 (46 modules) | Deep-review wave 2: each bumped 1.0.0 → 1.1.0/1.0.1, changelog entries, fixtures/tests strengthened |

## Wave 2 results (committed in e70eae5)

Format: Module | Version | Tests (pass/exit 0) | Notable fixes | GROK-NEEDED

| S001 | 1.1.0 | 12 | SEC §31 fee re-pinned to FY2026 advisory ($20.60/M eff 2026-04-04); borrow_bps→borrow_bps_per_day; regime enum `kills`→`inverts`; staleness TTL enforced | yes (3 pre-existing) |
| S026 | 1.1.0 | 10 | Citation corrected: Gao-Han-Li-Zhou 2018; Heston-Korajczyk-Sadka 2010; edge_bps formula fixed | none |
| S027 | 1.1.0 | 7 | Polygon→Massive rebrand ($29/mo Starter documented); mechanism classifier normative | none |
| S028 | 1.1.0 | 11 | Test cost stub gained maker-rebate branch; anti-lookahead pinned | none |
| S029 | 1.1.0 | 10 | Test stub implemented OR-leg entry + maker rebate | none |
| S030 | 1.1.0 | 13 | Caught NaN-stub bug (NaN<=0 False); fee as-of documented (SEC 34-104783) | none |
| S031 | 1.1.0 | 9 | locate_ok explicit stub param; Cowles-Jones citation DOI verified | yes (3) |
| S032 | 1.1.0 | 8 | TTL 180s→345600s (daily module); fixture day-count 1,950→1,980; Pukthuanthong-Le & Corbett not found → [unverified] | yes (3) |
| S033 | 1.1.0 | 9 | NYSE Pillar Msg 105 / Arca XDP 157 / NOII documented; regime_ids populated | none |
| S034 | 1.1.0 | 8 | FIXED: leak veto was literal, vetoed flagship example → mechanism-based rule; Polygon Stocks doesn't cover futures → ETF leg | none |
| S035 | 1.1.0 | 9 | borrow_bps_per_day 0.20 (short-leg over 5-day hold); r_hold non-leak test | none |
| S036 | 1.1.0 | 10 | Lou–Polk–Skouras 2019 evidence added (pattern-context, not backtest) | none |
| S037 | 1.1.0 | 9 | LM Gumbel quantile verified computationally = 2.9701952 | none (optional) |
| S038 | 1.1.0 | 10 | Roll 1984 citation added; Nasdaq $0.0030/share fee cross-check | none |
| S039 | 1.1.0 | 9 | FIXED: edge_bps referenced undefined f; regime `none`→`double` enum | none |
| S040 | 1.1.0 | 7 | sigma<=0 → UNKNOWN (ZeroDivisionError path closed) | none |
| S041 | 1.1.0 | 12 | FIXED: size_shares referenced undefined adv_shares | none |
| S042 | 1.0.1 | 8 | FIXED: float-noise knife-edge at >=0.015 threshold (tol 1e-12); test md COST stack divergence aligned; 1-min vs daily reconciliation | none |
| S043 | 1.1.0 | 8 | FIXED: test cost stub 2.65 bps vs md 1.80 bps aligned; CBOE ORF $0.0017/contract documented | yes (1) |
| S044 | 1.1.0 | 8 | Tag-law [documented-as-*] → [documented]; duplicated direction assignment removed | none |
| S045 | 1.1.0 | 11 | cost_gate_k fixed 0.5 [default] per proposal open item | none |
| S046 | 1.0.1 | 12 | Nasdaq Rule 7018 $0.0030/share documented → fee 0.30→0.60 bps | yes (1) |
| S047 | 1.1.0 | 11 | Roll identity pinned exact; data-tier SIP-vs-tick inconsistency fixed | none |
| S048 | 1.1.0 | 14 | Shock identification normative (5× median volume + 3× median spread) | none |
| S049 | 1.1.0 | 9 | FIXED: formation window hardcoded → Config.form_days; borrow lump → bps/day | none |
| S051 | 1.1.0 | 9 | FIXED: §S2 edge_bps=0 vs stub 5.0 → normative cost-gate ruling; Holý arXiv:1811.09312v2 added | none |
| S052 | 1.1.0 | 8 | KF implementations deduplicated | none |
| S053 | 1.1.0 | 8 | FIXED: raw vs demeaned zero crossings (Pair B/C redesigned as definition pins); Do&Faff lead flagged | none |
| S054 | 1.1.0 | 7 | p_L/p_U defaults retagged [documented] (Xie/Liew/Wu/Kinlay) | yes (3) |
| S055 | 1.1.0 | 10 | Johansen rank test per statsmodels semantics; Cheung & Lai 1993 replaces unverifiable claim | none |
| S056 | 1.1.0 | 9 | bound stays fee-schedule-derived, not optimized (doctrine preserved) | none |
| S057 | 1.1.0 | 8 | Zhuo et al. 2012 citation completed/verified | none |
| S058 | 1.1.0 | 8 | FIXED: convenience yield y dropped from fair-spread formula → restored | none |
| S059 | 1.1.0 | 11 | FIXED: edge_bps ×100 vs ×10000 (gate unsatisfiable on own fixture) | none |
| S060 | 1.1.0 | 9 | FIXED: min_abs_hy unit bug (HY-covariance vs |rho| scale) → rho_min=0.35; cost gate assert→veto | yes (2) |
| S061 | 1.1.0 | 11 | FIXED: FX convention (USD-per-local); expected bar-4 flipped +1→0, hand-verified | yes (3) |
| S062 | 1.1.0 | 8 | NYSE Arca fee schedule documented (Tier-1 $0.0029 Tape A/C) | none |
| S063 | 1.1.0 | 8 | Yang–Zhang k-weight formula documented | none |
| S064 | 1.1.0 | 8 | Lee–Mykland Gumbel .01 critical ≈4.6 [unverified] noted | yes (1) |
| S065 | 1.1.0 | 9 | QLIKE OOS objective documented (S066 evidence) | none |
| S066 | 1.1.0 | 8 | Pseudocode used fixture-scale 12-day mean → normative 22-day mean | none |
| S068 | 1.1.0 | 7 | Tape 8→70 days; VX slope→edge mapping flagged as [example] | yes (3) |
| S072 | 1.1.0 | 15 (11+4 param) | FIXED: staleness TTL 3s→1.5×cadence (daily module); validated ALL bars not just last | none |
| S073 | 1.1.0 | 8 | OPRA pricing re-pinned $199/mo [documented] | yes (2) |
| S074 | 1.1.0 | 8 | FIXED: staleness TTL 3s→259200s; FAKE citation quarantined (Danilova/Julliard SSRN → unrelated law paper); Ni/Pearson/Poteshman corrected to (2005) | yes (1) |
| S075 | 1.1.0 | 10 | FIXED: staleness TTL 3s→26h; Cboe fee schedule pinned 2026-08-03 [documented]; dangling S069 VRP gate wired | yes (2) |

## GROK-NEEDED (deduplicated, for parent delegation — coordinator cannot launch browser tasks)

_(append as workers flag)_

- [S032-Q1] Does a 2024 paper by Pukthuanthong-Le & Corbett on regime-switching/tail-risk/safe-havens exist? Exact title/venue/DOI; if none, confirm spurious.
- [S032-Q2] Current Polygon.io (Massive) Stocks plan tiers/pricing as of Sep 2026 (Starter/Developer/Advanced $29/$79-99/$199) — confirm.
- [S032-Q3] Sanity-check calibration OOS metric choice (avoided-drawdown bps per veto-day, 20-day embargo) for crisis-veto overlay.
- [S043-Q1] Correct low-build translation of monthly IV−RV vol-point spread into bps edge (vega×spread vs dimensionless form)?
- [S046-Q1] Published intraday U-shape absolute-move benchmark (per-window mean |return| in bps, open/lunch/close, large-cap US) to seed typ/sd as [documented]?
- [S054-Q1] OOS selection criterion for p_L/p_U grids: median-of-3 net-Sharpe vs rolling OOS log-likelihood; is 5-day embargo standard for daily copula pairs?
- [S054-Q2] Should retail adopt cumulative-mispricing-index parameterization (Δ1=0.6/Δ2=−0.6) vs raw p_ab thresholds?
- [S054-Q3] Right amortization horizon for short-leg borrow on daily copula pairs (10-day hold assumption)?
- [S060-Q1] What certified-lead hit rate (OOS, net of costs, ±50–100ms timestamp-shift stress) makes sub-second HY lead-lag monetizable, and what colocated latency budget?
- [S060-Q2] Production certification: Hoffmann–Rosenbaum–Yoshida (2013) contrast estimator vs simple argmax-ρ̂ + timestamp-shift stress?
- [S061-Q1] Typical ADR depositary issuance/cancellation all-in fees (bps) for liquid programs.
- [S061-Q2] Empirical premium half-life estimates for liquid ADRs.
- [S061-Q3] Representative GC vs HTB ADR stock-loan fee ranges.
- [S064-Q1] False-flag rate of Lee–Mykland test at 3.5/4.0/4.5 thresholds (and leave-one-out BV variant) vs power on labeled jump days, on 5-min production universe.
- [S068-Q1] Empirically defensible mapping from VX 1×2 slope (points) to tradable edge (bps) for cost-gate sizing.
- [S068-Q2] Inversion threshold / z-lookback combo maximizing OOS inversion precision on real CFE data.
- [S068-Q3] z-confirm veto: z<−1.0 vs percentile-based confirm given slope skew?
- [S073-Q1] Empirically grounded calibration target for edge_bps = u·β (forward |move| vs unusualness score u).
- [S073-Q2] Desk-standard convention for directional attribution of unsigned unusual prints (call/put split, protective-put filtering).
- [S074-Q1] Dealer-sign convention mapping from public OI to net dealer gamma — is "total_gex<0 ⇒ dealers short gamma ⇒ amplify" the desk standard?
- [S075-Q1] Published practitioner/academic source for trade-level dispersion returns to set edge_bps β as documented rather than fitted.
- [S075-Q2] Traded dispersion-book conventions: realized-corr window (30d vs 63d), entry-spread thresholds, standard crisis-tail hedge.
- [S001-Q*] 3 pre-existing expert questions (XNAS/XNYS marginal take-fee tier; empirical per-unit-z edge β ~500ms; CCZ PCA transferability + OOS R² decay).
