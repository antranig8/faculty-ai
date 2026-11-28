const storageKey = "faculty-ai.latest-rehearsal";
const pendingUpdates = new Map<string, Promise<unknown>>();
let latestSessionId: string | undefined;

export function rememberRehearsal(sessionId: string) {
  latestSessionId = sessionId;
  try {
    window.localStorage.setItem(storageKey, sessionId);
  } catch {
    // The in-memory ID still works when navigating in this tab.
  }
}

export function latestRehearsal(): string | undefined {
  try {
    return window.localStorage.getItem(storageKey) ?? latestSessionId;
  } catch {
    return latestSessionId;
  }
}

export function queueRehearsalUpdate<T>(sessionId: string, update: () => Promise<T>): Promise<T> {
  const previous = pendingUpdates.get(sessionId);
  // Analysis and question resolution both write the same backend session.
  const pending = Promise.resolve(previous).catch(() => undefined).then(update);
  pendingUpdates.set(sessionId, pending);
  function removeUpdate() {
    if (pendingUpdates.get(sessionId) === pending) {
      pendingUpdates.delete(sessionId);
    }
  }
  void pending.then(removeUpdate, removeUpdate);
  return pending;
}

export async function waitForRehearsalUpdates(sessionId: string) {
  await pendingUpdates.get(sessionId)?.catch(() => undefined);
}
