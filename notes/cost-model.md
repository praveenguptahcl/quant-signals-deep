# Local-Build Cost Model — Apple Mac, M5 Max, 128GB unified memory (v1)

**Purpose.** Single source of truth for every $/throughput/RAM/engineering-hour number used in
chapters S001–S100 and T001–T100. Workers: cite this file (e.g. `per notes/cost-model.md §3`)
instead of inventing numbers. All figures below are **planning assumptions for consistency** —
stated as `~` ranges, never as measured benchmarks of the reader's machine. Chapters must not
present them as lab measurements.

**Ground rules.**
- Hardware is **sunk**: assume the Mac is already owned (~$3,500–4,500 configured with 128GB;
  indicative). Marginal hardware cost per project = $0.
- Marginal operating cost ≈ electricity only (see §1) — effectively $0 for planning.
- Real project cost = **data subscriptions + engineering time**. Quote both, always.
- Every vendor price in every chapter is suffixed `indicative — verify before budgeting`.

---

## 1. Electricity & marginal operating cost

- Mac Studio-class machine under sustained load: ~60–140 W (planning assumption).
- Formula: `$/yr = watts × 24 × 365 / 1000 × $/kWh`.
- At 100 W average and $0.15/kWh: `100 × 24 × 365 / 1000 × 0.15 ≈ $131/yr` → **~$0.36/day**.
- Verdict for chapters: *"marginal compute cost ≈ $0; the machine's electricity is ~$100–180/yr
  if run 24/7 — negligible next to data and engineering costs."*

## 2. Throughput benchmarks (planning assumptions)

Use these unless a chapter measures otherwise (and says so):

| Operation | Assumed throughput | Notes |
|-----------|-------------------|-------|
| polars simple column ops (filter, groupby-agg) | ~10–50M rows/sec | Single-threaded-friendly; memory-bandwidth bound |
| polars complex (rolling joins, asof) | ~1–10M rows/sec | |
| numpy vectorized math | ~50–200M elements/sec | |
| Python pure event loop (per-tick Python) | ~100–500k events/sec | GIL-bound; fine for ≤20 symbols L1 |
| Rust event loop | ~5–50M events/sec | For full-depth / multi-symbol real-time |
| Parquet read (local NVMe) | ~1–3 GB/sec compressed | |
| sklearn/XGBoost train (1M rows × 50 feats) | ~1–10 min | Highly problem-dependent; state assumptions |
| M5 GPU (MLX/PyTorch MPS) inference, small transformer | ~1–50 ms/sequence | DeepLOB-class; batch for throughput |

**Per-symbol event-rate assumptions (US equities, liquid names):**
- L1 touch quote events: ~1–5k events/sec in busy periods, ~50–500/sec average over RTH.
- L2 full depth (MBP-10): ~10–50k events/sec busy for top names.
- Trades only: ~10–200/sec busy.
- 1-min bars, 500-symbol universe: 500 × 390 = 195k bars/day — trivial.

**Worked sizing example (chapters may copy):** 50 liquid symbols × 2k avg L1 events/sec =
100k events/sec → Python loop borderline, Rust comfortable; polars batch recompute every
minute easily handles it.

## 3. RAM footprint rules of thumb

- Raw: `bytes = rows × columns × 8` for float64. Parquet on disk ≈ 2–4× smaller than RAM.
- **Working budget: keep live working set < ~77GB (60% of 128GB)**; leave headroom for the OS,
  Python overhead (~2–3× for object-heavy frames — prefer polars/Arrow), and spikes.
- Rule-of-thumb table (cite this):

| Data | Granularity | 1 symbol-day | 500 symbols × 60 days |
|------|-------------|--------------|----------------------|
| L1 touch quotes (events) | ~1–10M events/day | ~0.5–4 GB RAM | **does not fit — sample or use bars** |
| L2 MBP-10 depth (events) | ~20–100M events/day | ~8–40 GB RAM | **does not fit — per-symbol daily files** |
| 1-min OHLCV bars | 390 bars/day | ~0.1 MB | ~12 MB — trivial |
| Daily OHLCV, 3000 stocks × 10y | — | — | ~60M rows ≈ 2–5 GB — fits |
| Options chain snapshot (SPX, full) | per snapshot | ~100–300 MB | 8 snapshots/day ≈ 1–2.5 GB/day |
| Pairwise distance matrix (2000²) | float32 | — | 16 GB — fits, compute in chunks |

