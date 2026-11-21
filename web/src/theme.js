const KEY = "kb_web_theme";

export function loadTheme() {
  const stored = localStorage.getItem(KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

export function applyTheme(theme) {
  const next = theme === "light" || theme === "dark" ? theme : "system";
  localStorage.setItem(KEY, next);
  if (next === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = next;
  return next;
}

export function applyStoredTheme() {
  applyTheme(loadTheme());
}
