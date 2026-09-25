"use client";

import { RefreshCw, Search } from "lucide-react";
import { useEffect, useState } from "react";

import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Message from "../../components/ui/Message";
import { Select } from "../../components/ui/Select";
import {
  ApiError,
  getCatalog,
  getLiveState,
  scanMarket,
  type Catalog,
  type ScannerLiveState,
  type ScannerSignal,
} from "../../lib/api";

const STRATEGIES = [
  { value: "trend_continuation", label: "Trend Continuation" },
  { value: "break_and_retest", label: "Break & Retest" },
  { value: "liquidity_sweep", label: "Liquidity Sweep" },
];

const STRATEGY_LABELS: Record<string, string> = Object.fromEntries(
  STRATEGIES.map((s) => [s.value, s.label]),
);

const SCOPE_TONE: Record<string, "accent" | "neutral"> = {
  external: "accent",
  internal: "neutral",
};

function describe(err: unknown): string {
  return err instanceof ApiError
    ? err.message
    : "Could not reach the server. Is the API running?";
}

function formatPrice(value: number): string {
  return value.toLocaleString(undefined, {
    maximumFractionDigits: value < 10 ? 4 : 2,
  });
}

function stateLabel(state: string): string {
  return state
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export default function ScannerPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [strategies, setStrategies] = useState<string[]>(
    STRATEGIES.map((s) => s.value),
  );

  const [scanning, setScanning] = useState(false);
  const [signals, setSignals] = useState<ScannerSignal[] | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  const [liveStates, setLiveStates] = useState<
    Record<string, ScannerLiveState | null>
  >({});


  useEffect(() => {
    if (strategies.length === 0) return undefined;
    let cancelled = false;

    async function poll() {
      const entries = await Promise.all(
        strategies.map(async (strategy) => {
          try {
            const state = await getLiveState(symbol, timeframe, strategy);
            return [strategy, state] as const;
          } catch {
            return [strategy, null] as const;
          }
        }),
      );
      if (!cancelled) {
        setLiveStates(Object.fromEntries(entries));
      }
    }

    poll();
    const interval = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [symbol, timeframe, strategies]);

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((result) => {
        if (!cancelled) setCatalog(result);
      })
      .catch((err) => {
        if (!cancelled) setCatalogError(describe(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function toggleStrategy(value: string) {
    setStrategies((current) =>
      current.includes(value)
        ? current.filter((s) => s !== value)
        : [...current, value],
    );
  }

  async function runScan() {
    if (strategies.length === 0) return;
    setScanning(true);
    setScanError(null);
    try {
      const result = await scanMarket(symbol, timeframe, strategies);
      setSignals(result.signals);

      const states: Record<string, ScannerLiveState | null> = {};
      await Promise.all(
        strategies.map(async (strategy) => {
          states[strategy] = await getLiveState(symbol, timeframe, strategy);
        }),
      );
      setLiveStates(states);
    } catch (err) {
      setScanError(describe(err));
      setSignals(null);
    } finally {
      setScanning(false);
    }
  }

  const instruments = catalog?.instruments ?? [{ symbol, market: "crypto" }];
  const timeframes = catalog?.timeframes ?? [timeframe];

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold">Scanner</h1>
      <p className="mt-1 text-sm text-muted">
        Pick a market, timeframe and strategies, and scan for valid setups.
      </p>

      {catalogError && (
        <Message kind="error" className="mt-4">
          {catalogError}
        </Message>
      )}

      <Card className="mt-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Instrument</span>
            <Select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {instruments.map((instrument) => (
                <option key={instrument.symbol} value={instrument.symbol}>
                  {instrument.symbol}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Timeframe</span>
            <Select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {timeframes.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </Select>
          </label>
        </div>

        <div className="mt-3">
          <span className="text-sm text-muted">Strategies</span>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {STRATEGIES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => toggleStrategy(s.value)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  strategies.includes(s.value)
                    ? "bg-accent text-accent-foreground"
                    : "border border-border text-muted hover:bg-surface-hover hover:text-foreground"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <Button
          type="button"
          onClick={runScan}
          disabled={scanning || strategies.length === 0}
          className="mt-4"
        >
          {scanning ? (
            <RefreshCw size={16} className="animate-spin" />
          ) : (
            <Search size={16} />
          )}
          {scanning ? "Scanning..." : "Scan"}
        </Button>
        {strategies.length === 0 && (
          <p className="mt-2 text-xs text-muted">Pick at least one strategy.</p>
        )}
      </Card>

      {scanError && (
        <Message kind="error" className="mt-4">
          {scanError}
        </Message>
      )}

      {signals && (
        <div className="mt-4 space-y-3">
          {signals.length === 0 && (
            <Card>
              <p className="text-sm text-muted">
                No confirmed setups right now for {symbol} on {timeframe}.
              </p>
            </Card>
          )}
          {signals.map((signal, i) => (
            <Card key={i}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">
                  {STRATEGY_LABELS[signal.strategy] ?? signal.strategy}
                </span>
                <span
                  className={`text-sm font-medium ${
                    signal.direction === "bullish" ? "text-buy" : "text-sell"
                  }`}
                >
                  {signal.direction === "bullish" ? "Bullish" : "Bearish"}
                </span>
                <Badge tone={SCOPE_TONE[signal.structure_scope] ?? "neutral"}>
                  {signal.structure_scope}
                </Badge>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
                <div>
                  <div className="text-muted">Entry</div>
                  <div>{formatPrice(signal.entry_price)}</div>
                </div>
                <div>
                  <div className="text-muted">Stop</div>
                  <div>{formatPrice(signal.stop_loss)}</div>
                </div>
                <div>
                  <div className="text-muted">Take Profit</div>
                  <div>
                    {signal.take_profit !== null
                      ? formatPrice(signal.take_profit)
                      : "—"}
                  </div>
                </div>
              </div>
              <p className="mt-2 text-sm text-muted">{signal.reason}</p>
            </Card>
          ))}
        </div>
      )}

      {Object.keys(liveStates).length > 0 && (
        <Card className="mt-4">
          <h2 className="font-semibold">Live setup state</h2>
          <div className="mt-2 space-y-2">
            {strategies.map((strategy) => {
              const state = liveStates[strategy];
              return (
                <div key={strategy} className="flex items-center justify-between text-sm">
                  <span>{STRATEGY_LABELS[strategy] ?? strategy}</span>
                  {state ? (
                    <Badge tone="accent">{stateLabel(state.state)}</Badge>
                  ) : (
                    <span className="text-muted">Not being watched live yet</span>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
}
