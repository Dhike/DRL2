"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import PriceChart from "../../components/PriceChart";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Message from "../../components/ui/Message";
import { Select } from "../../components/ui/Select";
import {
  ApiError,
  getCandles,
  getCatalog,
  type CandleData,
  type Catalog,
} from "../../lib/api";

type Loaded = { key: string; candles: CandleData[]; error: string | null };

const PROVIDER_LABELS: Record<string, string> = { gate: "Gate.io" };

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

export default function ManualAnalysisPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [timeframe, setTimeframe] = useState("1h");
  const [reloadKey, setReloadKey] = useState(0);
  const [loaded, setLoaded] = useState<Loaded | null>(null);

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

  const requestKey = `${symbol}|${timeframe}|${reloadKey}`;

  useEffect(() => {
    let cancelled = false;
    getCandles(symbol, timeframe, 300)
      .then((result) => {
        if (!cancelled) {
          setLoaded({ key: requestKey, candles: result.candles, error: null });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setLoaded({ key: requestKey, candles: [], error: describe(err) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [symbol, timeframe, requestKey]);

  const loading = loaded?.key !== requestKey;
  const candles = loaded?.candles ?? [];
  const error = loading ? null : (loaded?.error ?? null);

  const first = candles.at(0);
  const last = candles.at(-1);
  const change =
    first && last ? ((last.close - first.open) / first.open) * 100 : null;

  const instruments = catalog?.instruments ?? [{ symbol, market: "crypto" }];
  const timeframes = catalog?.timeframes ?? [timeframe];

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">Manual Analysis</h1>
        {catalog && (
          <Badge tone="accent">
            {PROVIDER_LABELS[catalog.provider] ?? catalog.provider}
          </Badge>
        )}
      </div>
      <p className="mt-1 text-sm text-muted">
        Pick an instrument and timeframe to view price candles.
      </p>

      {catalogError && (
        <Message kind="error" className="mt-4">
          {catalogError}
        </Message>
      )}

      <Card className="mt-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Market</span>
            <Select disabled defaultValue="crypto">
              <option value="crypto">Crypto</option>
            </Select>
          </label>
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
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {timeframes.map((tf) => (
            <button
              key={tf}
              type="button"
              onClick={() => setTimeframe(tf)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                tf === timeframe
                  ? "bg-accent text-accent-foreground"
                  : "border border-border text-muted hover:bg-surface-hover hover:text-foreground"
              }`}
            >
              {tf}
            </button>
          ))}
          <Button
            type="button"
            variant="secondary"
            onClick={() => setReloadKey((k) => k + 1)}
            disabled={loading}
            className="ml-auto"
          >
            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
            Refresh
          </Button>
        </div>
      </Card>

      <Card className="mt-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <span className="text-lg font-semibold">{symbol}</span>
            {last && (
              <span className="ml-3 text-lg">{formatPrice(last.close)}</span>
            )}
            {change !== null && (
              <span
                className={`ml-2 text-sm ${change >= 0 ? "text-buy" : "text-sell"}`}
              >
                {change >= 0 ? "+" : ""}
                {change.toFixed(2)}%
              </span>
            )}
          </div>
          <div className="text-xs text-muted">
            {loading
              ? "Loading..."
              : last
                ? `Last bar ${new Date(last.time * 1000).toLocaleString()}${last.closed ? "" : " (forming)"}`
                : ""}
          </div>
        </div>
        {error && (
          <Message kind="error" className="mt-3">
            {error}
          </Message>
        )}
        <div className="mt-3">
          <PriceChart candles={candles} />
        </div>
      </Card>
    </div>
  );
}
