import { useEffect, useState } from "react";
import { ApiError, createSession, getSession } from "./api";
import { ConsentScreen } from "./components/ConsentScreen";
import { DeclinedScreen } from "./components/DeclinedScreen";
import { EntryErrorScreen } from "./components/EntryErrorScreen";
import { LandingScreen } from "./components/LandingScreen";
import { LoadingScreen } from "./components/LoadingScreen";
import { QuestionFlow } from "./components/QuestionFlow";
import { ReportScreen } from "./components/ReportScreen";
import { Shell } from "./components/Shell";
import { StageIntroScreen } from "./components/StageIntroScreen";
import { WelcomeScreen } from "./components/WelcomeScreen";
import { clearStoredToken, loadStoredToken, storeToken } from "./storage";
import type { SessionState } from "./types";

type ViewState =
  | { kind: "landing" }
  | { kind: "loading" }
  | { kind: "entry_error"; message: string }
  | { kind: "welcome"; session: SessionState }
  | { kind: "consent"; session: SessionState }
  | { kind: "declined" }
  | { kind: "stage_intro"; session: SessionState }
  | { kind: "questions"; session: SessionState }
  | { kind: "report"; token: string };

/** ТЗ FR-04: система сама решает, какой экран показать — по состоянию сессии, без ручного выбора.
 *  Этап, который ещё не начат (ни одного ответа), сначала показывает стартовый экран — тест не
 *  запускается автоматически; уже начатый этап (есть хоть один ответ) при перезагрузке страницы
 *  возвращает прямо к вопросам (ТЗ FR-06.3/FR-06.4), а не на стартовый экран заново. */
function screenFromSession(session: SessionState): ViewState {
  if (session.consent_status === "declined") return { kind: "declined" };
  if (session.consent_status === "required") return { kind: "welcome", session };
  if (session.stage === null) return { kind: "report", token: session.token };
  if (session.stage_status === "not_started") return { kind: "stage_intro", session };
  return { kind: "questions", session };
}

export function App() {
  const [view, setView] = useState<ViewState>({ kind: "landing" });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const storedToken = loadStoredToken();
    // React.StrictMode в dev-режиме монтирует эффект дважды — без этого флага можно было бы
    // создать две сессии на один заход и применить уже устаревший ответ поверх нового состояния.
    let cancelled = false;

    async function bootstrap() {
      // FR-01.3: сохранённый токен продолжает прежнюю сессию — приоритет перед новым кодом в URL.
      if (storedToken) {
        setView({ kind: "loading" });
        try {
          const session = await getSession(storedToken);
          if (!cancelled) setView(screenFromSession(session));
          return;
        } catch {
          if (!cancelled) clearStoredToken();
        }
      }
      if (code) {
        setView({ kind: "loading" });
        try {
          const session = await createSession(code);
          // Отменённый (замененный вторым запуском эффекта) инстанс не должен перезаписывать
          // localStorage/URL уже после того, как активный инстанс сохранил свою сессию.
          if (cancelled) return;
          storeToken(session.token);
          window.history.replaceState({}, "", window.location.pathname);
          setView(screenFromSession(session));
        } catch (error) {
          if (cancelled) return;
          const message =
            error instanceof ApiError ? error.message : "Не удалось создать сессию. Попробуйте ещё раз.";
          setView({ kind: "entry_error", message });
        }
        return;
      }
      if (!cancelled) setView({ kind: "landing" });
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  let content;
  switch (view.kind) {
    case "landing":
      content = <LandingScreen />;
      break;
    case "loading":
      content = <LoadingScreen />;
      break;
    case "entry_error":
      content = <EntryErrorScreen message={view.message} />;
      break;
    case "welcome":
      content = (
        <WelcomeScreen session={view.session} onContinue={() => setView({ kind: "consent", session: view.session })} />
      );
      break;
    case "consent":
      content = <ConsentScreen session={view.session} onResult={(updated) => setView(screenFromSession(updated))} />;
      break;
    case "declined":
      content = <DeclinedScreen />;
      break;
    case "stage_intro":
      content = (
        <StageIntroScreen session={view.session} onStart={() => setView({ kind: "questions", session: view.session })} />
      );
      break;
    case "questions":
      content = (
        <QuestionFlow
          key={view.session.stage ?? "done"}
          session={view.session}
          onAdvance={(updated) => setView(screenFromSession(updated))}
        />
      );
      break;
    case "report":
      content = <ReportScreen token={view.token} />;
      break;
  }

  return <Shell>{content}</Shell>;
}
