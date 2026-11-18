[![bounty](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/KIM7667/btc-race-bot-1444/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/KIM7667/btc-race-bot-1444/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)

# btc-race-bot-1444

A BTC trading bot for the make.fun competition
[btc-race-24h-20261118-1444](https://make.fun/bounty/btc-race-24h-20261118-1444):
race a BTC trading bot live for 24 hours, paper money, simulation only.

## Strategy

Range trading on 1-minute cbBTC closes, long only. The bot only trades
the edges of a range it has actually seen, never the noise in the middle:

- Range: highest and lowest closes of the last 120 bars (2 hours).
- Buy: close within 30 bps above the rolling low, at least 25 bps above
  it (the low held and price is bouncing), and the low was set at least
  30 bars ago (an established level, not a fresh dip still falling).
  Full equity, one position at a time.
- Sell: close within 30 bps below the rolling high, that high set at
  least 120 bars ago, or a 0.80% trailing stop off the peak position
  value, or a 1.50% hard stop under cost.

Pure Python standard library, deterministic (integer math on closes only).

## Dev window result (local replay, exact harness economics)

- Net PnL: **+$10.85** on $1,000 paper (gate needs > $0)
- Trades: 4
- Max drawdown: 1.41% (guardrail: <= 25%)
- Determinism: two runs produce byte-identical action logs

Parameters were tuned on this race's own frozen dev window (3,888
combinations swept); the winning setting sits in the middle of a
profitable plateau (neighbouring settings all land between +$9.68 and
+$10.85), not on a knife-edge fit. The dev window itself fell ~3%
from first to last close, so the profit came from trading the bounces,
not from holding.

## Grade locally

```sh
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot . --driver docker
```

`main.py` is the entrypoint; `vendor/makefun_bars.py` is the kit SDK
shim copied byte for byte.
