import type { Meta, StoryObj } from "@storybook/react-vite";
import { FlowGrammar } from "./FlowGrammar";
const meta = { title: "Foundation/Flow grammar", component: FlowGrammar } satisfies Meta<typeof FlowGrammar>;
export default meta;
export const BaseNodes: StoryObj<typeof meta> = { render: () => <div style={{ height: 360 }}><FlowGrammar /></div> };
