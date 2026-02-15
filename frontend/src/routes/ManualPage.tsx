import { useEffect, useMemo, useState, useCallback } from "react";
import { fetchImageForPose } from "../api/images";
import { MOVE_STEP, VERTICAL_STEP, YAW_STEP_DEGREES } from "../config";
import { ViewportControls } from "../components/ViewportControls";
import type { Pose } from "../types/pose";

const initialPose: Pose = {
  x: 0,
  y: 0,
  z: 0,
  yaw: 0,
};

const LOADING_MESSAGES = [
  "Rendering reality...",
  "Asking the pixels nicely...",
  "Convincing photons to cooperate...",
  "Downloading more RAM...",
  "Bribing the server hamsters...",
  "Untangling the internet...",
  "Waiting for the universe to buffer...",
  "Teaching AI to see...",
  "Politely requesting data...",
  "Summoning images from the void...",
];

function LoadingPlaceholder() {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="loading-placeholder">
      <div className="loading-spinner" />
      <p className="loading-message">{LOADING_MESSAGES[messageIndex]}</p>
      <p className="loading-hint">WASD to move • Q/E to rotate • Space/Shift for altitude</p>
    </div>
  );
}

function normalizeYaw(yaw: number): number {
  const normalized = yaw % 360;
  return normalized < 0 ? normalized + 360 : normalized;
}

export function ManualPage() {
  const [pose, setPose] = useState<Pose>(initialPose);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Crossfade state: two image layers that alternate
  const [activeLayer, setActiveLayer] = useState<0 | 1>(0);
  const [imageSources, setImageSources] = useState<[string, string]>(["", ""]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    fetchImageForPose(pose)
      .then((src) => {
        if (!cancelled) {
          // Set new image on the inactive layer, then crossfade to it
          const nextLayer = activeLayer === 0 ? 1 : 0;
          setImageSources((prev) => {
            const next: [string, string] = [...prev];
            next[nextLayer] = src;
            return next;
          });

          // Wait a frame for the image to be set, then switch active layer
          requestAnimationFrame(() => {
            if (!cancelled) {
              setActiveLayer(nextLayer);
            }
          });
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
          // Keep showing loading placeholder or last valid image on error
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [pose]); // eslint-disable-line react-hooks/exhaustive-deps

  const poseLabel = useMemo(
    () =>
      `x: ${pose.x.toFixed(2)} | y: ${pose.y.toFixed(2)} | z: ${pose.z.toFixed(2)} | yaw: ${pose.yaw.toFixed(0)}°`,
    [pose],
  );

  const moveByYaw = useCallback((step: number) => {
    setPose((prev) => {
      const radians = (prev.yaw * Math.PI) / 180;
      return {
        ...prev,
        x: prev.x + Math.cos(radians) * step,
        y: prev.y + Math.sin(radians) * step,
      };
    });
  }, []);

  // Strafe left/right (perpendicular to yaw direction)
  const strafeByYaw = useCallback((step: number) => {
    setPose((prev) => {
      const radians = (prev.yaw * Math.PI) / 180;
      // Perpendicular direction: rotate 90 degrees
      return {
        ...prev,
        x: prev.x + Math.cos(radians + Math.PI / 2) * step,
        y: prev.y + Math.sin(radians + Math.PI / 2) * step,
      };
    });
  }, []);

  const rotateYaw = useCallback((delta: number) => {
    setPose((prev) => ({
      ...prev,
      yaw: normalizeYaw(prev.yaw + delta),
    }));
  }, []);

  const moveUp = useCallback(() => {
    setPose((prev) => ({ ...prev, z: prev.z + VERTICAL_STEP }));
  }, []);

  const moveDown = useCallback(() => {
    setPose((prev) => ({ ...prev, z: prev.z - VERTICAL_STEP }));
  }, []);

  // Keyboard controls
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case 'w':
          e.preventDefault();
          moveByYaw(MOVE_STEP);
          break;
        case 's':
          e.preventDefault();
          moveByYaw(-MOVE_STEP);
          break;
        case 'a':
          e.preventDefault();
          strafeByYaw(MOVE_STEP);
          break;
        case 'd':
          e.preventDefault();
          strafeByYaw(-MOVE_STEP);
          break;
        case 'q':
          e.preventDefault();
          rotateYaw(-YAW_STEP_DEGREES);
          break;
        case 'e':
          e.preventDefault();
          rotateYaw(YAW_STEP_DEGREES);
          break;
        case ' ':
          e.preventDefault();
          moveUp();
          break;
        case 'shift':
          e.preventDefault();
          moveDown();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [moveByYaw, strafeByYaw, rotateYaw, moveUp, moveDown]);

  return (
    <section className="manual-page">
      <div className="status-bar">
        <span className="pose">{poseLabel}</span>
        {loading && <span className="status">Loading image...</span>}
        {!loading && error && <span className="status error">{error}</span>}
      </div>

      <div className="viewport-card">
        {/* Show loading placeholder when no images loaded yet */}
        {!imageSources[0] && !imageSources[1] ? (
          <LoadingPlaceholder />
        ) : (
          <div className="viewport-crossfade">
            <img
              className={`viewport-image crossfade-layer ${activeLayer === 0 ? 'active' : ''}`}
              src={imageSources[0]}
              alt="Rendered world view"
            />
            <img
              className={`viewport-image crossfade-layer ${activeLayer === 1 ? 'active' : ''}`}
              src={imageSources[1]}
              alt="Rendered world view"
            />
          </div>
        )}
        <ViewportControls
          onForward={() => moveByYaw(MOVE_STEP)}
          onBackward={() => moveByYaw(-MOVE_STEP)}
          onLeft={() => strafeByYaw(MOVE_STEP)}
          onRight={() => strafeByYaw(-MOVE_STEP)}
          onUp={moveUp}
          onDown={moveDown}
          onTurnLeft={() => rotateYaw(-YAW_STEP_DEGREES)}
          onTurnRight={() => rotateYaw(YAW_STEP_DEGREES)}
        />
      </div>
    </section>
  );
}

