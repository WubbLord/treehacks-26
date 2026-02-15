import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useAgentSession } from "../hooks/useAgentSession";
import { QueryInput } from "../components/QueryInput";
import { AgentCard } from "../components/AgentCard";
import { AgentTrajectoryMap } from "../components/AgentTrajectoryMap";
import { DEFAULT_AGENT_COUNT } from "../config";

const STATUS_LABELS: Record<string, string> = {
  idle: "READY",
  running: "SEARCHING...",
  complete: "COMPLETE",
  error: "ERROR",
};

export function AgentPage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();

  const {
    sessionId,
    sessionStatus,
    agents,
    winnerAgentId,
    error,
    selectedAgentId,
    startSession,
    joinSession,
    cancelSession,
    selectAgent,
  } = useAgentSession();

  // Auto-join session from URL on mount
  useEffect(() => {
    if (urlSessionId && sessionStatus === "idle") {
      joinSession(urlSessionId);
    }
  }, [urlSessionId, sessionStatus, joinSession]);

  // Update URL when a new session is created from the query form
  useEffect(() => {
    if (sessionId && !urlSessionId) {
      window.history.replaceState(null, "", `/agent/${sessionId}`);
    }
  }, [sessionId, urlSessionId]);

  const agentList = useMemo(() => Array.from(agents.values()), [agents]);
  const selectedAgent =
    selectedAgentId !== null ? agents.get(selectedAgentId) : undefined;
  const latestStep = selectedAgent?.steps[selectedAgent.steps.length - 1];

  const trajectories = useMemo(
    () =>
      agentList.map((a) => ({
        agentId: a.agentId,
        points: a.trajectory.map((t) => ({ x: t.x, y: t.y, step: t.step })),
        isWinner: a.agentId === winnerAgentId,
      })),
    [agentList, winnerAgentId],
  );

  const handleStart = (query: string) => {
    startSession(query, DEFAULT_AGENT_COUNT);
  };

  // Hide query form when viewing a shared session link
  const showQueryForm =
    !urlSessionId &&
    (sessionStatus === "idle" ||
      sessionStatus === "complete" ||
      sessionStatus === "error");

  return (
    <section className="agent-page">
      {/* Status bar */}
      <div className="status-bar">
        <span className="pose">AGENT MODE</span>
        <span className={`status ${sessionStatus === "error" ? "error" : ""}`}>
          {error || STATUS_LABELS[sessionStatus] || sessionStatus.toUpperCase()}
        </span>
      </div>

      {/* Query input */}
      {showQueryForm && (
        <QueryInput onSubmit={handleStart} disabled={false} />
      )}

      {/* Main content — visible when session has started */}
      {sessionStatus !== "idle" && (
        <>
          {/* Viewport */}
          <div className="agent-viewport">
            <div className="viewport-card">
              {latestStep ? (
                <>
                  <img
                    className="viewport-image"
                    src={latestStep.imageSrc}
                    alt="Agent view"
                  />

                  {/* Reasoning overlay */}
                  <div className="agent-reasoning-overlay">
                    {latestStep.reasoning}
                  </div>

                  {/* Trajectory map overlay */}
                  {trajectories.some((t) => t.points.length > 0) && (
                    <div className="agent-map-overlay">
                      <AgentTrajectoryMap trajectories={trajectories} />
                    </div>
                  )}

                  {/* Found banner */}
                  {selectedAgent?.status === "found" && (
                    <div className="agent-found-banner">TARGET FOUND</div>
                  )}
                </>
              ) : (
                <div className="loading-placeholder">
                  <div className="loading-spinner" />
                  <p className="loading-message">Agents initializing...</p>
                </div>
              )}
            </div>
          </div>

          {/* Agent cards strip */}
          {agentList.length > 0 && (
            <div className="agent-cards-strip">
              {agentList.map((agent) => (
                <AgentCard
                  key={agent.agentId}
                  agent={agent}
                  isWinner={agent.agentId === winnerAgentId}
                  isSelected={agent.agentId === selectedAgentId}
                  onClick={() => selectAgent(agent.agentId)}
                />
              ))}
            </div>
          )}

          {/* Controls bar */}
          <div className="agent-controls-bar">
            {sessionStatus === "running" && !urlSessionId && (
              <button className="replay-btn" onClick={cancelSession}>
                CANCEL
              </button>
            )}
            {sessionStatus === "complete" && winnerAgentId !== null && (
              <span className="agent-success-label">
                AGENT {winnerAgentId} FOUND TARGET
              </span>
            )}
            {sessionStatus === "complete" && winnerAgentId === null && (
              <span className="agent-success-label" style={{ color: "var(--swiss-black)" }}>
                NO TARGET FOUND
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}
