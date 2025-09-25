We are building a backend in Python for a perp dex trading terminal for Vamient. This should allow for a trader to perform API trading across different perp dexes, starting with Hyperliquid, Lighter, Extended, EdgeX, Vest.

The backend should be highly modular and allows new perp dexes to be easily plugged in and supported when needed. There should be a standard list of functions supported, which directly integrated with the API or SDK of that perp dexes.

The backend should support user to trade with multiple different accounts on the same perp dex, or across different perp dexes.

There should be API exposed by the backend so the trading terminal can consume.