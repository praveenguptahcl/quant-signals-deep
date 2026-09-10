# RB3 — Grok questions (regimes R021–R030)

- Batch: RB3 — Positioning + macro regimes (R021–R030)
- Bot: Grok (grok.com), signed in — record account + date + chat URL when answered
- Protocol: ask the three questions ONE AT A TIME in one chat, each only after the prior
  answer fully completes. Capture verbatim into `batches/RB3/grok-answers.md`.
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
R021 retail-flow dominance regime · R022 hard-to-borrow / short-squeeze regime ·
R023 liquidation-cascade regime (crypto) · R024 interest-rate level/direction regime ·
R025 yield-curve shape regime (2s10s) · R026 inflation-surprise regime ·
R027 growth-surprise regime (economic surprise index) · R028 credit-stress regime (HY OAS) ·
R029 dollar regime (DXY) · R030 central-bank event proximity

---

### Q-RB3-1 — definitions + exact formulas + worked numeric examples
```
For each of the 10 regimes R021–R030 above, give: (1) the PRECISE definition,
(2) the EXACT calculation formula with every symbol defined (units included) plus the data
inputs required, (3) typical parameter ranges and regime threshold bands — and label each
band as documented-with-citation or illustrative-example, (4) ONE concrete worked numerical
example per regime with every intermediate number shown (use small synthetic datasets, e.g.
a 10-day odd-lot trade count series for retail share; borrow fee 12% + utilization 93% +
short interest/ADV = 6 days for a squeeze-candidate scorecard; reported 24-h liquidations
of $480M vs a $90M 30-day median for a liquidation z-score — label it reported_* since
public aggregators are censored lower bounds; Fed funds futures implying 68% hike odds for
the R024 state machine; 2y=4.8%/10y=4.2% for the curve state; CPI actual 3.4% vs consensus
3.1% with trailing surprise sigma 0.2% for an inflation-surprise z-score; HY OAS 620 bps
with a +110 bps 20-day change for credit stress; DXY 50-day above 200-day at the 80th
percentile of its 5-year range). Show the final regime classification for each example.
Cite the source paper or data source for each formula.
```

### Q-RB3-2 — local M5 Max build + automated-loop detection spec
```
I have a Mac with Apple M5 Max and 128GB unified memory (sunk cost, already owned).
For computing all 10 regime indicators R021–R030: (1) what data feeds do I need — exact
product names (TAQ odd-lot flags, securities-lending vendor, crypto liquidation
aggregators, FRED series IDs for SOFR/OIS/DGS2/DGS10/HY OAS/DXY, Fed funds futures,
economic calendar + consensus vendor, central-bank meeting calendars), (2) expected
compute time for the daily refresh in Python+polars, (3) RAM and disk budgets,
(4) engineering hours for a correct causal pipeline, (5) buy-vs-build: name vendors with
INDICATIVE monthly pricing (mark as indicative) and give a build-vs-buy verdict for a
one-person research operation. THEN specify the automated detection loop: which software
agent computes each indicator and on what cadence, the independent verification step for
each (second estimator + agreement tolerance), and the fail-safes. Explicitly cover:
T+1/lagged data vintage tagging (COT, FINRA, Fed series), timestamp discipline on
release days (regime flips only AFTER the 8:30 ET print — no pre-print leakage),
and low-confidence tagging when the lending feed is absent (Reg SHO list fallback).
```

### Q-RB3-3 — efficacy impact (direction + mechanism) + documented evidence + failure modes
```
For each regime R021–R030: (1) HOW does it modulate signal/strategy efficacy — state the
DIRECTION explicitly (which strategy families improve, which die) and the MECHANISM
(e.g. "borrow fee above expected edge makes short P&L mechanically negative: P&L ≈
−return − fee − buy-in risk"; "HY OAS blowout kills high-beta equity mean-reversion via
the Merton channel — equity is a junior claim on deteriorating credit"),
(2) DOCUMENTED evidence with citations — before/after-cost labeling, markets and periods
studied (e.g. documented momentum-crash anatomy; documented 2022 stock/bond positive
correlation breaking 60/40; documented pre-FOMC drift), (3) WHEN the regime classification
itself fails — misclassification costs, slow-moving indicators misused as timing signals
(credit stress, curve inversion — Gate rejects day-trading off them), surprise-methodology
mining (weights fixed ex ante), (4) how these regimes COMPOUND jointly (e.g. hot inflation
surprise + inverted curve + wide HY OAS = one stagflationary state). End with an honest
bottom line per regime: trade trigger, sizing input, factor tilt, or stand-down flag.
```
