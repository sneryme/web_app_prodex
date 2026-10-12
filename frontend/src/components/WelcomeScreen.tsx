import type { SessionState } from "../types";
import { TokenBadge } from "./TokenBadge";

interface Props {
  session: SessionState;
  onContinue: () => void;
}

/** ТЗ FR-02: цель, время, конфиденциальность и что увидит работодатель — до перехода к согласиям. */
export function WelcomeScreen({ session, onContinue }: Props) {
  return (
    <section className="card">
      <span className="tag">Шаг 1 из 3 · Знакомство</span>
      <h2>Добро пожаловать</h2>
      <p>Вы проходите короткое тестирование «до / после» курса в Комнате психоэмоционального здоровья.</p>
      <ul className="facts">
        <li>
          <strong>Цель.</strong> Оценить ваше состояние до и после курса, чтобы вы сами увидели изменения.
        </li>
        <li>
          <strong>Время.</strong> Прохождение занимает несколько минут — один вопрос на экран.
        </li>
        <li>
          <strong>Конфиденциальность.</strong> У вас анонимный код участника; ФИО, телефон и e-mail не
          запрашиваются.
        </li>
        <li>
          <strong>Работодатель.</strong> Получает только обезличенную групповую статистику — ваш личный
          результат ему не передаётся.
        </li>
      </ul>
      <button type="button" onClick={onContinue}>
        Начать знакомство
      </button>
      <TokenBadge token={session.token} />
    </section>
  );
}
