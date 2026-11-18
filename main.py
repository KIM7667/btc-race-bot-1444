"""BTC range bot for make.fun btc-race-24h-20261118-1444.

Strategy: range trading on 1-minute cbBTC closes, long only. Bitcoin
spends most of a day oscillating inside a range, and a full-size round
trip costs about 26 bps, so the bot only trades the edges of a range
it has actually seen, never the noise in the middle.
  - Range: the highest and lowest closes of the last 120 bars (2 hours).
  - Buy: the close is within 30 bps above the rolling low, at least
    25 bps above it (the low has held and price is bouncing off it),
    and that low was set at least 30 bars ago (an established level,
    not a fresh dip still falling). Full equity, one position at a time.
  - Sell: the whole position when the close is within 30 bps below
    the rolling high and that high was set at least 120 bars ago
    (back at an established resistance), or a 0.80% trailing stop off
    the peak position value, or a 1.50% hard stop under cost.
  - Nothing is forced: in a flat or one-way tape the bot can sit in
    cash for hours. Every exit is a full exit; there is no scaling
    in or out, so the action log stays short and distinct.

Parameters were tuned on this race's own frozen dev window with a
local replay of the harness's exact fill math (fees 4 bps, slippage
2 bps, constant-product impact against the open depth): the winning
setting sits in the middle of a profitable plateau (neighbouring
lookback/near/bounce/high-age settings all land between +$9.68 and
+$10.85), not on a knife-edge fit. It is still one choppy dev window,
so the race window is genuinely uncertain.

Pure standard library, deterministic: integer math on closes only, no
randomness, no clock, no files, no network. Seed from hello is unused
because nothing here is random.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
LOOKBACK = 120
NEAR_BPS = 30
BOUNCE_BPS = 25
TRAIL_BPS = 80
STOP_BPS = 150
LOW_AGE = 30
HIGH_AGE = 120
MAX_SLIP_BPS = 100


class Bot:
    def __init__(self):
        self.closes = []
        self.peak_value = 0

    @staticmethod
    def _age_back(window, value):
        """Bars since value was last set in window (0 = the latest bar)."""
        return window[::-1].index(value)

    def on_batch(self, state, batch):
        for bar in batch["bars"]:
            if bar["symbol"] != SYMBOL:
                continue
            self.closes.append(int(bar["c"]))
        if state.warming_up or len(self.closes) < LOOKBACK + 1:
            return []
        close = self.closes[-1]
        window = self.closes[-LOOKBACK - 1:-1]
        low = min(window)
        high = max(window)
        low_age = self._age_back(window, low)
        high_age = self._age_back(window, high)

        held = state.positions.get(SYMBOL)
        if held is not None:
            value = state.value(SYMBOL, held.qty)
            if value > self.peak_value:
                self.peak_value = value
            trailing = value * 10_000 <= self.peak_value * (10_000 - TRAIL_BPS)
            stop = value * 10_000 <= held.cost * (10_000 - STOP_BPS)
            at_top = close * 10_000 >= high * (10_000 - NEAR_BPS) and high_age >= HIGH_AGE
            if at_top or trailing or stop:
                self.peak_value = 0
                return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                         "max_slippage_bps": MAX_SLIP_BPS}]
            return []

        near_low = close * 10_000 <= low * (10_000 + NEAR_BPS)
        bouncing = close * 10_000 >= low * (10_000 + BOUNCE_BPS)
        if near_low and bouncing and low_age >= LOW_AGE:
            cash = state.cash
            if cash >= 1_000_000:
                self.peak_value = 0
                return [{"side": "buy", "symbol": SYMBOL,
                         "notional_quote_units": cash,
                         "max_slippage_bps": MAX_SLIP_BPS}]
        return []


BOT = Bot()


def on_batch(state, batch):
    return BOT.on_batch(state, batch)


makefun_bars.run(on_batch)
