import type { FeedbackItem } from "@/lib/types";

type Props = {
  latestFeedback?: FeedbackItem;
  open: boolean;
  unseenCount: number;
  onOpen: () => void;
};

export function FacultyAlert({ latestFeedback, open, unseenCount, onOpen }: Props) {
  if (!latestFeedback || open) {
    return null;
  }

  return (
    <button className="faculty-alert" onClick={onOpen} type="button" aria-label="Open faculty feedback">
      <span>!</span>
      {unseenCount > 0 ? <strong>{unseenCount}</strong> : null}
    </button>
  );
}

