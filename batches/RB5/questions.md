# RB5 — Grok questions (regimes R041–R050)

- Batch: RB5 — Session/intraday + structural regimes (R041–R050)
- Bot: Grok (grok.com), signed in — record account + date + chat URL when answered
- Protocol: ask the three questions ONE AT A TIME in one chat, each only after the prior
  answer fully completes. Capture verbatim into `batches/RB5/grok-answers.md`.
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
R041 overnight-gap dominance regime · R042 time-of-day liquidity U-shape regime ·
R043 closing-auction imbalance regime · R044 market concentration regime (HHI) ·
R045 dispersion regime · R046 factor-crowding regime · R047 news-flow intensity/novelty
regime · R048 halt / limit-up-down proximity regime · R049 short-sale restriction regime ·
R050 cross-venue / SIP-vs-direct divergence regime

---

### Q-RB5-1 — definitions + exact formulas + worked numeric examples
```
For each of the 10 regimes R041–R050 above, give: (1) the PRECISE definition,
(2) the EXACT calculation formula with every symbol defined (units included) plus the data
inputs required, (3) typical parameter ranges and regime threshold bands — and label each
band as documented-with-citation or illustrative-example, (4) ONE concrete worked numerical
example per regime with every intermediate number shown (use small synthetic datasets, e.g.
a 10-day overnight-vs-intraday return panel for the variance decomposition ON_share;
a per-name 5-minute spread/volume seasonal profile marking the open/midday/close states;
an auction imbalance tape with ImbZ = +3.2 for the fade-vs-follow rule; top-10 index
weight 38% for the concentration state; a 10-name cross-sectional return panel for
dispersion; a momentum-factor vol at its 85th percentile with +2.2σ trailing return for
the crowding flag — cite Daniel & Moskowitz 2016 on momentum crashes; news intensity 4×
median with novelty 0.12 for the stale-news fade setup, using novelty = 1 − cos(embedding,
trailing-10-day centroid); LULD band distance 0.8σ for the stand-down flag; the −10%
Rule-201 SSR trigger arithmetic). For R050, explain precisely WHY a desk Mac without
colocation cannot measure SIP-vs-direct divergence, and what the honest labeling must be
for any latency-sensitive backtest run on SIP data. Show the final regime classification
for each example. Cite the source paper or data source for each formula.
```

### Q-RB5-2 — local M5 Max build + automated-loop detection spec
```
I have a Mac with Apple M5 Max and 128GB unified memory (sunk cost, already owned).
For computing all 10 regime indicators R041–R050: (1) what data feeds do I need — exact
product names (corporate-action-adjusted daily bars vendor, TAQ for imbalance messages and
odd-lots, index weight files, factor library, news API vendor, SIP halt messages,
exchange status pages, Reg SHO list), (2) expected compute time for the daily refresh in
Python+polars, (3) RAM and disk budgets, (4) engineering hours for a correct causal
pipeline, (5) buy-vs-build: name vendors with INDICATIVE monthly pricing (mark as
indicative) and give a build-vs-buy verdict for a one-person research operation.
THEN specify the automated detection loop: which software agent computes each indicator
and on what cadence, the independent verification step for each (second estimator +
agreement tolerance), and the fail-safes. Explicitly cover: corporate-action adjustment
BEFORE any variance decomposition (Adversary injects an unadjusted split), as-of index
membership (no survivorship bias in dispersion), halt-message parse failures (fail-safe:
assume halted — never trade through), R050 as a CAPABILITY gate (no colocation box → the
state is permanently UNKNOWN and every latency-sensitive chapter carries the
"simulated only — requires MBO/ITCH" label), and separate seasonal profiles for half-days.
```

### Q-RB5-3 — efficacy impact (direction + mechanism) + documented evidence + failure modes
```
For each regime R041–R050: (1) HOW does it modulate signal/strategy efficacy — state the
DIRECTION explicitly (which strategy families improve, which die) and the MECHANISM
(e.g. "on overnight-dominated names the backtest's close-to-close returns include gaps the
intraday strategy never traded — return-attribution mismatch"; "open-session signals are
gross-strong but net-weak: edge minus 2–3× midday spreads"; "positive-GEX pinning means
dealer hedging trades against moves — free reversion flow; negative GEX means hedging
chases moves — fades get run over"; "pair P&L is proportional to idiosyncratic vol, so
low dispersion starves pairs"),
(2) DOCUMENTED evidence with citations — before/after-cost labeling, markets and periods
studied, (3) WHEN the regime classification itself fails — misclassification costs,
structural breaks that invalidate historical thresholds (0DTE diluting OpEx pinning;
tick-rule definition changes; retail composition shifts), slow-moving structural regimes
misused as timing signals (concentration, factor crowding — Gate rejects intraday triggers
off them), (4) how these regimes COMPOUND jointly, and the annotation discipline for the
200 existing chapters: at most 6 regimes per chapter ordered by impact, most-specific
regime preferred, every line states direction explicitly. End with an honest bottom line
per regime: trade trigger, sizing input, factor tilt, or stand-down flag.
```
