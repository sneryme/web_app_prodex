function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }

  const field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.left = "-9999px";
  document.body.appendChild(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();

  return copied ? Promise.resolve() : Promise.reject(new Error("Copy failed"));
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest(".js-copy-entry-link");
  if (!button) return;

  const originalText = button.textContent;
  try {
    await copyText(button.dataset.copyUrl);
    button.textContent = "Скопировано";
  } catch {
    button.textContent = "Не удалось скопировать";
  }

  window.setTimeout(() => {
    button.textContent = originalText;
  }, 1800);
});
