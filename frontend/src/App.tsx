import { useEffect, useState } from "react";
import { ApiError, createSession, getEntryContext, getSession, selectBundle } from "./api";
import { ConsentScreen } from "./components/ConsentScreen";
import { DeclinedScreen } from "./components/DeclinedScreen";
import { EntryErrorScreen } from "./components/EntryErrorScreen";
import { FollowupNoticeScreen } from "./components/FollowupNoticeScreen";
import { LandingScreen } from "./components/LandingScreen";
import { LoadingScreen } from "./components/LoadingScreen";
import { QuestionFlow } from "./components/QuestionFlow";
import { ReportScreen } from "./components/ReportScreen";
import { Shell } from "./components/Shell";
import { StreamSelectionScreen } from "./components/StreamSelectionScreen";
import { BundleSelectionScreen } from "./components/BundleSelectionScreen";
import { TestMenuScreen } from "./components/TestMenuScreen";
import { TokenNoticeScreen } from "./components/TokenNoticeScreen";
import { WelcomeScreen } from "./components/WelcomeScreen";
import {
  clearStoredToken,
  clearTokenNoticePending,
  isTokenNoticePending,
  loadStoredToken,
  markTokenNoticePending,
  storeToken,
} from "./storage";
import type { ParticipantHomeState, ParticipantStream, SessionState } from "./types";

type ViewState =
  | { kind: "landing" }
  | { kind: "loading" }
  | { kind: "stream_select"; entryCode: string; streams: ParticipantStream[] }
  | { kind: "token_notice"; home: ParticipantHomeState }
  | { kind: "bundle_select"; home: ParticipantHomeState }
  | { kind: "entry_error"; message: string }
  | { kind: "welcome"; session: SessionState }
  | { kind: "consent"; session: SessionState }
  | { kind: "followup_notice"; session: SessionState }
  | { kind: "declined" }
  | { kind: "test_menu"; session: SessionState }
  | { kind: "questions"; session: SessionState; questionnaireCode: string }
  | { kind: "report"; token: string; bundleId: number };

/** ТЗ FR-04: система сама решает, какой экран показать — по состоянию сессии, без ручного выбора.
 *  Этап, который ещё не начат (ни одного ответа), сначала показывает стартовый экран — тест не
 *  запускается автоматически; уже начатый этап (есть хоть один ответ) при перезагрузке страницы
 *  возвращает прямо к вопросам (ТЗ FR-06.3/FR-06.4), а не на стартовый экран заново. */
function screenFromSession(session: SessionState): ViewState {
  if (session.consent_status === "declined") return { kind: "declined" };
  if (session.consent_status === "required") return { kind: "welcome", session };
  if (session.stage === null) return { kind: "report", token: session.token, bundleId: session.bundle_id ?? 0 };
  if (session.stage === "followup" && (session.followup_locked || session.stage_status === "not_started")) {
    return { kind: "followup_notice", session };
  }
  if (session.stage_status === "not_started") return { kind: "test_menu", session };
  const firstUnanswered = session.questions.find((question) => question.answer === null);
  return { kind: "questions", session, questionnaireCode: firstUnanswered?.questionnaire_code ?? session.questionnaires[0]?.code ?? "" };
}

