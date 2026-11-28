const pendingUpdates = new Map<string, Promise<unknown>>();

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
