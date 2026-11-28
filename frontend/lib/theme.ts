export const themeStorageKey = "faculty-ai.theme";

export const themeInitScript = `
(() => {
  const root = document.documentElement;
  const systemTheme = matchMedia("(prefers-color-scheme: dark)");
  const updateSystemTheme = () => {
    root.dataset.systemTheme = systemTheme.matches ? "dark" : "light";
  };
  const restoreTheme = () => {
    try {
      const stored = localStorage.getItem("${themeStorageKey}");
      if (stored === "light" || stored === "dark") {
        root.dataset.theme = stored;
      } else {
        delete root.dataset.theme;
      }
    } catch {}
  };
  updateSystemTheme();
  restoreTheme();
  systemTheme.addEventListener("change", updateSystemTheme);
  window.addEventListener("storage", (event) => {
    if (event.key === "${themeStorageKey}" || event.key === null) restoreTheme();
  });
})();`;
