# Deep-review pass 2 (REVIEW2) — status

Coordinator: deep-review subagent. Started 2026-09-10 (UTC 2026-09-11).
Rule: one worker per module ID; workers touch ONLY their own .md + fixtures + tests.
Commits: every ~25 modules done, `git status` + fetch first, stage ONLY modules/ files.

## Completed waves

| Wave | Modules | Commit | Result |
|---|---|---|---|
| REVIEW2 wave 1 (signals) | S001–S100 | `4d281e6` | All 100 signal modules deep-reviewed; fixtures regenerated; 7–18 gaps fixed per module (real bugs: wrong formula S004, MBP-1→MBP-10 S002/S005, wrong imbalance values S003, PIN premium stat S009, SEC-31 fee re-pin S001 FY2026); GROK-NEEDED sections added where web evidence insufficient |
| REVIEW2 wave 2 (signals, 2nd pass subset) | S001, S026–S049, S051–S066, S068, S072–S075 | `e70eae5` | 46 modules bumped 1.1.0/1.0.1; real bugs: S001 SEC-31 fee re-pin, S034 leak-veto inconsistency, S053 raw-vs-demeaned zero crossings, S059 edge_bps x10000, S060 rho_min units, S061 FX convention, S074 bogus Danilova/Julliard citation quarantined, stale-cost gates/TTLs corrected |
| REVIEW2 final signal wave (3rd pass) | S067, S069–S071, S076–S100 (29 modules) | _below_ | All 29 bumped 1.0.0 → 1.1.0 with §0 changelogs; 421 tests green; real bugs: S076 dead cost-gate, S089 dropped γσ²(T−t)/2 term, S090 dead `mixed` branch, S096 pseudocode contradicted fixture, S097 dropped cost gate + wrong sent_min, S100 assert-vs-veto + C2 violation, S081 persistence/κ_exit, S088 embargo-floor violation, S083 impossible tick_done, S094 unbound drift edge, S084 mis-titled Campigli cite, S087 wrong-signed FFD, S082 shredded skip list + bps/pence units, S092 dead cooldown + 404 repec URL; duplicate S092/S093 worker collisions reconciled; GROK-NEEDED additions captured per module |
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

## Final signal wave results (S067, S069–S071, S076–S100 — 29 modules)

All bumped 1.0.0 → 1.1.0 with §0 changelog entries. Real-bug fixes and GROK-NEEDED from worker reports; tests verified green by coordinator.

