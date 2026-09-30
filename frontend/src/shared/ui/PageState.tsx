export function PageLoader() {
  return (
    <p className="hint" role="status">
      Загрузка…
    </p>
  );
}

export function PageError({ message = "Не удалось загрузить данные. Обновите страницу." }) {
  return (
    <p className="alert" role="alert">
      {message}
    </p>
  );
}
