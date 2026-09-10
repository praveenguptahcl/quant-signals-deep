# RB4 — Grok questions (regimes R031–R040)

- Batch: RB4 — Cross-asset stress + calendar/event regimes (R031–R040)
- Bot: Grok (grok.com), signed in — record account + date + chat URL when answered
- Protocol: ask the three questions ONE AT A TIME in one chat, each only after the prior
  answer fully completes. Capture verbatim into `batches/RB4/grok-answers.md`.
- Handling: treat answers as *leads*, not facts. Anything without a checkable source
  (paper title/URL/arXiv ID) goes under `Unverified leads` in the chapter, never in `Sources`.
- All thresholds and dollar figures are illustrative examples unless documented with a citation.
- Nothing here is a live-trading spec.

**Standing context to paste with Q1 (bots need it once):**
> Context: I am writing deep-dive chapters for a quant research document. Each chapter covers
> one MARKET REGIME — a measurable market state that modulates trading-signal efficacy.
> All numbers you give must be labeled as documented (with a citable paper/URL) or as
> illustrative estimates. Never invent paper titles, URLs, or statistics. Formulas must be
> exact with every symbol defined.

**Regimes in this batch:**
R031 cross-asset correlation regime · R032 flight-to-quality (stock/bond correlation sign) ·
R033 systemic tail-risk / crisis regime · R034 energy/commodity shock regime ·
R035 earnings proximity / earnings season · R036 macro announcement windows ·
R037 month/quarter-end rebalancing · R038 thin-liquidity sessions ·
R039 options expiry / OpEx pinning · R040 index rebalance days

---

### Q-RB4-1 — definitions + exact formulas + worked numeric examples
```
For each of the 10 regimes R031–R040 above, give: (1) the PRECISE definition,
(2) the EXACT calculation formula with every symbol defined (units included) plus the data
inputs required, (3) typical parameter ranges and regime threshold bands — and label each
band as documented-with-citation or illustrative-example, (4) ONE concrete worked numerical
example per regime with every intermediate number shown (use small synthetic datasets, e.g.
a 5-asset × 10-day return panel for mean pairwise correlation; SPY/TLT 63-day correlation
+0.35 for the flight-to-quality state; a tail-count over 8 benchmarks with 3 breaching
2.5σ on the same day for the crisis flag; WTI +18% in 20 days for the shock z-score;
a name 2 days pre-earnings with IV ranked at the 90th percentile; a CPI-day window map
(T−60m compression / T…T+15m repricing / digestion) with spread multiples; month-end
rebalance pressure arithmetic for one index name; a half-day session with VPace 0.55;
max-pain arithmetic on a 5-strike chain for OpEx pinning — and note that daily 0DTE
expiries have diluted classic monthly pinning, so 2010s pinning statistics must not be
applied to 2026 without re-verification; index add/delete dollar-flow arithmetic for a
rebalance name). Show the final regime classification for each example. Cite the source
paper or data source for each formula.
```

### Q-RB4-2 — local M5 Max build + automated-loop detection spec
```
I have a Mac with Apple M5 Max and 128GB unified memory (sunk cost, already owned).
For computing all 10 regime indicators R031–R040: (1) what data feeds do I need — exact
product names (benchmark ETF/index data vendor, FRED series, futures vendor for WTI,
earnings-calendar vendor with announced-vs-actual timestamp handling, economic calendar
vendor, index announcement calendars, exchange holiday/half-day calendar, options OI
snapshots), (2) expected compute time for the daily refresh in Python+polars,
(3) RAM and disk budgets, (4) engineering hours for a correct causal pipeline,
(5) buy-vs-build: name vendors with INDICATIVE monthly pricing (mark as indicative) and
give a build-vs-buy verdict for a one-person research operation. THEN specify the
automated detection loop: which software agent computes each indicator and on what cadence,
the independent verification step for each (second estimator + agreement tolerance), and
the fail-safes. Explicitly cover: benchmark-set fixation ex ante (no cherry-picking —
Adversary checks), earnings timestamp accuracy (after-hours vs before-open — close-to-close
event returns do NOT demonstrate intraday tradability), calendar-feed outages (fallback:
assume no-trade windows around known monthly dates), and futures-roll handling for the
commodity shock series.
```

### Q-RB4-3 — efficacy impact (direction + mechanism) + documented evidence + failure modes
```
For each regime R031–R040: (1) HOW does it modulate signal/strategy efficacy — state the
DIRECTION explicitly (which strategy families improve, which die) and the MECHANISM
(e.g. "in correlation monoculture the market-factor R² → 1, residual variance → 0, so
idiosyncratic signals drown"; "pre-event compression kills breakouts via false breaks
while the post-print reaction window has the month's highest genuine-information density"),
(2) DOCUMENTED evidence with citations — before/after-cost labeling, markets and periods
studied (e.g. documented post-earnings announcement drift; documented month-end reversal;
documented crisis correlation → 1), (3) WHEN the regime classification itself fails —
misclassification costs, announcement-window spread blowups (3–5× — market orders in the
first 60 seconds fill at the worst print), thin-session backtest flattery (backtests must
exclude or separately model half-days), (4) how these regimes COMPOUND jointly. End with an
honest bottom line per regime: trade trigger, sizing input, or stand-down flag.
```
