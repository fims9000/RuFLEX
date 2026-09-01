import type { Meta, StoryObj } from "@storybook/react-vite";
import { ChartSurface } from "./ChartSurface";
import { chartFixtures } from "./fixtureOptions";
const meta = { title: "Foundation/ChartSurface", component: ChartSurface } satisfies Meta<typeof ChartSurface>;
export default meta;
export const Ready: StoryObj<typeof meta> = { args: { title: "Learning curves", option: chartFixtures[0].option, theme: "light" } };
export const States: StoryObj<typeof meta> = { args: { title: "States", option: {}, theme: "light" }, render: () => <div style={{ display: "grid", gap: 12 }}><ChartSurface title="Loading" option={{}} theme="light" state="loading" /><ChartSurface title="Empty" option={{}} theme="dark" state="empty" /><ChartSurface title="Error" option={{}} theme="light" state="error" /></div> };
