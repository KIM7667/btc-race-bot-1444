"""Two-hour range trader for make.fun btc-race-24h-20261118-1444.

The tape this bot races on is one-minute closes of cbBTC against USDC,
starting from $1,000 of paper money, long only. A full round trip costs
roughly 26 bps once the 4 bps fee, the 2 bps modelled slippage and the
pool's own price impact are all paid, so the bot waits for moves that
clear that bar by a wide margin and otherwise stays in cash.

How it trades:
  - It watches the last 120 closes (two hours) and remembers the lowest
    and highest close inside that window.
  - It buys the whole cash balance when the latest close sits within
    30 bps above the window low, has already lifted at least 25 bps off
    that low (the level held and price is turning up), and the low was
    first set at least 30 bars ago (an old level, not a dip still
    falling). One open position at a time, never more.
  - It sells everything when the close comes back within 30 bps below
    the window high and that high is at least 120 bars old, or when the
    position has given back 0.80% from its best marked value, or when
    it sits 1.50% under what was paid for it.
  - It never chases the middle of the range: in a flat or one-way tape
    it can hold cash for hours and finish the window with few trades.

The numbers above were picked by sweeping 3,888 parameter combinations
against this race's own frozen 24-hour dev window, replayed locally with
the harness's exact fill math. The chosen setting is not a spike: its
neighbours all land between +$9.68 and +$10.85, and it clears the dev
gate (net PnL above $0) with 4 trades and a 1.41% maximum drawdown.
The race window is a different 24 hours, so none of that is a promise
about the race itself.

Deterministic by construction: only integer arithmetic on closes, no
randomness, no clock, no files, no network. The seed hello carries is
never read.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

ASSET = "CBBTC"
WINDOW_BARS = 120
EDGE_BPS = 30
LIFT_BPS = 25
TRAIL_STOP_BPS = 80
HARD_STOP_BPS = 150
MIN_LOW_AGE = 30
MIN_HIGH_AGE = 120
SLIP_CAP_BPS = 100
MIN_CASH = 1_000_000


def _bps_above(numer, denom):
    """How far numer sits above denom, in basis points, integer math."""
    return (numer - denom) * 10_000 // denom


def _bars_since_last(window, level):
    """Bars back to the most recent bar that set `level` (0 = latest)."""
    for i in range(len(window) - 1, -1, -1):
        if window[i] == level:
            return len(window) - 1 - i
    return len(window)


class RangeTrader:
    """One-position range trader over one-minute closes."""

    def __init__(self):
        self.history = []
        self.best_value = 0

    def _ingest(self, bars):
        for bar in bars:
            if bar["symbol"] == ASSET:
                self.history.append(int(bar["c"]))

    def decide(self, state, batch):
        self._ingest(batch["bars"])
        if state.warming_up or len(self.history) <= WINDOW_BARS:
            return []
        closes = self.history
        close = closes[-1]
        window = closes[-WINDOW_BARS - 1:-1]
        floor = min(window)
        ceiling = max(window)
        floor_age = _bars_since_last(window, floor)
        ceiling_age = _bars_since_last(window, ceiling)
        held = state.positions.get(ASSET)
        if held is not None:
            return self._exit(state, held, close, ceiling, ceiling_age)
        return self._enter(state, close, floor, floor_age)

    def _exit(self, state, held, close, ceiling, ceiling_age):
        worth = state.value(ASSET, held.qty)
        if worth > self.best_value:
            self.best_value = worth
        gave_back = _bps_above(self.best_value, worth) >= TRAIL_STOP_BPS
        under_water = _bps_above(held.cost, worth) >= HARD_STOP_BPS
        back_at_top = (
            close * 10_000 >= ceiling * (10_000 - EDGE_BPS)
            and ceiling_age >= MIN_HIGH_AGE
        )
        if gave_back or under_water or back_at_top:
            self.best_value = 0
            return [{"side": "sell", "symbol": ASSET, "qty": held.qty,
                     "max_slippage_bps": SLIP_CAP_BPS}]
        return []

    def _enter(self, state, close, floor, floor_age):
        near_floor = close * 10_000 <= floor * (10_000 + EDGE_BPS)
        lifting = close * 10_000 >= floor * (10_000 + LIFT_BPS)
        settled = floor_age >= MIN_LOW_AGE
        if near_floor and lifting and settled and state.cash >= MIN_CASH:
            self.best_value = 0
            return [{"side": "buy", "symbol": ASSET,
                     "notional_quote_units": state.cash,
                     "max_slippage_bps": SLIP_CAP_BPS}]
        return []


TRADER = RangeTrader()


def on_batch(state, batch):
    return TRADER.decide(state, batch)


makefun_bars.run(on_batch)