- Verdict pattern for chapters: *"X fits comfortably / fits with care / does not fit — use
  per-symbol daily files + streaming"*, referencing the 77GB working budget.

## 4. Storage growth (planning)

| Feed | Per symbol-day (parquet) | 60-day note |
|------|--------------------------|-------------|
| L1 quotes+trades, liquid | ~2–8 GB | per-symbol files; 50 symbols ≈ 6–24 TB/yr — use sampling or bars for history |
| L2 MBP-10, liquid | ~10–40 GB | research-only; do not archive naively |
| 1-min bars, 500 symbols | ~50 MB total | ~3 GB / 60 days — archive freely |
| Daily bars, 3000 stocks | ~5 MB total | trivial |
| OPRA full chain snapshots | ~1–3 GB/day (SPX-like) | selective underlyings only |

## 5. Engineering-time bands (hours, one competent quant-dev)

| Tier | Scope | Band | $ at $150/hr loaded |
|------|-------|------|---------------------|
| **L** | 1-min/daily bar signals, bar clocks, labels (S021–S048, S083, S085/86/88) | **4–12 h** | $600–1,800 |
| **M** | L1 event pipelines, pairs screens, vol estimators, Kalman/HMM (S001–S020 ex-L2, S049–S070, S077–S079) | **20–60 h** | $3,000–9,000 |
| **M+** | Strategy harness around M-tier signals (execution sketch, cost model, risk) | **40–100 h** | $6,000–15,000 |
| **H** | L2/MBO, full OPRA analytics, PIN, licensed alt-data pipelines, DeepLOB training (S002, S005, S009, S071–S074, S082, G-family) | **60–200 h** | $9,000–30,000 |

Chapters: pick the band, justify placement in one line, convert to $ with the $150/hr rate
labeled `loaded-cost estimate`.

## 6. Vendor price bands (INDICATIVE — verify before budgeting)

Repeat per chapter as needed; always with the indicative disclaimer.

| Tier | Option | Indicative price | Covers |
|------|--------|-----------------|--------|
| Tier 0 | Stooq, Alpaca IEX, SEC EDGAR, Google Trends, FINRA short interest, exchange delayed quotes | ~$0 | Daily bars, attention proxies, borrow snapshots |
| Tier 1 | Polygon (Stocks Advanced), Alpaca SIP, Tiingo | ~$30–200/mo | 1-min/real-time SIP bars, corporate actions |
| Tier 1 | Cboe delayed options data | ~$0–50/mo | Coarse Greeks, straddle moves |
| Tier 2 | Databento Standard (pay-as-you-go + plan) | ~$200/mo + usage | Honest L1/L2 (MBP-1/10), futures, OPRA research, imbalance feeds |
| Tier 2 | Benzinga Pro / similar news | ~$100–200/mo | Machine-readable headlines (redistribution limits) |
| Tier 3 | LOBSTER (academic) | ~hundreds/yr academic | MBO/ITCH order-book replay |
| Tier 3 | OptionMetrics IvyDB | ~$thousands/yr academic; institutional $$$$ | Publication-quality options history |
| Tier 3 | RavenPack / Bloomberg-class news | $$$$ enterprise | Full licensed news + sentiment |
| Tier 3 | TAQ / full OPRA production | Institutional $$$$ | Production-grade tick/options |

**Crossover heuristics (for buy-vs-build verdicts):**
- **Build** when: data tier ≤ 2, eng tier ≤ M, and the edge needs custom parameters or
  microstructure honesty (you can't buy your own thresholds).
- **Buy** when: licensed redistribution data (news, full OPRA chain), MBO/ITCH depth history,
  or borrow/term-structure panels — building means re-licensing anyway.
- **Hybrid (common)**: buy the raw feed (Tier 1/2), build the analytics.

## 7. How chapters must use this file

1. S7/T5 sections cite section numbers (`cost-model §2/§3/§5`), not raw vibes.
2. Every $ figure = data subscription (indicative) + engineering band × $150/hr.
3. Throughput claims use §2 table values with `~`; if a chapter measured real numbers on the
   M5 Max, it says `measured on <date>` and keeps both.
4. The one-line verdict pattern: *"Feasible on the M5 Max (Tier M, ~40 h ≈ $6k eng + ~$200/mo
   data); bottleneck is X; breaks at Y symbols."*
