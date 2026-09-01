import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button, EmptyState, PanelHeader, StatusBadge, TextInput } from "./StudioPrimitives";

const meta = { title: "Foundation/Primitives", parameters: { layout: "padded" } } satisfies Meta;
export default meta;
export const Controls: StoryObj = { render: () => <div style={{ display: "grid", gap: 12, maxWidth: 360 }}><Button view="action">Primary action</Button><Button view="outlined">Secondary</Button><Button disabled>Disabled</Button><TextInput placeholder="Input" /><PanelHeader title="PANEL HEADER" detail="state" /><StatusBadge tone="success">PASS</StatusBadge><StatusBadge tone="warning">WARNING</StatusBadge><StatusBadge tone="danger">ERROR</StatusBadge></div> };
export const EmptyLoadingError: StoryObj = { render: () => <><EmptyState title="No evidence">Run an analysis to create an artifact.</EmptyState><div className="error">Controlled error state</div></> };
