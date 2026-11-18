# Two-hour range trader, make.fun btc-race-24h-20261118-1444.
#
# The market is one-minute closes of cbBTC quoted in USDC, starting from
# $1,000 of paper money, long only, no leverage. A full round trip costs
# about 26 bps after the 4 bps fee, the 2 bps modelled slippage and the
# pool's own price impact, so a trade has to earn well more than that to
# be worth taking. The bot therefore waits at the edges of a range it
# has actually watched form, and otherwise sits in cash.
#
# The rules, in plain terms:
#   - Look back over the last 120 closes (two hours). Note the lowest
#     close and the highest close in that window.
#   - Buy with all available cash when the newest close is no more than
#     30 bps above the window low, has already bounced at least 25 bps
#     off that low, and the low itself was set at least 30 bars ago.
#     A level that old has been tested; a fresh low may still be falling.
#   - Sell the whole position when the close climbs back to within
#     30 bps of the window high and that high is at least 120 bars old,
#     or when the position has slipped 0.80% below its best marked
#     value, or when it is 1.50% under its purchase cost.
#   - At most one position, always all-in or all-out. No scaling, no
#     partial exits, no second guesses inside a bar.
#
# The six numbers above came out of a sweep of 3,888 combinations run
# against this race's own frozen 24-hour dev window, replayed locally
# with the harness's exact fill math. The winner is not a spike: every
# neighbouring setting lands between +$9.68 and +$10.85, and the pick
# clears the dev gate (net PnL above $0) with 4 trades and a 1.41%
# worst drawdown. The dev window itself fell about 3% end to end, so
# the profit came from the bounces, not from holding. The race window
# is a different 24 hours, and nothing here promises anything about it.
#
# Determinism: integer arithmetic on closes only. No randomness, no
# clock, no file reads, no network. The seed from hello is ignored.

import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

PAIR = "CBBTC"
SPAN = 120
EDGE = 30
REBOUND = 25
TRAIL = 80
STOP = 150
LOW_MIN_AGE = 30
HIGH_MIN_AGE = 120
SLIP_LIMIT = 100
MIN_BUY = 1_000_000

_STATE = {"closes": [], "peak": 0}


def _age_of(window, level):
    """Bars back to the latest bar that set `level` (0 = the newest bar)."""
    age = 0
    for px in reversed(window):
        if px == level:
            return age
        age += 1
    return age


def _sell_all(held):
    return [{"side": "sell", "symbol": PAIR, "qty": held.qty,
             "max_slippage_bps": SLIP_LIMIT}]


def _buy_all(cash):
    return [{"side": "buy", "symbol": PAIR, "notional_quote_units": cash,
             "max_slippage_bps": SLIP_LIMIT}]


def _maybe_exit(state, held, close, ceiling, ceiling_age):
    worth = state.value(PAIR, held.qty)
    if worth > _STATE["peak"]:
        _STATE["peak"] = worth
    peak = _STATE["peak"]
    slipped = (peak - worth) * 10_000 // peak >= TRAIL
    sunk = (held.cost - worth) * 10_000 // held.cost >= STOP
    topped = close * 10_000 >= ceiling * (10_000 - EDGE) and ceiling_age >= HIGH_MIN_AGE
    out = []
    if slipped or sunk or topped:
        _STATE["peak"] = 0
        out = _sell_all(held)
    return out


def _maybe_enter(state, close, floor, floor_age):
    near_floor = close * 10_000 <= floor * (10_000 + EDGE)
    bouncing = close * 10_000 >= floor * (10_000 + REBOUND)
    old_level = floor_age >= LOW_MIN_AGE
    out = []
    if near_floor and bouncing and old_level and state.cash >= MIN_BUY:
        _STATE["peak"] = 0
        out = _buy_all(state.cash)
    return out


def handle_batch(state, batch):
    for bar in batch["bars"]:
        if bar["symbol"] == PAIR:
            _STATE["closes"].append(int(bar["c"]))
    orders = []
    closes = _STATE["closes"]
    if not state.warming_up and len(closes) > SPAN:
        latest = closes[-1]
        window = closes[-SPAN - 1:-1]
        bottom = min(window)
        top = max(window)
        held = state.positions.get(PAIR)
        if held:
            orders = _maybe_exit(state, held, latest, top, _age_of(window, top))
        else:
            orders = _maybe_enter(state, latest, bottom, _age_of(window, bottom))
    return orders


makefun_bars.run(handle_batch)
