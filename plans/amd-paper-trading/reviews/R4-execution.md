# R4 — Execution practicality review (broker, data, fills, timeline)

Reviewer role: execution/broker red-team. Scope is deliberately narrow: only the
practicality of §6 (broker integration), the AMD data feed, paper-fill stamping
and reconciliation, rate limits/throttling, the IBKR TWS/gateway requirement,
order types per venue, validation gate 5 (1-share test orders), and the realism
of the days 1–2 broker/data timeline. Methodology, statistics, allocator math,
and dashboard work are reviewed elsewhere.

Verdict up front: the plan's broker/data timeline is the weakest part of an
otherwise solid plan. Alpaca paper in days 1–2 is realistic. IBKR paper in
days 1–2 is not — the gateway alone is a multi-day job on headless infra, and
it carries the only real safety risk in the whole build (live-account orders).
Recommendation: ship phase 1 on Alpaca paper only; move IBKR to phase 2.

## Numbered findings

### 1. [HIGH] IBKR paper in days 1–2 is unrealistic; the gateway is the long pole

**Flaw.** §6 lists "IBKR paper second (richer, but TWS/gateway + paper
credentials needed)" inside a 2-day broker/data window. In practice IBKR paper
requires a running TWS or IB Gateway on infrastructure the connector can reach,
with API enabled on a fixed port, the gateway logged specifically into the
*paper* account, and daily re-authentication (IB auto-logs the gateway off
every day). On a headless Linux VM that means Xvfb (or equivalent virtual
display), a supervisor keeping the gateway alive, scripted restart, and handling
IB's session resets — plus the first-time login, which for accounts with 2FA
(IB Key) cannot be completed headlessly at all and needs an interactive session.
None of this is in the plan, and each step has its own failure modes (stale
`.jts` lockfiles, API port conflicts after unclean restarts, gateway silently
sitting at the login screen). This is a 3–6 day job, not a subtask of days 1–2.

**Fix.** Split the venues: phase 1 = Alpaca paper only (REST + websockets, API
keys, no gateway — genuinely a half-day integration). Move IBKR paper to phase
2 with its own explicit work items: gateway host decision, Xvfb/supervisor
setup, paper-mode verification, daily re-auth handling, and a disconnect/
reconnect drill. Do not let IBKR gate the first paper trades.

### 2. [HIGH] No guard against the gateway sitting on the LIVE account

**Flaw.** The plan's #1 frozen decision is "paper only, no real-money path,"
but §6 contains no mechanism that enforces it. The classic IBKR day-1 failure:
the gateway is logged into the live account (same username/password as paper —
paper is just an account toggle), the connector connects happily, and every
"paper" order is real. Credentials-via-vault does not prevent this; it is a
session-state problem, not a secrets problem.

**Fix.** Hard safety interlock in the IBKR connector (phase 2): on connect,
query the gateway's managed accounts and refuse to start unless the account ID
exactly matches the expected `DU…` paper account and does *not* match any
`U…` live account. Log the account ID at every session start. Treat an
account-ID mismatch as a fatal startup error, not a warning. Separately: never
reuse the live API port/client-id conventions for paper; document both.

### 3. [HIGH] IBKR paper market data is typically delayed — the plan assumes REAL bars

**Flaw.** §3 shows "AMD market data (REAL-stamped bars)" feeding the loop, and
§6 positions IBKR as the second venue. IBKR paper accounts generally receive
*delayed* market data unless the linked live account carries paid real-time
subscriptions. A bar-close-driven loop built on the assumption of real-time
bars will silently compute signals on stale closes and stamp them REAL. For a
daily-bar system a 15-minute delay is mostly harmless at the daily close, but
it is fatal to the provenance invariant if undocumented, and it breaks any
intraday entry-gating that assumes fresh quotes.

**Fix.** Pin the feed decision explicitly: if IBKR is ever the bar source,
verify the data delay on paper *before* trusting a single bar, and stamp bars
with their actual delay (`REAL-DELAYED-15M`), not just REAL. Better: make
Alpaca the sole bar source in phase 1 (see finding 5) and keep IBKR purely as
an execution venue in phase 2.

### 4. [MED] Alpaca "free data" means IEX, not the consolidated tape

**Flaw.** §6 says "Alpaca paper first (simpler API, free data)." Alpaca's free
market-data plan serves the IEX feed only; full SIP consolidated data requires
a paid subscription. For AMD daily bars the difference is negligible, but
several surviving signals may use intraday volume/quote features (imbalance,
microprice-style inputs) where IEX-only prints diverge from consolidated
prints. The selection pipeline (Stage 1) will then score modules on IEX
history while any future SIP-based execution sees different inputs — a quiet
train/serve skew.

