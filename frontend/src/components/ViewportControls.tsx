import { ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ArrowUp, ArrowDown } from "lucide-react";

type ViewportControlsProps = {
  onForward: () => void;
  onBackward: () => void;
  onUp: () => void;
  onDown: () => void;
  onTurnLeft: () => void;
  onTurnRight: () => void;
};

export function ViewportControls({
  onForward,
  onBackward,
  onUp,
  onDown,
  onTurnLeft,
  onTurnRight,
}: ViewportControlsProps) {
  return (
    <div className="overlay-controls">
      <button type="button" className="nav-arrow left" aria-label="Turn left" onClick={onTurnLeft}>
        <ChevronLeft size={32} strokeWidth={3} />
      </button>
      <button
        type="button"
        className="nav-arrow right"
        aria-label="Turn right"
        onClick={onTurnRight}
      >
        <ChevronRight size={32} strokeWidth={3} />
      </button>
      <button
        type="button"
        className="nav-arrow center-forward"
        aria-label="Move forward"
        onClick={onForward}
      >
        <ChevronUp size={32} strokeWidth={3} />
      </button>
      <button
        type="button"
        className="nav-arrow center-backward"
        aria-label="Move backward"
        onClick={onBackward}
      >
        <ChevronDown size={32} strokeWidth={3} />
      </button>
      <button type="button" className="nav-arrow z-up" aria-label="Move up" onClick={onUp}>
        <ArrowUp size={28} strokeWidth={3} />
      </button>
      <button type="button" className="nav-arrow z-down" aria-label="Move down" onClick={onDown}>
        <ArrowDown size={28} strokeWidth={3} />
      </button>
    </div>
  );
}

