import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { EmployerApp } from "./employer/EmployerApp";
import "./styles.css";
import "./employer/employer.css";

// Нет роутинга (намеренно, см. ARCHITECTURE.md) — участник и работодатель это два разных
// "контура" (PROJECT_RULES №9), поэтому различаются просто по пути, без react-router.
const isEmployer = window.location.pathname.startsWith("/employer");

createRoot(document.getElementById("root")!).render(
  <StrictMode>{isEmployer ? <EmployerApp /> : <App />}</StrictMode>,
);
