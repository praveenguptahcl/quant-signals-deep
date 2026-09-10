# RB2 — Grok questions (regimes R011–R020)

- Batch: RB2 — Liquidity/microstructure + funding/positioning (R011–R020)
- Bot: Grok (grok.com), signed in — record account + date + chat URL when answered
- Protocol: ask the three questions ONE AT A TIME in one chat, each only after the prior
  answer fully completes. Capture verbatim into `batches/RB2/grok-answers.md`.
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
R011 depth / liquidity-provision regime (book depth, Kyle's lambda) ·
R012 price-impact / Amihud illiquidity regime · R013 abnormal volume / participation regime ·
R014 informed-flow toxicity (VPIN) regime · R015 tick-constraint regime ·
R016 fragmentation / off-exchange share regime · R017 funding-stress regime (SOFR-OIS) ·
R018 equity positioning / crowding regime · R019 crypto funding-rate regime ·
R020 options gamma positioning (GEX) regime

---

### Q-RB2-1 — definitions + exact formulas + worked numeric examples
```
For each of the 10 regimes R011–R020 above, give: (1) the PRECISE definition,
(2) the EXACT calculation formula with every symbol defined (units included) plus the data
inputs required, (3) typical parameter ranges and regime threshold bands — and label each
band as documented-with-citation or illustrative-example, (4) ONE concrete worked numerical
example per regime with every intermediate number shown (use small synthetic datasets, e.g.
a 10-bar signed-volume series for a Kyle's-lambda OLS regression; 10 days of |return| and
dollar volume for Amihud; a 6-bucket volume tape for VPIN with bulk volume classification;
a 10-quote tape for tick-bind fraction; 8-hour funding rates 0.020%/0.015%/0.025% on
$10,000 notional for the funding-rate annualization; a 5-strike option chain with gamma×OI
for a GEX-proxy computation — and note explicitly that the GEX proxy assumes dealer
positioning and requires full-chain OI, it never reveals actual positioning). Show the
final regime classification for each example. Cite the source paper for each formula.
```

### Q-RB2-2 — local M5 Max build + automated-loop detection spec
```
I have a Mac with Apple M5 Max and 128GB unified memory (sunk cost, already owned).
For computing all 10 regime indicators R011–R020 over a 500-stock US universe + BTC/ETH:
(1) what data feeds do I need — exact product names (e.g. Databento MBP-1 for depth,
TAQ for odd-lots, FINRA ATS weekly files, NY Fed/FRED for funding, CBOE put/call,
crypto funding APIs, full-chain options OI vendor), (2) expected compute time for the
daily refresh in Python+polars, (3) RAM and disk budgets, (4) engineering hours for a
correct causal pipeline, (5) buy-vs-build: name vendors with INDICATIVE monthly pricing
(mark as indicative) and give a build-vs-buy verdict for a one-person research operation.
THEN specify the automated detection loop: which software agent computes each indicator
and on what cadence, the independent verification step for each (second estimator +
agreement tolerance), and the fail-safes. Explicitly cover: L1/L2 unavailable (no SIP-only
depth inference), FINRA data staleness (~2 weeks lag — vintage tagging), crypto exchange
API outages, and single-name GEX with fewer than 5 liquid strikes.
```

### Q-RB2-3 — efficacy impact (direction + mechanism) + documented evidence + failure modes
```
For each regime R011–R020: (1) HOW does it modulate signal/strategy efficacy — state the
DIRECTION explicitly (which strategy families improve, which die) and the MECHANISM
(e.g. "VPIN > 0.7 means adverse selection spikes; passive-fill market-making expected
P&L turns negative as spreads run 2–3x normal" — cite Easley, Lopez de Prado & O'Hara 2012),
(2) DOCUMENTED evidence with citations — before/after-cost labeling, markets and periods
studied (e.g. the documented 2010 flash-crash VPIN precedent; documented momentum-crash
anatomy for crowding), (3) WHEN the regime classification itself fails — misclassification
costs, lookahead traps, estimator disagreement, censored-data traps (public crypto
liquidation/funding aggregators are lower bounds — use reported_* labeling),
(4) how these regimes COMPOUND jointly. End with an honest bottom line per regime:
trade trigger, sizing input, or stand-down flag.
```
