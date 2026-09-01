import * as echarts from "echarts";

const common = { backgroundColor: "transparent", textStyle: { fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 } };
export const chartThemeNames = { light: "ruflex-light", dark: "ruflex-dark" } as const;

export function registerChartThemes() {
  echarts.registerTheme(chartThemeNames.light, { ...common, color: ["#3B6FD8", "#C76B1D", "#16858C", "#8057C8", "#BE4F73", "#3D8658"], textStyle: { ...common.textStyle, color: "#66635D" }, categoryAxis: { axisLine: { lineStyle: { color: "#C6BFB4" } }, axisLabel: { color: "#66635D" }, splitLine: { lineStyle: { color: "#E8E3DA" } } }, valueAxis: { axisLabel: { color: "#66635D" }, splitLine: { lineStyle: { color: "#E8E3DA" } } }, tooltip: { backgroundColor: "#FCFBF8", borderColor: "#D8D2C8", textStyle: { color: "#1B1B19" } } });
  echarts.registerTheme(chartThemeNames.dark, { ...common, color: ["#7EA5FF", "#F0A45D", "#66C8CC", "#B29AE8", "#E88AA8", "#82C997"], textStyle: { ...common.textStyle, color: "#B7B2A8" }, categoryAxis: { axisLine: { lineStyle: { color: "#4B4A42" } }, axisLabel: { color: "#B7B2A8" }, splitLine: { lineStyle: { color: "#302F2C" } } }, valueAxis: { axisLabel: { color: "#B7B2A8" }, splitLine: { lineStyle: { color: "#302F2C" } } }, tooltip: { backgroundColor: "#20201E", borderColor: "#383832", textStyle: { color: "#F2EFE8" } } });
}