| Module | Tests (pass/exit 0) | Notable fixes | GROK-NEEDED |
|---|---|---|---|
| S067 | 20 | Broken source URLs/DOIs repaired; Stooq 5-min coverage (~15d) flagged insufficient for 20d default window; cost gate veto path pinned | none (all claims web-verifiable) |
| S069 | 12 | Bollerslev–Marrone–Xu–Zhou authorship corrected; Martin 2011 NBER WP 16884 description corrected; Cboe schedule pinned 2026-07-20 | yes (4) |
| S070 | 11 | §S0.1 <2-events→UNKNOWN claim contradicted arithmetic — corrected; size_shares unbound adv_shares fixed; dead cost-gate veto documented (9.6 ≤ 0.5·80·z always) | yes (3) |
| S071 | 15 | OPRA.PILLAR history starts 2023-03-28 documented (constrains 6-yr walk-forward); LiveVol IV-surface price unverifiable — needs vendor quote | yes (4) |
| S076 | 13 | Dead cost-gate veto (edge_bps=rr×8.0 never binds) fixed: edge_bps=max(0,rr−k)×10.0; squeeze-p10 short-tape anchoring pinned | yes (2) |
| S077 | 18 | Vacuous P_max veto applied to predicted variance Pp; Config ranges that excluded defaults fixed; undeclared params added | yes (3) |
| S078 | 10 | §S4 tape narrative spurious "−3.04" return corrected; truncated source URLs repaired (Roll 1984 DOI verified); test ref diverged from chapter (staleness/halt guards, maker rebate) — aligned | yes (4) |
| S079 | 14 | Six truncated citations/URLs restored; nine undefined pseudocode symbols bound; XNAS/SEC fees documented; explicit gate-pass fixtures | yes (4) |
| S080 | 11 | z_exit defined (1.0); m default 1 vs 3 reconciled to 3; W=252 outside 60–250 range fixed; AL-2010 BEFORE→AFTER-cost (Sharpe 1.44); invalid-input check falsely UNKNOWN'd negative returns — scoped | yes (3) |
| S081 | 14 | Entry "sign persistence over 3 events" implemented (persist_n=3); κ_exit added (1.5); COST callable 3.7 vs block 7.40 vs test stack — unified to 7.40; garbled §1.5 skip list rewritten; Muni Toke & Yoshida XETRA claim corrected | yes (4) |
| S082 | 21 | Three §0 sources truncated mid-sentence — rebuilt full; §1.5 skip list shredded character-by-character — rewritten; bps/pence unit inconsistency in COST fixed; risk-limit row 0.5 vs p_max 0.25 reconciled to 0.25 | yes (3) |
| S083 | 13 | Fixture tick_done=1 at ev4 with tick_n=5 (impossible close) → 0; truncated citation + wrong mlfinlab URL fixed; test/md cost signature drift aligned | yes (4) |
| S084 | 16 | Campigli et al. mis-titled (that's Dufour & Engle's title) → arXiv:2212.12687v1; Dufour & Engle "via CFS" → JF 55(6); edge_bps mislabeled cents-as-bps; cost gate didn't bind on direction (contradicted C2) — now binds | yes (3) |
| S085 | 22 | §S3 multiplicative P·(1±kσ̂) contradicted additive fixture P±kσ̂ — additive canonical; callable maker-rebate branch contradicted zero stack — removed; truncated source URLs repaired | yes (3) |
| S086 | 10 | Dead darufinance URL (github.com/) replaced with real Project 09 README; numbers enriched (log-loss 0.68 vs 0.81; 0/40 DSR>0.95); PBO/Harvey-Liu/AFML citations enriched with verified facts | yes (3) |
| S087 | 14 | §S3 Σw_k x_{t−k} put w_0 on latest bar, fixture puts it on earliest — formula fixed (old gave 34.944, fixture 38.438); "d=1 → first differences" was wrong-signed (x_{t−1}−x_t); cost callable maker-rebate removed | yes (5) |
| S088 | 14 | Fixture used embargo_n=3 with 5-day horizon — violated own floor L_E ≥ max(t_1−t_0) → raised to 5, fixture regenerated; "embargo before the fold" convention wrong (AFML 7.2 drops train rows after test fold) — both conventions now implemented/tested; Bailey PBO numerals retagged [unverified] | yes (4) |
| S089 | 13 | §S3 δ* formula dropped γσ²(T−t)/2 finite-horizon term — restored; symbol collision k (0.5 gate vs 1.5 book-depth) → k_gate; undefined A added (140.0); breach UNKNOWN vs DEGRADED standardized to DEGRADED pull; capital 0.25× → 0.5× | yes (3) |
| S090 | 14 | Dead `mixed` branch: persist/revert checked before contradiction — fixture contradicted doctrine → precedence fixed (row 9 now `mixed`); direction −1 on revert → 0; cost callable flat 2.0 → 4-component stack; gate veto decorative → C2-veto | yes (3) |
| S091 | 15 | Test cost decomposition 2.0/1.0/0.0/0.0 vs chapter 1.5/0.5/0.0/1.0 — fixed to mirror; zero-sentiment capital bug (direction −1 with nonzero capital for S_b=0) — forced 0; fake regime IDs R-liquidation-cascade/R-venue-stress replaced with real R017/R019/R013/R012 | yes (3) |
| S092 | 16 | cooldown checked but never armed → armed per jump-event-id; assert i>=lookback / sigma>0 would crash → UNKNOWN guards; test CFG threshold 3.5 vs chapter 3.0 aligned; cost stack spread 2.0/fees 1.0 vs block 2.5/0.5 → mirrored exactly; repec URL 404 fixed | yes (4) |
| S093 | 16 | md cost 3.0/1.0/0.0/3.0 vs test 2.0/1.0/1.0/3.0 → unified 2.0/1.0/1.25/3.0=7.25; hand-check mis-tagged [documented]→[example]; invented `licensing@benzinga.com` from concurrent wave-2 pass removed; duplicate worker edits consolidated to honest 1.1.0 | yes (5; +3 from second reviewer) |
| S094 | 14 | Unbound cost-gate edge (illustrative_drift_bps undefined, reference gated on realized edge → spurious bin-4 fail) → expected_drift_bps=15.0 bound ex-ante; §S4 "(25+18−0)/43" vs bin-4 buy 43/sell 0 → corrected; trigger rule |BLOCKIMB|>0 vs block-volume threshold — unified | yes (3) |
| S095 | 14 | md z_cut=3.0/trail_n=30 vs fixture 2.5/5 — aligned to 2.5/5; cost gate as assert (would raise) → veto; cost stack components/side didn't mirror block — mirrored; negative-extreme direction +1 undocumented — now specified | yes (3) |
| S096 | 17 | §S3 shock rule contradicted fixture (h48/h49 shock_flag=1 would never flag) — normative rewrite; test cost 3/8/10 vs chapter 10/6/5 — unified 10/6/0/5; phantom CFG params (k_oi, depth_drop, m_liq) removed; h51 "~40×" → ~61× | yes (2) |
| S098 | 14 | md sqz_crowd=3.0/sqz_util=0.8 vs reference 0.60/90.0 — 0.8 dimensionally wrong on percent-unit util → aligned to 0.60/90.0; F1 guard let +inf fees through → non-finite rejected | yes (4) |
| S099 | 13 | md delta=0.5 vs test delta=1.0 aligned to 0.5; COST 0.75/1.50 vs block 1.0/2.0 contradiction fixed; C2 said sub-threshold→0 but doctrine direction always 1 — amended; ASVI reference computed log(current)−median(log(prior8)) vs prose log(current)−log(median(raw prior8)) — corrected to retain raw SVI; pytrends archived read-only 2025-04 documented | yes (2) |
| S097 | 13 | COST total 15.0 vs 10.0+1.75+0.0+3.0=14.75 — fixed; default sent_min=0.15 made day-6 fire impossible → 0.10; test z_entry=1.96 vs md 3.0 aligned; old impl ignored sent_min and dropped cost gate (never vetoed) — both now enforced; Hasso et al. FRL 44:102636 → 45:102140; AUCTION updated computed_at without new fill — fixed; IBKR Pro fee schedule pinned 2026-09-10 | yes (4) |
| S100 | 14 | Cost gate as assert (exception) + fixture emitted ±1 with gate_pass=0 — violated C2 → veto semantics; Livnat & Mendenhall DOI 10.1111/...00194.x → ...00196.x; "tiers at ±1.0 [documented]" false (Bernard & Thomas use deciles) → [example]; _bad() missed ±inf; boundary float literals never hit ±1.0 — rebuilt with exact arithmetic | yes (3) |


