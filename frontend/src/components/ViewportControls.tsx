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
        <span aria-hidden>◀</span>
      </button>
      <button
        type="button"
        className="nav-arrow right"
        aria-label="Turn right"
        onClick={onTurnRight}
      >
        <span aria-hidden>▶</span>
      </button>
      <button
        type="button"
        className="nav-arrow center-forward"
        aria-label="Move forward"
        onClick={onForward}
      >
        <span aria-hidden>▲</span>
      </button>
      <button
        type="button"
        className="nav-arrow center-backward"
        aria-label="Move backward"
        onClick={onBackward}
      >
        <span aria-hidden>▼</span>
      </button>
      <button type="button" className="nav-arrow z-up" aria-label="Move up" onClick={onUp}>
        <span aria-hidden>↥</span>
      </button>
      <button type="button" className="nav-arrow z-down" aria-label="Move down" onClick={onDown}>
        <span aria-hidden>↧</span>
      </button>
    </div>
  );
}

