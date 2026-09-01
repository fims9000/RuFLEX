import { createRoot } from "react-dom/client";
import { ThemeProvider } from "@gravity-ui/uikit";
import { App } from "./app/App";
import "./styles.css";
createRoot(document.getElementById("root")!).render(<ThemeProvider><App /></ThemeProvider>);
