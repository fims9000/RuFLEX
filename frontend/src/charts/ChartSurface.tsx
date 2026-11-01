import * as echarts from "echarts";
import { EChartsOption } from "echarts";
import { useEffect, useRef } from "react";
import { chartThemeNames, registerChartThemes } from "../design/chartTheme";
import { StudioTheme } from "../design/tokens";
import { ui } from "../design/language";

let themesRegistered = false;
export function ChartSurface({ title, option, theme, state = "ready" }: { title: string; option: EChartsOption; theme: StudioTheme; state?: "ready" | "loading" | "error" | "empty" }) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current || state !== "ready") return;
    if (!themesRegistered) { registerChartThemes(); themesRegistered = true; }
    const chart = echarts.init(container.current, chartThemeNames[theme], { renderer: "svg" });
    chart.setOption(option, { notMerge: true });
    const resize = new ResizeObserver(() => chart.resize()); resize.observe(container.current);
    return () => { resize.disconnect(); chart.dispose(); };
  }, [option, state, theme]);
  return <section className="chart-surface" aria-label={title}><div className="chart-title">{title}</div>{state === "ready" ? <div ref={container} className="chart-canvas" /> : <div className={`chart-state ${state}`} role={state === "error" ? "alert" : "status"}>{state === "error" ? ui("Chart unavailable", "Не удалось показать график") : state === "loading" ? ui("Loading chart…", "Загрузка графика…") : ui("No evidence yet", "Нет данных для графика")}</div>}</section>;
}