**Fix.** Decide and document now: (a) accept IEX-only and restrict Stage 0
applicability filtering to exclude SIP-dependent modules, or (b) pay for SIP
and use it in both backtest and live. Either is fine; mixing them is not. Stamp
bars with feed provenance (`REAL-IEX` vs `REAL-SIP`), and add a data-contract
test asserting the live feed's adjustment basis (splits/dividends) matches the
history used in Stage 1.

### 5. [MED] Reconciliation "every bar, mismatch → halt" will false-halt on Alpaca paper

**Flaw.** §6: "reconciliation loop matches broker-reported positions vs.
internal book every bar; mismatch → halt and alert." Alpaca paper updates
positions asynchronously after fills; polling immediately post-fill routinely
returns the pre-fill position. The first real trading bar will therefore
"detect" a mismatch that is just propagation lag, halt the loop, and page —
then do it again the next bar. A halt-on-first-mismatch policy converts normal
paper latency into a daily outage.

**Fix.** Reconcile against *broker-reported* positions as source of truth with
a grace window (e.g. re-check for up to N seconds/minutes before declaring
mismatch), and halt only on *persistent* mismatch across K consecutive bars.
Keep per-venue books — the same symbol held via Alpaca and IBKR must never be
netted into one position line, or cross-venue reconciliation becomes
meaningless.

### 6. [MED] Gate 5's "1-share test orders" prove almost nothing

**Flaw.** Validation gate 5: "Broker paper connectivity proven with 1-share
test orders on each venue." A 1-share market order on AMD proves: credentials
work, the network path works, the order schema is accepted. It does *not*
prove: fill behavior at real strategy sizes, short-sale handling, limit/stop
semantics per venue, extended-hours handling, position-reporting lag (finding
5), or rate-limit behavior under the loop's real request pattern. Worse, it is
unnecessarily timid — the entire point of paper trading is that size is free.
A gate that passes on 1-share orders can still fail on the first real bar.

**Fix.** Replace with a realistic connectivity drill: run the full loop in a
controlled live session (or a market-hours replay against the paper API) with
*strategy-sized* orders, and validate the complete path —
signal → allocation → order → fill → broker position → reconciliation →
dashboard. Also note the scheduling gotcha: 1-share (or any) `day` orders
placed outside market hours on Alpaca paper are rejected/cancelled, so a
weekend drill "fails" spuriously. Gate 5 must run during market hours.

### 7. [MED] Alpaca paper fills are unrealistically clean — size the expectations

**Flaw.** The plan correctly stamps fills PAPER, but nothing in §6 or §9
accounts for *how* clean Alpaca's paper simulator is: market orders fill at
the prevailing quote with no slippage model, no partial-fill realism, no
queue position, and no borrow-constraint simulation. For liquid AMD this is
acceptable, but any strategy whose edge depends on passive-fill rates or
short availability will look better on Alpaca paper than anywhere else. Paper
P&L "proves plumbing, not edge" (§9) is stated — but the plumbing being proved
is plumbing against a simulator that never says no.

**Fix.** Document Alpaca paper's fill semantics as an explicit assumption in
the plan (fill at quote, no slippage, no partials), and add a slippage haircut
in the *internal* P&L accounting (not the broker fills) so strategy
comparisons in Stage 1/2 aren't decided by simulator generosity. Revisit before
any phase-2 venue comparison.

### 8. [MED] Rate limits: Alpaca is fine, IBKR pacing violations disconnect you

**Flaw.** §9 notes "rate limits are stricter than they look — the connector
must throttle and queue," which is directionally right but venue-blind.
Alpaca's 200 req/min is generous for a bar-close-driven loop and hard to hit
accidentally. IBKR's limits are qualitatively different: ~50 messages/second
*and* historical-data pacing rules, where violations produce pacing-violation
errors and can get the client disconnected. The Stage-1 backfill (per-module
walk-forward on AMD intraday history) is exactly the workload that trips
IBKR pacing if history comes from IBKR.

**Fix.** Throttle/queue design must be per-venue with the actual numbers
documented and tested: Alpaca 200 req/min token bucket; IBKR ≤50 msg/s with
pacing-aware historical-data requests. Include a pacing-violation drill in the
IBKR phase-2 work (finding 1). Source Stage-1 history from a bulk provider
(Alpaca historical API with backfill throttling), not from paced IBKR
historical requests.

### 9. [MED] No venue capability matrix — "IBKR for order types Alpaca lacks" is ungrounded