### GROK-NEEDED additions from final signal wave (verbatim from worker reports; web search genuinely could not answer)

**S069:** (1) LiveVol tier/pricing; (2) SPX customer fees; (3) after-cost VRP Sharpe; (4) Databento OPRA backtest cost.
**S070:** (1) For short event straddles on liquid US names, what is the empirically typical realized round-trip cost in bps (two-leg half-spread + fees + event-day slippage) — is the module's 9.60 bps reference stack conservative or aggressive? (2) What walk-forward OOS procedure (fold length, embargo, selection metric) do quant vol desks actually use to fit z_star-style fade thresholds on ~12–20 events/name/year without overfitting? (3) Is there any published after-cost P&L (Sharpe, hit rate, per-trade $) for a systematic "fade the rich earnings straddle" strategy, or is the edge only documented as pricing accuracy and practitioner lore?
**S071:** (1) Actual vendor price of Cboe LiveVol's IV-surface product (the $500/mo documented figure covers Open-Close EOD only). (2) Typical 25-delta wing half-spread at the daily close for liquid names. (3) Do walk-forward folds of z_star ∈ {1.5,2.0,2.5,3.0} produce stable thresholds across names, or does the freeze rule collapse to 2.0? (4) Should cost_gate_k be 0.5 or 2.0 — needs live P&L calibration.
**S076:** (1) Any published, after-cost evidence (hit rate, follow-through, Sharpe) for a 1.75× range-ratio expansion trigger on US equities, or for the bar-following direction convention on squeeze resolution? (2) Walk-forward-calibrated values of k, N, and the edge_scale gate-binding point for a 1.75×-class range-ratio breakout on a modern liquid-US-equity universe with purged/embargoed folds — and what OOS cost-gated follow-through do they achieve?
**S077:** (1) Q/R estimation; (2) after-cost Kalman strategy evidence; (3) innovation kurtosis/jump filtering.
**S078:** (1) The actual venue fee schedule (XNAS taker fee + regulatory fees, per-share) to replace the 0.30 bps [example] placeholder, and as of what date? (2) Current easy-to-borrow rates (bps/day) for typical US large-cap shorts. (3) Any published after-cost Sharpe or P&L evidence for standalone 1–5 min AR(1)/ARMA forecast trading? (4) For 1-min AR(1) on US large caps, a realistic calibrated φ range and per-bar net edge after costs from any practitioner source?
**S079:** (1) Avoided-regime-risk edge; (2) HMM refit cadence; (3) hysteresis widths; (4) effective 5-minute half-spreads.
**S080:** (1) OOS-optimal m (# PCA factors) for a broad US large/mid-cap daily panel under a realistic short-borrow cost model — does the residual–market |corr| < 0.3 guard bind before OOS Sharpe peaks? (2) For OU residual s-scores, what r2_crit / κ̂ thresholds survive walk-forward with embargo at realistic turnover — is the AL-2010 κ̂>8.4 annualized cutoff still the right floor on post-2010 data? (3) What fraction of the Epstein PCA+OU net −4.32 collapse is turnover vs shorting costs, and what turnover budget (bps/day) would the standalone trigger need to break even?
**S081:** (1) Practitioner walk-forward calibration grids (α_self/β_self/α_cross/β_cross ranges, refit windows, embargo lengths) for bivariate buy/sell Hawkes MLE on US equities. (2) Measured Lee–Ready trade-signing misclassification rate on modern consolidated SIP data vs direct-feed aggressor side, especially in fast/burst markets. (3) Any published after-cost Sharpe (or even gross P&L) for a raw buy/sell Hawkes intensity-imbalance trigger at seconds horizons? (4) Databento live MBO subscription pricing for a ≤20-symbol US-equities research universe — pay-as-you-go vs plan crossover?
**S082:** (1) Current (2026) LOBSTER academic subscription price and what it includes (symbols, years, levels). (2) Any documented after-cost executable P&L for a DeepLOB-style trigger (post-2019 reproductions with queue/turnover modeled)? (3) What fee tier/rebate schedule applies to the maker's −0.20 bps assumption for an HFT-style venue on the module's target liquidity tier?
**S083:** (1) Empirical basis for the practitioner "≈50 bars/day" target (B*) — documented AFML/mlfinlab recommendation or folklore, and what target maximizes downstream feature stationarity across liquid US equities? (2) For imb_theta = Ê_0[T]·Ê_0[|θ|], which EWMA λ and warmup window are used in production imbalance-bar implementations, and what bar-duration band is healthy before refit? (3) Tick-rule vs exchange side-flag sign agreement rates on modern US consolidated tape (DBEQ.BASIC) — is the ≥80% rule-of-thumb still valid, and when does Lee–Ready with quotes materially change θ? (4) Current (2026) DBEQ.BASIC vs XNAS.ITCH trades historical $/GB from the live catalog, and which dataset practitioners prefer for single-name bar research.
**S084:** (1) On modern fragmented US TAQ, measured Lee–Ready vs quote-rule signing agreement rates for large caps, and does the VAR innovation keep its documented permanent-impact shape on SIP (not exchange-ts) timestamps? (2) Is p≈10 still the literature's working lag default for the Hasbrouck VAR on post-Reg-NMS data, or have documented calibrations moved longer given order-flow long memory? (3) For Escribano & Pascual (2006)'s VEC extension, documented buy-vs-sell informativeness asymmetry magnitudes on recent data — is the spread error-correction term material enough for a phase-2 build?
**S085:** (1) Polygon's current Stocks Advanced list price (as of Sept 2026), and does it include full 1-minute aggregates history? (2) Stooq's current policy/limit for historical-range CSV downloads after the early-2026 CAPTCHA-key change? (3) Any documented practitioner evidence for cost-gate k 0.5 vs 2.0 on a zero-cost infrastructure module's gate?
**S086:** (1) For τ calibration on overlapping triple-barrier labels, what embargo convention do practitioners use — one full label-span vs one session — and how sensitive is the selected τ to that choice? (2) Is the Project 09 minimum-class floor (<50 net-profitable bets) a documented practitioner consensus or project-specific? (3) Is there a documented basis for the cost-gate multiplier k (0.5 vs 2) in the AFML/practitioner literature?
**S087:** (1) The d* scan runs one ADF test per grid candidate on the same training window — does the "smallest d with p < 0.05" rule preserve nominal 5% size, or is a multiplicity correction standard in production FFD pipelines? (2) What embargo length (in 1-min bars) makes train/test ADF statistics approximately independent given the FFD memory tail at d*≈0.3–0.6 — is there a rule linking embargo to L(d*, τ)? (3) Is the corr(x̃, log-price) < 0.3 "d too high" trigger supported by literature/production practice, or purely heuristic? (4) For a universe: per-symbol or pooled d* search given ADF's low power on short 1-min windows, and how do production shops handle cross-sectional d* heterogeneity? (5) For the KPSS complement: the correct joint decision rule (ADF rejects unit root AND KPSS fails to reject stationarity), and is it actually used in production feature pipelines or does it over-gate?
**S088:** (1) Any documented production procedure for embargo length above the floor with measured leakage residuals per choice? (2) Measured leakage difference between test-head vs after-fold embargo conventions on triple-barrier daily-bar labels? (3) Documented validity comparison of purged walk-forward vs purged K-fold under regime drift with a switching rule? (4) Confirm/correct the PBO paper's test-case numerals from the paper text.
**S089:** (1) The qca replication shows the paper's Table 1 drops the γσ²(T−t) term — any published or practitioner evidence on whether the full finite-horizon δ* vs the constant-term spread performs better in live quoting, and which variant production A-S desks actually run? (2) For γ/k/A joint calibration: is maximizing OOS (mean_pnl − 3×std_inventory) subject to gate pass-rate ≥95% the right selection metric, or do practitioners fit directly against the A-S value function / realized fill-intensity KS tests? What refit cadence survives fee-tier changes? (3) The standard production extension of A-S that preserves closed-form quotes while handling adverse selection (Guéant-Lehalle-Tapia inventory bounds? Cartea-Jaimungal ambiguity aversion? Hawkes-arrival intensities?) — and does it change the δ* formula or just add a veto layer?
**S090:** (1) Practitioner-standard calibration for daily-equity VR regime labels: accepted grid for (k_fast, k_slow, window, persist/revert thresholds), and is label-stability or regime-conditioned consumer Sharpe the better OOS selection metric? (2) The confidence mappings (min(1, 2·|VR−1|) etc.) are invented [example] — is there a principled map from VR distance-to-1 into [0,1], e.g. via the Lo–MacKinlay asymptotic variance of the VR estimator? (3) Cost-gate k default 0.5 vs 2 — any practitioner guidance on the fee-covering multiple for regime-gated (never directly traded) signals?
**S091:** (1) Any published out-of-sample evaluation of a Benzinga/ESS-style first-minute news-reaction rule after transaction costs on US equities (2015+), or is all tradability evidence pre-cost? (2) Documented enterprise price band for Benzinga's machine-readable News API (v2 schema) for a quant research/production license? (3) Effective half-life (in minutes) of the first-minute news-reaction leg on large-cap US names post-2020, from any practitioner or academic measurement?
**S092:** (1) Benzinga's current machine-readable News API pricing (per-month tiers or per-call), and which plan includes the created_at-level timestamp feed needed for point-in-time news joins? (2) For Benzinga stories, which timestamp field (created_at vs updated_at) corresponds to first public availability, and is there a first_seen/published distinction in the schema? (3) Empirically, what news_window_min (5/15/30/60) maximizes after-cost $/event for 5-min jump follow/fade — any published calibration of news-match windows for jump decomposition? (4) Current XNAS Rule 7018 removal-fee schedule version (any 2026 amendments changing the $0.0030/share reference), and the typical stock-loan fee range for intraday large-cap shorts?
**S093:** (1) What do RavenPack News Analytics / Benzinga newswire licenses actually cost for systematic-trading use, and do terms permit derived novelty features? (2) Any published calibration of the 0.5 novelty gate or measured after-cost performance of a stale-news reversal strategy (Tetlock is before-cost; FININ is a model, not a traded strategy)? (3) Documented holding horizon/after-cost magnitude for the ride leg (novel-news drift)? (4) Actual commercial price band for RavenPack News Analytics full-text license for a single-strategy fund? (5) Does Benzinga offer an enterprise Newsfeed API license, at what band (only retail Pro ~$37–197/mo is public)? (6) Is τ=0.5 a defensible staleness gate for TF-IDF (vs embedding) novelty, and how does the TF-IDF→embedding similarity mapping shift it? (7) Defensible realized borrow-bps-per-day and spread realization (vs quoted) on the 1–5-day short fade leg in large caps? (8) Optimal n_prior × max-window-span for the trailing centroid before regime contamination?
**S094:** (1) What ex-ante expected drift per gated 5-min RVOL+block-imbalance signal (bps) should seed the cost gate on liquid US equities — is the chapter's 15 bps [example] conservative or aggressive versus measured post-publication implementations? (2) Current Lee–Ready classification accuracy against audit-trail truth on modern feeds (especially midquote prints) — is Ellis–Michaely–O'Hara (2000, TORQ-era) still the best available benchmark, or is there a newer audit-trail validation study? (3) For walk-forward calibration of 5-min intraday signals across 500 names, what embargo length and fold geometry best controls cross-sectional leakage from common factor days (the chapter's 5-day embargo is a guess)?
**S095:** (1) Calibrated (z_cut, trail_n) selection statistics and measured out-of-sample avoided-drawdown-after-costs for a funding-rate z-score leverage governor on real perpetual funding panels — no public study found. (2) The current CoinGlass API price list (Hobbyist → Enterprise) as of 2026-09-10, from an official citable page. (3) Production thresholds for cross-venue print divergence that trigger a stand-down in live funding governors (the R017 condition) — practitioner-internal, no public source found.
**S096:** (1) Measured post-confirmation fade edge: forward return from the first post-cascade funding flip over 4–24h on BTC perps, net of ~21 bps costs — no published study found. (2) Calibration of shock_liq_mult / shock_px_pct / shock_oi_pct on censored reported liquidation data — no public parameter study; must run the §S2 walk-forward recipe on desk data.
**S097:** (1) Any published out-of-sample calibration of concentration-based manipulation filters (HHI-style) in social-volume trading signals — empirical support for hhi_max ≈ 0.25, or a defensible alternative? (2) Verify current official X API v2 pricing: pay-per-use $0.005/post read (default since Feb 2026 per news) and current Basic/Pro/Enterprise tier rates as of 2026-09-10. (3) Verify Reddit Data API current commercial pricing/contract terms, and StockTwits API Enterprise plan pricing (no public rate card found). (4) Any published daily-horizon study of a sentiment→volume-lead composite (like S = z_vol × w_sent) with checkable OOS results?
**S098:** (1) Actual enterprise list prices / tier breakpoints for IHS Markit Securities Finance and S3 Partners Black App/Blacklight (per-seat vs per-entity, feed vs UI)? (2) The exact FINRA short-interest machine-readable download endpoint and file layout for automated ingestion. (3) Any published, peer-reviewed calibration of borrow-stress squeeze-corner thresholds? (4) ORTEX retail-tier pricing for short-interest/borrow data as a cheaper alternative panel.
**S099:** (1) Under Google's gated first-party Trends API as available today, what are the exact weekly interest-over-time request/response fields, quota, price, publication lag, sampling policy, and point-in-time vintage guarantees? (2) For stock-level weekly ASVI, what empirically validated anchor-query or stitching method makes normalized Google Trends observations comparable across point-in-time weekly vintages without lookahead, and what measurable instability threshold should force UNKNOWN?
**S100:** (1) Current price band (as of 2026-09-10) for the Massive API Benzinga earnings add-on (Business tier + Benzinga license) serving GET /benzinga/v1/earnings — which plan tier includes release date/time + consensus + actuals + surprise %? (2) Any citable practitioner/academic source using a ±1.0-standard-deviation SUE tier cutoff (rather than decile/quintile sorts) for earnings-surprise entry rules? (3) Measured first-quote/open-auction fill statistics after earnings announcements (open gap distribution, adverse-fill rates) — any citable source or must this be measured live?
**S067:** none — every factual claim web-verifiable.
