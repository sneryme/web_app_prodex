/** ТЗ FR-01.4: неверная или отключённая ссылка — понятная ошибка, токен не создаётся. */
export function EntryErrorScreen({ message }: { message: string }) {
  return (
    <section className="card">
      <span className="tag">Не удалось начать</span>
      <h2>Ссылка недействительна или отключена</h2>
      <p>{message} Обратитесь к вашему координатору за актуальной ссылкой или QR-кодом.</p>
    </section>
  );
}
