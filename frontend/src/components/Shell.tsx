import type { ReactNode } from "react";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <main className="shell">
      <div className="eyebrow">PRODEX / DIGITAL</div>
      <h1>Комната психоэмоционального здоровья</h1>
      <p className="lead">Цифровой маршрут оценки состояния «до / после».</p>
      {children}
      <p className="note">
        Результаты опросников носят информационный и скрининговый характер и не являются диагнозом.
      </p>
    </main>
  );
}
