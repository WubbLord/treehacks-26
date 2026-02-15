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

const PLACEHOLDER_IMAGE = `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700">
    <rect width="1200" height="700" fill="#d8e2ef"/>
    <rect x="36" y="36" width="1128" height="628" rx="20" fill="#eef3f9" stroke="#b8c4d7" stroke-width="3"/>
    <text x="600" y="330" text-anchor="middle" font-family="Roboto, Arial, sans-serif" font-size="42" fill="#5b6f89">Image placeholder</text>
    <text x="600" y="382" text-anchor="middle" font-family="Roboto, Arial, sans-serif" font-size="23" fill="#7a8ca3">/getImages unavailable or empty</text>
  </svg>`,
)}`;

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
          const nextLayer = activeLayer === 0 ? 1 : 0;
          setImageSources((prev) => {
            const next: [string, string] = [...prev];
            next[nextLayer] = PLACEHOLDER_IMAGE;
            return next;
          });
          setActiveLayer(nextLayer);
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

  const rotateYaw = useCallback((delta: number) => {
    setPose((prev) => ({
      ...prev,
      yaw: normalizeYaw(prev.yaw + delta),
    }));
  }, []);

  return (
    <section className="manual-page">
      <div className="status-bar">
        <span className="pose">{poseLabel}</span>
        {loading && <span className="status">Loading image...</span>}
        {!loading && error && <span className="status error">{error}</span>}
      </div>

      <div className="viewport-card">
        {/* Two image layers for crossfade effect */}
        <div className="viewport-crossfade">
          <img
            className={`viewport-image crossfade-layer ${activeLayer === 0 ? 'active' : ''}`}
            src={imageSources[0] || PLACEHOLDER_IMAGE}
            alt="Rendered world view"
          />
          <img
            className={`viewport-image crossfade-layer ${activeLayer === 1 ? 'active' : ''}`}
            src={imageSources[1] || PLACEHOLDER_IMAGE}
            alt="Rendered world view"
          />
        </div>
        <ViewportControls
          onForward={() => moveByYaw(MOVE_STEP)}
          onBackward={() => moveByYaw(-MOVE_STEP)}
          onUp={() =>
            setPose((prev) => ({
              ...prev,
              z: prev.z + VERTICAL_STEP,
            }))
          }
          onDown={() =>
            setPose((prev) => ({
              ...prev,
              z: prev.z - VERTICAL_STEP,
            }))
          }
          onTurnLeft={() => rotateYaw(-YAW_STEP_DEGREES)}
          onTurnRight={() => rotateYaw(YAW_STEP_DEGREES)}
        />
      </div>
    </section>
  );
}

