"use client";

import { themeStorageKey } from "@/lib/theme";

import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  function toggleTheme() {
    const { dataset } = document.documentElement;
    const nextTheme = (dataset.theme ?? dataset.systemTheme) === "dark" ? "light" : "dark";
    dataset.theme = nextTheme;
    try {
      localStorage.setItem(themeStorageKey, nextTheme);
    } catch {
      // The selection still applies in the current tab.
    }
  }

  return (
    <button className={styles.toggle} type="button" onClick={toggleTheme}>
      <span className={styles.switchToDark}>
        <span className={styles.icon} aria-hidden="true">☾</span>
        <span className={styles.label}>Dark mode</span>
      </span>
      <span className={styles.switchToLight}>
        <span className={styles.icon} aria-hidden="true">☀︎</span>
        <span className={styles.label}>Light mode</span>
      </span>
    </button>
  );
}