export function App() {
  const [view, setView] = useState<ViewState>({ kind: "landing" });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const participantToken = params.get("token");
    const storedToken = loadStoredToken();
    // React.StrictMode в dev-режиме монтирует эффект дважды — без этого флага можно было бы
    // создать две сессии на один заход и применить уже устаревший ответ поверх нового состояния.
    let cancelled = false;

    async function bootstrap() {
      if (participantToken) {
        clearTokenNoticePending();
        setView({ kind: "loading" });
        try {
          const session = await getSession(participantToken);
          if (cancelled) return;
          storeToken(session.token);
          window.history.replaceState({}, "", window.location.pathname);
          setView({ kind: "bundle_select", home: session });
        } catch (error) {
          if (cancelled) return;
          clearStoredToken();
          window.history.replaceState({}, "", window.location.pathname);
          const message = error instanceof ApiError ? error.message : "Could not restore this session. Please try again.";
          setView({ kind: "entry_error", message });
        }
        return;
      }

      // У ссылки организации приоритет над сохранённой сессией другой организации. Если токен
      // относится к этой же организации, продолжаем его как раньше.
      if (code) {
        setView({ kind: "loading" });
        try {
          const entry = await getEntryContext(code);
          if (cancelled) return;
          if (storedToken) {
            try {
              const session = await getSession(storedToken);
              if (cancelled) return;
              if (session.organization_id === entry.organization_id) {
                setView(
                  isTokenNoticePending() ? { kind: "token_notice", home: session } : { kind: "bundle_select", home: session },
                );
                return;
              }
            } catch {
              if (!cancelled) clearStoredToken();
            }
          }
          if (!cancelled) setView({ kind: "stream_select", entryCode: code, streams: entry.streams });
        } catch (error) {
          if (cancelled) return;
          const message = error instanceof ApiError ? error.message : "Не удалось создать сессию. Попробуйте ещё раз.";
          setView({ kind: "entry_error", message });
        }
        return;
      }

      // Без новой корпоративной ссылки продолжаем сохранённую сессию участника.
      if (storedToken) {
        setView({ kind: "loading" });
        try {
          const session = await getSession(storedToken);
          if (!cancelled) {
            setView(isTokenNoticePending() ? { kind: "token_notice", home: session } : { kind: "bundle_select", home: session });
          }
          return;
        } catch {
          if (!cancelled) clearStoredToken();
        }
      }
      if (!cancelled) setView({ kind: "landing" });
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  async function startSession(entryCode: string, streamId: number | null) {
    setView({ kind: "loading" });
    try {
      const home = await createSession(entryCode, streamId);
      storeToken(home.token);
      markTokenNoticePending();
      window.history.replaceState({}, "", window.location.pathname);
      setView({ kind: "token_notice", home });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Could not create a session. Please try again.";
      setView({ kind: "entry_error", message });
    }
  }

  async function resumeSession(token: string) {
    const home = await getSession(token);
    clearTokenNoticePending();
    storeToken(home.token);
    window.history.replaceState({}, "", window.location.pathname);
    setView({ kind: "bundle_select", home });
  }

  function continueFromTokenNotice(home: ParticipantHomeState) {
    clearTokenNoticePending();
    setView({ kind: "bundle_select", home });
  }

  async function openBundle(token: string, bundleId: number) {
    const session = await selectBundle(token, bundleId);
    setView(screenFromSession(session));
  }

  async function returnToBundleMenu(token: string) {
    try {
      const home = await getSession(token);
      storeToken(home.token);
      setView({ kind: "bundle_select", home });
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "Could not load the test bundle menu. Please try again.";
      setView({ kind: "entry_error", message });
    }
  }

  let content;
  switch (view.kind) {
    case "landing":
      content = <LandingScreen onResume={resumeSession} />;
      break;
    case "loading":
      content = <LoadingScreen />;
      break;
    case "stream_select":
      content = (
        <StreamSelectionScreen
          streams={view.streams}
          onSelect={(streamId) => void startSession(view.entryCode, streamId)}
          onResume={resumeSession}
        />
      );
      break;
    case "token_notice":
      content = <TokenNoticeScreen home={view.home} onContinue={() => continueFromTokenNotice(view.home)} />;
      break;
    case "bundle_select":
      content = view.home.consent_status === "declined" ? (
        <DeclinedScreen />
      ) : (
        <BundleSelectionScreen home={view.home} onSelect={(bundleId) => openBundle(view.home.token, bundleId)} />
      );
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
    case "followup_notice":
      content = (
        <FollowupNoticeScreen
          session={view.session}
          onContinue={() => setView({ kind: "test_menu", session: view.session })}
          onBackToBundles={() => void returnToBundleMenu(view.session.token)}
        />
      );
      break;
    case "declined":
      content = <DeclinedScreen />;
      break;
    case "test_menu":
      content = (
        <TestMenuScreen
          session={view.session}
          onSelect={(code) => setView({ kind: "questions", session: view.session, questionnaireCode: code })}
            onBackToBundles={() => void returnToBundleMenu(view.session.token)}
        />
      );
      break;
    case "questions":
      content = (
        <QuestionFlow
          key={`${view.session.stage ?? "done"}-${view.questionnaireCode}`}
          session={view.session}
          questionnaireCode={view.questionnaireCode}
          onAdvance={(updated) => setView({ ...view, session: updated })}
          onBackToMenu={(updated) => setView({ kind: "test_menu", session: updated })}
          onQuestionnaireComplete={(updated) =>
            setView(updated.stage === view.session.stage ? { kind: "test_menu", session: updated } : screenFromSession(updated))
          }
        />
      );
      break;
    case "report":
      content = (
        <ReportScreen
          token={view.token}
          bundleId={view.bundleId}
          onBackToBundles={() => void returnToBundleMenu(view.token)}
        />
      );
      break;
  }

  return <Shell>{content}</Shell>;
}
