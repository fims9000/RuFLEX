import { createRoot } from "react-dom/client";
import { ThemeProvider } from "@gravity-ui/uikit";
import { useState } from "react";
import { App } from "./app/App";
import { StudioTheme } from "./design/tokens";
import "./styles.css";

const initialTheme: StudioTheme = localStorage.getItem("ruflex.theme") === "dark" ? "dark" : "light";
document.documentElement.dataset.ruflexTheme = initialTheme;

function StudioRoot() {
  const [theme, setTheme] = useState<StudioTheme>(initialTheme);
  return <ThemeProvider theme={theme}><App theme={theme} setTheme={setTheme} /></ThemeProvider>;
}

createRoot(document.getElementById("root")!).render(<StudioRoot />);
