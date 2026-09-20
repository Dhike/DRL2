"use client";

import type { IChartApi, ISeriesApi, UTCTimestamp } from "lightweight-charts";
import { useCallback, useEffect, useRef } from "react";

import type { CandleData } from "../lib/api";
import { useTheme, type Theme } from "../lib/theme";

type ChartSeries = {
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
};

function cssColor(name: string): string {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

export default function PriceChart({ candles }: { candles: CandleData[] }) {
  const theme = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ChartSeries | null>(null);
  const latest = useRef<{ candles: CandleData[]; theme: Theme }>({
    candles,
    theme,
  });

  const apply = useCallback(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const buy = cssColor("--buy");
    const sell = cssColor("--sell");
    const grid = cssColor("--border");

    chart.applyOptions({
      layout: { textColor: cssColor("--muted") },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      rightPriceScale: { borderColor: grid },
      timeScale: { borderColor: grid },
    });
    series.candles.applyOptions({
      upColor: buy,
      downColor: sell,
      wickUpColor: buy,
      wickDownColor: sell,
    });

    const data = latest.current.candles;
    series.candles.setData(
      data.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    series.volume.setData(
      data.map((c) => ({
        time: c.time as UTCTimestamp,
        value: c.volume,
        color: `${c.close >= c.open ? buy : sell}66`,
      })),
    );
    chart.timeScale().fitContent();
  }, []);

  useEffect(() => {
    let disposed = false;
    let chart: IChartApi | null = null;

    import("lightweight-charts").then((lib) => {
      const container = containerRef.current;
      if (disposed || !container) return;

      chart = lib.createChart(container, {
        autoSize: true,
        layout: {
          background: { type: lib.ColorType.Solid, color: "transparent" },
          fontSize: 12,
        },
        crosshair: { mode: lib.CrosshairMode.Normal },
        timeScale: { timeVisible: true, secondsVisible: false },
      });
      const candlesSeries = chart.addSeries(lib.CandlestickSeries, {
        borderVisible: false,
      });
      const volumeSeries = chart.addSeries(lib.HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "",
      });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });

      chartRef.current = chart;
      seriesRef.current = { candles: candlesSeries, volume: volumeSeries };
      apply();
    });

    return () => {
      disposed = true;
      chart?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [apply]);

  useEffect(() => {
    latest.current = { candles, theme };
    apply();
  }, [candles, theme, apply]);

  return <div ref={containerRef} className="h-[360px] w-full" />;
}
