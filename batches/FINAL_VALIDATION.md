# FINAL INTEGRITY VALIDATION — MASTER.md (Part II)

**File validated:** `~/workspace/quant-signals-deep/MASTER.md`
**Size:** 36,207 lines
**Validation date:** 2026-09-10
**Method:** grep / Python scanning. MASTER.md was **not edited** — this report is read-only output.
**Verdict: NOT READY FOR DELIVERY**

---

## Verdict rationale

One BLOCKER, 54 MAJOR violations, and one MINOR defect were confirmed. All checks below report exact counts.

| # | Check | Result | Count |
|---|-------|--------|-------|
| 1 | TOC anchors resolve | ✅ PASS | 200/200 resolve, 0 broken |
| 2 | Cross-references (S###/T###) | ✅ PASS | 5,139 occurrences, 0 dangling |
| 3 | Chatbot-only evidence sections | ✅ PASS | 200 sections, 0 violations |
| 4 | Same-bar execution / lookahead | ✅ PASS | 17 flagged matches reviewed, 0 violations |
| 5 | Vendor-price disclaimer suffix | ❌ FAIL | **54 violations** (30 comma-variant + 24 uncovered) |
| 6 | Citation spot-check (20 identifiers) | ✅ PASS | 20/20 verified live, real, title-matched |
| 7 | Formula delimiter sanity | ⚠️ MINOR | 1 malformed inline-math delimiter |
| 8 | Stage numbers/order | ❌ **BLOCKER** | stages do **not** run 1–200 in document order |
| 9 | Placeholder tokens | ✅ PASS | 0 TODO/FIXME/XXX/TBD/CHAPTER-DEFERRED |

---

## BLOCKER

### B-1 — Stage headings do not run 1–200 in document order

200 stage headings found; no missing numbers, no duplicates, and every stage→chapter-ID mapping is correct (S001–S100 → Stages 1–100; T001–T100 → Stages 101–200). **But the signal half is ordered by research-batch merge order, not numerically.** There are **9 backward jumps** (out of 199 transitions); the strategy half (Stages 101–200) is correctly ordered throughout.

Evidence (all signal half; chapter, document order):

| Transition | Line | From | Line | To |
|---|---|---|---|---|
| 1 | 2696 | Stage 40 (S040) | 2899 | Stage 11 (S011) |
| 2 | 4654 | Stage 83 (S083) | 4843 | Stage 49 (S049) |
| 3 | 6533 | Stage 94 (S094) | 6710 | Stage 2 (S002) |
| 4 | 8406 | Stage 47 (S047) | 8603 | Stage 22 (S022) |
| 5 | 10250 | Stage 45 (S045) | 10450 | Stage 34 (S034) |
| 6 | 12031 | Stage 60 (S060) | 12224 | Stage 51 (S051) |
| 7 | 14135 | Stage 90 (S090) | 14425 | Stage 64 (S064) |
| 8 | 16506 | Stage 74 (S074) | 16690 | Stage 16 (S016) |
| 9 | 18334 | Stage 89 (S089) | 18506 | Stage 9 (S009) |

The document begins `Stage 1, 3, 4, 6, 8, 14, 24, …` (lines 463–2062). Fix: reorder signal chapters into ascending stage order (or renumber/re-issue TOC) before delivery.

---

## MAJOR findings — vendor-price disclaimer suffix

Required exact suffix on every vendor-price mention: `indicative — verify before budgeting`.
Exact-suffix instances present: **522**. Violations: **54**.

### M-1 — Punctuation variant: `indicative, verify before budgeting` (30 lines)

Comma substituted for the required em dash — not the exact suffix. All 30 are vendor-price table cells:

- S001: 602, 603, 604, 605 (4)
- S003: 797, 798, 799 (3)
- S004: 1064, 1065, 1066 (3)
- S031: 9810, 9811, 9812, 9813 (4)
- S033: 10000, 10001, 10002, 10003 (4)
- S044: 10193, 10194, 10195, 10196 (4)
- S045: 10393, 10394, 10395, 10396 (4)
- S070: 15905 (1)
- S100: 20255, 20257, 20332 (3)

Example (S001, line 603): `| Tier 1: Polygon Stocks Advanced / Alpaca SIP | real-time SIP L1, history | ~$30–200/mo — *indicative, verify before budgeting* |`
Example (S100, line 20257): `| Intraday bars | 1-minute | matches events | Databento (~$200/mo + usage); LOBSTER (hundreds/yr) — indicative, verify before budgeting |`

### M-2 — Vendor-price lines with neither per-line nor blanket disclaimer (24 lines)

| Chapter | Lines |
|---|---|
| S054 | 12943, 12944 |
| S055 | 13145, 13146 |
| S057 | 13337 |
| S058 | 13529 |
| S064 | 14660, 14661 |
| S065 | 14985, 14987 |
| S067 | 15302 |
| S078 | 17567, 17568 |
| S080 | 17749, 17750 |
| S082 | 17920 |
| S097 | 19752, 19755 |
| S098 | 19916 |
| S099 | 20086 |
| S100 | 20273, 20275 |
| T001 | 20455 |
| T008 | 21562 |

Representative evidence:
- S054 L12943: `| Tier-1 retail (Polygon Stocks Advanced) | Clean SIP daily/1-min bars + corp actions | ~$30–200/mo | Reliable adjustmen…` — no disclaimer anywhere on the line or chapter-level blanket covering it.
- T001 L20455: `Databento live MBP-1 (or TotalView MBO) on 5–10 symbols at ~$2k–6k/mo all-in is the honest Phase-1 spend…` — prose price mention with no disclaimer.
- T008 L21562: `40–100 h ≈ $6,000–15,000 eng (loaded-cost e…` — no disclaimer.

---

## MINOR findings

### m-1 — Malformed inline-math delimiter (S017, line 7996)

`near-critical branching ($n \to 1\));` — closes inline math with `\)` but opens with a plain `(` instead of `\(`. Global `\(`/`\)` parity confirms this is the sole orphan: 5 opens vs 6 closes. Renders literally as `\)` in most Markdown renderers.

---

## Detailed check results

### 1. TOC anchors — 200/200 resolve, 0 broken
All 200 Markdown TOC anchor links were generated and matched against GitHub heading slugs. Initial pass reported 200 broken due to a validator bug (collapsing consecutive spaces); corrected validator confirms GitHub converts each space to a hyphen separately, preserving double hyphens after removed punctuation. **0 broken.**

### 2. Cross-references — 5,139 occurrences, 0 dangling
Every `S###`/`T###` reference resolves to an existing chapter heading. No dangling references.

### 3. Chatbot-only evidence — 200 sections, 0 violations
All 200 S9/T7-style evidence tables scanned: none has every substantive row drawn only from Grok/chatbot/research-note material. Published evidence appears in all tables; a few tables also carry explicitly labeled chatbot "leads" rows alongside published sources — those are not violations.

### 4. Same-bar execution — 17 flagged matches reviewed, 0 violations
Loose regex hits on "same bar" were all hand-reviewed. The only strict hit (T094, line 35240) is a **false positive**: it describes same-bar filling as a *lookahead error* and explicitly requires `t+1`. Other reviewed cases are compliant, e.g.:
- T004 L20885 — signal calculated at close of `t`, eligible at open of `t+1`
- T049 L28434 — confirmations occur on the same signal bar; trade waits for a later pullback bar
- T072 L31910 — same-bar feature confirmation, explicitly fills at `t+1`
- T081 L33056, T091 L34636, T093 L34973 — explicitly prohibit same-bar fills

### 5. Vendor-price disclaimer — see MAJOR findings above
- Exact suffix instances: 522
- Comma-variant violations: 30 (in price lines)
- Uncovered vendor-price lines: 24
- Blanket-sentence coverage exists in some chapters (e.g. S006 L1343, "all prices are indicative") but the required rule is the exact per-mention suffix, so blanket coverage is noted but not credited.

### 6. Citation spot-check — 20/20 verified live ✅

Sample drawn programmatically from the S12 and T10 evidence sections (one identifier per chapter's evidence table): **16 from signal chapters, 4 from strategy chapters**. Each identifier was opened and its title/authorship/publication checked against the citation text. All 20 are real, live, and match.

| # | Chapter | Identifier | Verified result |
|---|---|---|---|
| 1 | S014 | arXiv:1907.06230 | *Multi-Level Order-Flow Imbalance in a Limit Order Book* — match |
| 2 | S001 | DOI 10.1111/1468-0262.00418 | *Modeling and Forecasting Realized Volatility* — match |
| 3 | S013 | DOI 10.1016/0304-405X(93)90029-B | *Stealth trading and volatility: Which trades move prices?* — match (bibliographic search; publisher page had no extractable text) |
| 4 | S028 | arXiv:0808.1710 | *Dynamic modeling of mean-reverting spreads for statistical arbitrage* — match |
| 5 | S039 | arXiv:1802.01921 | *Dynamical regularities of US equities opening and closing auctions* — match |
| 6 | S044 | arXiv:2112.13213 | *Cross-Impact of Order Flow Imbalance in Equity Markets* — match |
| 7 | S048 | DOI 10.1093/rfs/hhq141 | *All the News That's Fit to Reprint: Do Investors React to Stale Information?* — match |
| 8 | S050 | DOI 10.1111/j.1540-6261.1991.tb03749.x | Hasbrouck, *Measuring the Information Content of Stock Trades* — match |
| 9 | S058 | DOI 10.1111/j.1540-6261.2009.01447.x | DellaVigna & Pollet Friday-announcement paper — title and cited result confirmed via search |
| 10 | S065 | arXiv:1011.6402 | *The Price Impact of Order Book Events* — match |
| 11 | S066 | DOI 10.1093/rfs/hhy083 | *Information, Trading, and Volatility: Evidence from Firm-Specific News* — match |
| 12 | S070 | DOI 10.1111/j.1540-6261.2010.01573.x | *Intraday Patterns in the Cross-Section of Stock Returns* — match |
| 13 | S073 | DOI 10.1016/0165-1889(88)90041-3 | Johansen, *Statistical analysis of cointegration vectors* — match |
| 14 | S073 | DOI 10.1111/j.1540-6261.1988.tb02591.x | Berkowitz, Logue & Noser, *The Total Cost of Transactions on the NYSE* — match |
| 15 | S082 | arXiv:2506.05764 | *Exploring Microstructural Dynamics in Cryptocurrency Limit Order Books* — match |
| 16 | S083 | arXiv:2102.04591 | *Liquidation, Leverage and Optimal Margin in Bitcoin Futures Markets* — match |
| 17 | T054 | SSRN 2460551 | Bailey & López de Prado, *The Deflated Sharpe Ratio* (JPM 40(5), 94–107, 2014) — match |
| 18 | T061 | SSRN 4416622 | Zarattini & Aziz, *Can Day Trading Really Be Profitable?* (ORB on QQQ 2016–2023, net of commissions) — match |
| 19 | T018 | SSRN 3461283 | Plastun, Sibande, Gupta & Wohar, *Price Gap Anomaly in the US Stock Market: The Whole Story* — match |
| 20 | T091 | NBER w16884 | Martin, *Simple Variance Swaps* (March 2011) — match |

### 7. Formula sanity — 1 MINOR (see m-1)
Fence-aware scan (code fences excluded): 551 `$$` tokens. All unpaired instances examined individually — every one is **dollar-tier shorthand in S8/T6 buy/build price tables** (`$$`, `$$$`, `$$$$` meaning price tiers, e.g. S035 L2635, T092 L34888, T099 L35994), or a properly opened/closed multiline display block (S006 L1178–1179; S035 L2527–2529). No genuinely unclosed `$$` display block exists. The sole real defect is the S017 L7996 `\(` / `\)` mismatch.

### 8. Stage numbers/order — BLOCKER (see B-1)
200 stage headings; no missing numbers, no duplicates, all stage→ID mappings correct; 61 transitions where the next stage number is not previous+1, of which 9 are backward jumps in the signal half.

### 9. Placeholders — 0
No `TODO`, `FIXME`, `XXX`, `TBD`, or `CHAPTER-DEFERRED` anywhere in the file.

---

## False positives explicitly reviewed and rejected

1. **TOC validator space-collapsing bug** — initial 200-broken result was a slug-generation error in the validator, not in MASTER.md. Corrected: 0 broken.
2. **T094 L35240 "same bar"** — describes same-bar filling as a lookahead error; compliant.
3. **`$$$$` / `$$$` / `$$` in buy/build price tables** (S8/T6) — dollar-tier shorthand, not broken display math. Affects ~12 unpaired-`$$` flags including S006 L1341, S014 L1968, S035 L2635, S038 L11095, S041 L11449, S080 L17751, T009 L21726, T039 L26772, T092 L34888, T093 L35057, T095 L35377, T099 L35994.
4. **Multiline `$$ … $$` display blocks** (e.g. S006 L1178–1179, S035 L2527–2529) — properly closed; line-level scanners report them falsely.
5. **S058 L13528** — contains the exact suffix (`Indicative — verify before budgeting`, sentence-case at cell start); compliant.
6. **T016 L22944 / T017 L23091** — contain `indicative, verify before budgeting` but in "Unverified leads" research-note context, not vendor-price mentions; not applicable to the disclaimer rule.
7. **Blanket disclaimer sentences** (e.g. S006 L1343) — noted but not credited against the per-mention rule.
8. **Chatbot "Unverified leads" rows** in evidence tables — always accompanied by published sources; not chatbot-only.

---

## Summary of required fixes before delivery

1. **BLOCKER:** Reorder signal chapters so stages run 1–200 in document order (9 backward jumps in Stages 1–100; see table in B-1).
2. **MAJOR:** Normalize 30 comma-variant disclaimers to the exact suffix `indicative — verify before budgeting` (lines listed in M-1).
3. **MAJOR:** Add the exact suffix to 24 uncovered vendor-price mentions (lines listed in M-2).
4. **MINOR:** Fix S017 L7996 inline math: `($n \to 1\))` → `\($n \to 1\)`.

Supporting artifacts: `batches/validate_final.py`, `batches/validation_results.json` (intermediate tooling; not user-facing).
