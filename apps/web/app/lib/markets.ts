import type { InstrumentInfo } from "./api";

export const DEFAULT_SYMBOL = "EUR/USD";
export const DEFAULT_TIMEFRAME = "1h";

const MARKET_LABELS: Record<string, string> = {
  forex: "Forex",
  commodities: "Commodities",
  crypto: "Crypto",
  indices: "Indices",
  stocks: "Stocks",
  synthetic: "Synthetic indices",
};

export function marketLabel(market: string): string {
  return MARKET_LABELS[market] ?? market;
}

export function marketsOf(instruments: InstrumentInfo[]): string[] {
  return Array.from(new Set(instruments.map((i) => i.market)));
}

export function resolveInstrument(
  instruments: InstrumentInfo[],
  choice: string | null,
): InstrumentInfo | null {
  return (
    instruments.find((i) => i.symbol === choice) ??
    instruments.find((i) => i.symbol === DEFAULT_SYMBOL) ??
    instruments[0] ??
    null
  );
}

export function firstInMarket(
  instruments: InstrumentInfo[],
  market: string,
): string | null {
  const inMarket = instruments.filter((i) => i.market === market);
  return (
    (inMarket.find((i) => i.symbol === DEFAULT_SYMBOL) ?? inMarket[0])?.symbol ??
    null
  );
}

export function resolveTimeframe(
  timeframes: string[],
  choice: string | null,
): string | null {
  if (choice && timeframes.includes(choice)) return choice;
  return timeframes.includes(DEFAULT_TIMEFRAME)
    ? DEFAULT_TIMEFRAME
    : (timeframes[0] ?? null);
}
