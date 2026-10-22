import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { EmployerApp } from "./employer/EmployerApp";
import { ProdexApp } from "./prodex/ProdexApp";
import "./styles.css";
import "./employer/employer.css";
import "./prodex/prodex.css";

// Нет роутинга (намеренно, см. ARCHITECTURE.md) — участник, работодатель и PRODEX Admin это три
// разных "контура" (PROJECT_RULES №9, ТЗ FR-11.6), поэтому различаются просто по пути, без
// react-router.
const isEmployer = window.location.pathname.startsWith("/employer");
const isProdex = window.location.pathname.startsWith("/prodex");

createRoot(document.getElementById("root")!).render(
  <StrictMode>{isProdex ? <ProdexApp /> : isEmployer ? <EmployerApp /> : <App />}</StrictMode>,
);
