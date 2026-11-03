import type { ParticipantStream } from "../types";
import { ResumeSessionForm } from "./ResumeSessionForm";

interface Props {
  streams: ParticipantStream[];
  onSelect: (streamId: number | null) => void;
  onResume: (token: string) => Promise<void>;
}

export function StreamSelectionScreen({ streams, onSelect, onResume }: Props) {
  return (
    <section className="card">
      <span className="tag">{"\u0423\u0447\u0430\u0441\u0442\u0438\u0435 \u0432 \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0435"}</span>
      <h2>{"\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u043e\u0442\u043e\u043a"}</h2>
      {streams.length ? (
        <>
          <p>{"\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0433\u0440\u0443\u043f\u043f\u0443, \u043a \u043a\u043e\u0442\u043e\u0440\u043e\u0439 \u0432\u044b \u043e\u0442\u043d\u043e\u0441\u0438\u0442\u0435\u0441\u044c."}</p>
          <div className="stream-menu">
            {streams.map((stream) => (
              <button key={stream.id} type="button" className="stream-menu__item" onClick={() => onSelect(stream.id)}>
                <span className="stream-menu__name">{stream.name}</span>
                <span className="stream-menu__code">{stream.code}</span>
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          <p>{"\u0414\u043b\u044f \u044d\u0442\u043e\u0439 \u043e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0446\u0438\u0438 \u043f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0445 \u043f\u043e\u0442\u043e\u043a\u043e\u0432. \u041c\u043e\u0436\u043d\u043e \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u0431\u0435\u0437 \u0432\u044b\u0431\u043e\u0440\u0430 \u043f\u043e\u0442\u043e\u043a\u0430."}</p>
          <button type="button" onClick={() => onSelect(null)}>{"\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"}</button>
        </>
      )}
      <ResumeSessionForm onResume={onResume} />
    </section>
  );
}