**Flaw.** §6: "IBKR paper as second venue for strategies that need order types
Alpaca lacks." But no survivor strategy is known yet (Stage 4 hasn't run),
and Alpaca already supports market, limit, stop, stop-limit, trailing-stop,
and bracket (OTO/OCA-style) orders — which covers every order type a daily/
intraday swing system plausibly needs. There is currently no identified
strategy requiring an IBKR-only order type, which means IBKR's entire
operational cost (findings 1–3, 8) is being paid for a hypothetical.

**Fix.** Build the venue capability matrix *after* SURVIVORS.md is frozen:
list each survivor's required order types and TIFs, map to venue support, and
only then decide whether IBKR is needed at all. Default assumption until that
matrix exists: Alpaca paper covers 100% of phase-1 needs. Related: pin the
extended-hours policy now — AMD moves heavily pre/post market; if any strategy
emits on extended-hours bars, Alpaca extended-hours behavior on paper must be
verified before relying on it, otherwise the first pre-market signal breaks
the router on day 1.

### 10. [LOW] Feed liveness is assumed — websockets die silently

**Flaw.** The paper loop is bar-close driven and assumes fresh bars arrive.
Alpaca websocket streams disconnect (network blips, silent server-side drops),
and a loop that merely "waits for the next bar" will sit on stale data
indefinitely, computing signals on the last known bar and stamping them as
current.

**Fix.** Heartbeat/liveness monitor on the feed: if no bar/heartbeat arrives
within X× the expected interval, the loop pauses signal computation (no
stale-bar signals, no orders) and alerts. This is cheap and prevents the
most embarrassing day-1 failure mode: trading on yesterday's close because
the socket died at 2am.

### 11. [LOW] Session calendar and bar completeness are unspecified

**Flaw.** "Bar-close driven" (§3) assumes bars exist and are complete. The
plan never defines the session calendar (NYSE holidays, half-days) or what
constitutes a *complete* bar. Day-1 breakage candidates: the loop runs on a
market holiday and fires on empty bars; a half-day session produces a
short bar that intraday features misread; the first bar after a holiday
carries a multi-day gap that volatility estimators misread as a shock.

**Fix.** Pin the session calendar (NYSE, via exchange-calendars or equivalent)
and define bar-completeness rules (expected vs. received trades/quotes per
bar; skip-and-log incomplete bars, never compute on them). Add a gap-aware
rule for post-holiday bars in the volatility scaling (§5).

### 12. [LOW] 100-signal-per-bar compute cost is unmeasured

**Flaw.** The 250 plug-ins were built and tested individually; nothing has
measured running all 100 signal plug-ins against a single AMD bar in one
process. Fixture-style per-module code (pandas frames per signal, repeated
I/O-shaped helpers) can be surprisingly slow in aggregate. For daily bars this
almost certainly doesn't matter; for the intraday entry-gating path (§5) a
slow signal layer can miss the bar it was meant to gate.

**Fix.** Before the live loop: a perf smoke test — all 100 signal plug-ins on
one AMD daily bar and one intraday bar, timed, with a per-bar compute budget
(e.g. signals must complete in <10% of the shortest bar interval). Optimize
or prune the tail offenders; do not discover this at the first intraday bar.

## What will actually break on day 1 (condensed)

1. IBKR gateway logged into the live account instead of paper (safety —
   finding 2), or gateway not running at all on the headless VM (finding 1).
2. Bars assumed real-time that are actually delayed/IEX-only (findings 3, 4).
3. First fill → immediate reconcile → false mismatch → halt loop (finding 5).
4. A pre-market signal hits a router with no extended-hours policy (finding 9).
5. Gate-5 drill run on a weekend "fails" on order rejection (finding 6).

## Suggested re-scope of §8 (broker/data rows only)

| Days | Work |
|------|------|
| 1–2 | Alpaca paper connector + AMD data feed (Alpaca IEX or paid SIP — decide in finding 4) + feed liveness monitor (finding 10) |
| 2–5 | Orchestrator + allocator + risk layer (unchanged) |
| 5–8 | Selection pipeline on AMD history (unchanged), history sourced from Alpaca bulk API with throttled backfill (finding 8) |
| 8–10 | Validation gates with realistic-size drill (finding 6), grace-window reconciliation (finding 5), venue matrix after SURVIVORS.md (finding 9) |
| Phase 2 | IBKR paper: gateway on headless infra, account-ID interlock, pacing drill, delayed-data verification (findings 1, 2, 3, 8) |

Net effect on the 2-week timeline: achievable *if* IBKR moves to phase 2 and
Alpaca is the sole phase-1 venue. As written (both venues in days 1–2), the
broker/data work is underestimated by roughly 3–5 days, and it carries the
plan's only real safety risk.
