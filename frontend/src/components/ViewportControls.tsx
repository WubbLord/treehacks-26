import { RotateCcw, RotateCw, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from "lucide-react";

type ViewportControlsProps = {
  onForward: () => void;
  onBackward: () => void;
  onLeft: () => void;
  onRight: () => void;
  onUp: () => void;
  onDown: () => void;
  onTurnLeft: () => void;
  onTurnRight: () => void;
};

export function ViewportControls({
  onForward,
  onBackward,
  onLeft,
  onRight,
  onUp,
  onDown,
  onTurnLeft,
  onTurnRight,
}: ViewportControlsProps) {
  return (
    <div className="overlay-controls">
      {/* Rotation controls - bottom corners with circular arrows */}
      <button type="button" className="nav-arrow rotate-left" aria-label="Rotate counter-clockwise" onClick={onTurnLeft} title="Turn Left (CCW)">
        <RotateCcw size={26} strokeWidth={2.5} />
        <span className="nav-label">CCW</span>
      </button>
      <button
        type="button"
        className="nav-arrow rotate-right"
        aria-label="Rotate clockwise"
        onClick={onTurnRight}
        title="Turn Right (CW)"
      >
        <RotateCw size={26} strokeWidth={2.5} />
        <span className="nav-label">CW</span>
      </button>

      {/* Movement controls - center bottom (WASD-style layout) */}
      <button
        type="button"
        className="nav-arrow move-forward"
        aria-label="Move forward"
        onClick={onForward}
        title="Move Forward"
      >
        <ArrowUp size={28} strokeWidth={3} />
        <span className="nav-label">FWD</span>
      </button>
      <button
        type="button"
        className="nav-arrow move-left"
        aria-label="Strafe left"
        onClick={onLeft}
        title="Strafe Left"
      >
        <ArrowLeft size={28} strokeWidth={3} />
        <span className="nav-label">LEFT</span>
      </button>
      <button
        type="button"
        className="nav-arrow move-backward"
        aria-label="Move backward"
        onClick={onBackward}
        title="Move Backward"
      >
        <ArrowDown size={28} strokeWidth={3} />
        <span className="nav-label">BACK</span>
      </button>
      <button
        type="button"
        className="nav-arrow move-right"
        aria-label="Strafe right"
        onClick={onRight}
        title="Strafe Right"
      >
        <ArrowRight size={28} strokeWidth={3} />
        <span className="nav-label">RIGHT</span>
      </button>

      {/* Vertical (altitude) controls - top right */}
      <div className="nav-group altitude">
        <span className="nav-group-label">ALT</span>
        <button type="button" className="nav-arrow z-up" aria-label="Move up (altitude)" onClick={onUp} title="Increase Altitude">
          <ArrowUp size={20} strokeWidth={3} />
        </button>
        <button type="button" className="nav-arrow z-down" aria-label="Move down (altitude)" onClick={onDown} title="Decrease Altitude">
          <ArrowDown size={20} strokeWidth={3} />
        </button>
      </div>
    </div>
  );
}

