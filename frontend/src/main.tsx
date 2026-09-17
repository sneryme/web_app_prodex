import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  return <main className="shell"><div className="eyebrow">PRODEX / DIGITAL</div><h1>Комната психоэмоционального здоровья</h1><p className="lead">Цифровой маршрут оценки состояния «до / после».</p><section className="card"><span className="tag">MVP scaffold</span><h2>Ваш стартовый профиль</h2><p>Здесь появится безопасный маршрут тестирования с одним вопросом на экран, автосохранением и понятным результатом.</p><button>Начать знакомство</button></section><p className="note">Результаты опросников носят информационный и скрининговый характер и не являются диагнозом.</p></main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
