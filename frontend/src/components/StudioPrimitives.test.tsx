import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ButtonHTMLAttributes, InputHTMLAttributes } from "react";

vi.mock("@gravity-ui/uikit", () => ({
  Button: ({ children, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props}>{children}</button>,
  TextInput: (props: InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

import { EmptyState, StatusBadge } from "./StudioPrimitives";

describe("Studio primitives", () => {
  it("renders an accessible empty state without pretending data exist", () => {
    render(<EmptyState title="No persisted evaluation">Save validation evidence before selecting policy.</EmptyState>);
    expect(screen.getByText("No persisted evaluation")).toBeVisible();
    expect(screen.getByText(/Save validation evidence/)).toBeVisible();
  });

  it("renders the declared evidence status", () => {
    render(<StatusBadge tone="warning">NOT AVAILABLE</StatusBadge>);
    expect(screen.getByText("NOT AVAILABLE")).toBeVisible();
  });
});
