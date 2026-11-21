import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { applyStoredTheme } from "./theme.js";
import "./styles.css";

applyStoredTheme();

createRoot(document.getElementById("root")).render(<App />);
