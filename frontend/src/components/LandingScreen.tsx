import { useState } from "react";

/** Публичная страница без корпоративного кода — не функциональный вход, а общее описание сервиса. */
export function LandingScreen() {
  const [showHint, setShowHint] = useState(false);

  return (
    <section className="card">
      <span className="tag">MVP scaffold</span>
      <h2>Ваш стартовый профиль</h2>
      <p>
        Здесь появится безопасный маршрут тестирования с одним вопросом на экран, автосохранением и
        понятным результатом.
      </p>
      <button type="button" onClick={() => setShowHint(true)}>
        Начать знакомство
      </button>
      {showHint && (
        <p className="hint">
          Чтобы начать, перейдите по ссылке или QR-коду, который прислал ваш работодатель.
        </p>
      )}
    </section>
  );
}
