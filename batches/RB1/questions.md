# RB1 — Grok questions (regimes R001–R010)

- Batch: RB1 — Volatility regimes + trend/range + spread (R001–R010)
- Bot: Grok (grok.com), signed in — record account + date + chat URL when answered
- Protocol: ask the three questions ONE AT A TIME in one chat, each only after the prior
  answer fully completes. Capture verbatim into `batches/RB1/grok-answers.md`.
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
R001 realized-volatility level · R002 implied-vs-realized spread (variance risk premium) ·
R003 volatility term-structure slope · R004 volatility clustering/persistence ·
R005 jump regime · R006 vol-of-vol · R007 trend strength (ADX/Hurst) ·
R008 range compression/expansion (squeeze) · R009 mean-reversion vs momentum dominance
(variance ratio) · R010 spread regime (quoted/effective spread percentile)

---

### Q-RB1-1 — definitions + exact formulas + worked numeric examples
```
For each of the 10 regimes R001–R010 above, give: (1) the PRECISE definition,
(2) the EXACT calculation formula with every symbol defined (units included) plus the data
inputs required, (3) typical parameter ranges and regime threshold bands — and label each
band as documented-with-citation or illustrative-example, (4) ONE concrete worked numerical
example per regime with every intermediate number shown (use small synthetic datasets, e.g.
10 daily closes for a Parkinson/Garman-Klass realized-vol computation; a VIX=22 / RV=16
pair for the variance risk premium; VIX=20 / VIX3M=24 for term-structure slope; a 6-observation
return series for a Lee-Mykland-style jump check; 14 Wilder-smoothed values for ADX;
a 20-bar series for Bollinger bandwidth percentile; an 8-return series for variance ratio
VR(2); a 10-quote tape for time-weighted quoted spread). Show the final regime
classification for each example. Cite the source paper for each formula.
```

### Q-RB1-2 — local M5 Max build + automated-loop detection spec
```
I have a Mac with Apple M5 Max and 128GB unified memory (sunk cost, already owned).
For computing all 10 regime indicators R001–R010 DAILY over a 500-stock US universe plus
intraday refresh for R001/R007/R010: (1) what data feed do I need — exact product names
(e.g. Databento OHLCV-1 vs SIP, CBOE VIX history, options surface vendor), (2) expected
compute time for the full universe daily refresh in Python+polars, (3) RAM and disk for
60 days of 1-min bars + daily bars for 500 symbols, (4) engineering hours for a correct
causal pipeline (no lookahead: percentile lookbacks strictly trailing), (5) buy-vs-build:
name vendors with INDICATIVE monthly pricing (mark as indicative) and give a build-vs-buy
verdict for a one-person research operation. THEN specify the automated detection loop for
these 10 regimes: which software agent computes each indicator and on what cadence, the
independent verification step for each (second estimator + agreement tolerance), and the
fail-safes (missing data, stale data, out-of-bounds values — what state does the regime
take and what must downstream signals do).
```

### Q-RB1-3 — efficacy impact (direction + mechanism) + documented evidence + failure modes
```
For each regime R001–R010: (1) HOW does it modulate signal/strategy efficacy — state the
DIRECTION explicitly (which strategy families improve, which die) and the MECHANISM
(e.g. "edge minus spread turns negative when effective spread exceeds 4 bps"),
(2) DOCUMENTED evidence with citations — published papers or practitioner accounts showing
the efficacy difference across the regime (before/after-cost labeling; markets and periods
studied), (3) WHEN the regime classification itself fails — misclassification costs,
lookahead traps (e.g. percentile computed in-sample), and estimator disagreement cases,
(4) how these regimes COMPOUND jointly (e.g. high realized vol + wide spreads + toxic flow
is one untradeable state, not three filters). End with an honest bottom line per regime:
is it a trade trigger, a sizing input, or a stand-down flag.
```
