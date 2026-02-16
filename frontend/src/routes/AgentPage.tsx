import { useEffect, useMemo, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useAgentSession } from "../hooks/useAgentSession";
import { QueryInput } from "../components/QueryInput";
import { MAX_AGENT_STEPS } from "../config";

const STATUS_LABELS: Record<string, string> = {
  idle: "READY",
  running: "SEARCHING...",
  complete: "COMPLETE",
  error: "ERROR",
};

const AGENT_STATUS_LABELS: Record<string, string> = {
  waiting: "WAITING",
  exploring: "EXPLORING",
  found: "FOUND",
  done: "DONE",
  error: "ERROR",
};

export function AgentPage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId?: string }>();
  const [searchParams] = useSearchParams();
  const autoStarted = useRef(false);

  const {
    sessionId,
    sessionStatus,
    agents,
    winnerAgentId,
    error,
    startSession,
    joinSession,
    cancelSession,
  } = useAgentSession();

  // Auto-join session from URL on mount
  useEffect(() => {
    if (urlSessionId && sessionStatus === "idle") {
      joinSession(urlSessionId);
    }
  }, [urlSessionId, sessionStatus, joinSession]);

  // Auto-start from query params: /agent?q=find+bathroom&n=2
  useEffect(() => {
    if (autoStarted.current) return;
    const q = searchParams.get("q");
    if (q && sessionStatus === "idle") {
      autoStarted.current = true;
      const n = parseInt(searchParams.get("n") ?? "2", 10);
      startSession(q, isNaN(n) ? 2 : Math.max(1, Math.min(8, n)));
    }
  }, [searchParams, sessionStatus, startSession]);

  // Update URL when a new session is created from the query form
  useEffect(() => {
    if (sessionId && !urlSessionId) {
      window.history.replaceState(null, "", `/agent/${sessionId}`);
    }
  }, [sessionId, urlSessionId]);

  const agentList = useMemo(() => Array.from(agents.values()), [agents]);

  const handleStart = (query: string, numAgents: number) => {
    startSession(query, numAgents);
  };

  // Hide query form when viewing a shared session link or auto-started from params
  const fromLink = !!urlSessionId || !!searchParams.get("q");
  const showQueryForm =
    !fromLink &&
    (sessionStatus === "idle" ||
      sessionStatus === "complete" ||
      sessionStatus === "error");

  // Determine grid columns based on agent count
  const gridCols =
    agentList.length <= 1 ? 1 : agentList.length <= 4 ? 2 : 3;

  return (
    <section className="agent-page">
      {/* Status bar */}
      <div className="status-bar">
        <span className="pose">AGENT MODE</span>
        <span className={`status ${sessionStatus === "error" ? "error" : ""}`}>
          {error || STATUS_LABELS[sessionStatus] || sessionStatus.toUpperCase()}
        </span>
        {sessionStatus === "running" && !fromLink && (
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

      {/* Query input */}
      {showQueryForm && (
        <QueryInput onSubmit={handleStart} disabled={false} />
      )}

      {/* Agent feed grid — visible when session has started */}
      {sessionStatus !== "idle" && (
        <div
          className="agent-feed-grid"
          style={{ "--grid-cols": gridCols } as React.CSSProperties}
        >
          {agentList.length === 0 && (
            <div className="agent-feed-loading">
              <div className="loading-spinner" />
              <p className="loading-message">Agents initializing...</p>
            </div>
          )}
          {agentList.map((agent) => {
            const latestStep = agent.steps[agent.steps.length - 1];
            const stepCount = agent.steps.length;
            const progress = (stepCount / MAX_AGENT_STEPS) * 100;
            const isWinner = agent.agentId === winnerAgentId;

            return (
              <div
                key={agent.agentId}
                className={`agent-feed-panel${isWinner ? " winner" : ""}`}
              >
                {/* Header */}
                <div className="agent-feed-header">
                  <span className="agent-feed-id">AGENT {agent.agentId}</span>
                  {latestStep && (
                    <span className="agent-feed-pose">
                      ({latestStep.pose.x.toFixed(1)}, {latestStep.pose.y.toFixed(1)}, {latestStep.pose.z.toFixed(1)}, {latestStep.pose.yaw.toFixed(0)}&deg;)
                    </span>
                  )}
                  <span className={`agent-feed-status ${agent.status}`}>
                    {AGENT_STATUS_LABELS[agent.status] ?? agent.status.toUpperCase()}
                  </span>
                  <span className="agent-feed-steps">
                    {stepCount}/{MAX_AGENT_STEPS}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="agent-feed-progress">
                  <div
                    className="agent-feed-progress-fill"
                    style={{ width: `${progress}%` }}
                  />
                </div>

                {/* Camera feed */}
                <div className="agent-feed-image">
                  {latestStep ? (
                    <>
                      <img
                        src={latestStep.imageSrc}
                        alt={`Agent ${agent.agentId} view`}
                      />
                      {/* Reasoning overlay */}
                      <div className="agent-feed-reasoning">
                        {latestStep.reasoning}
                      </div>
                      {/* Found banner */}
                      {agent.status === "found" && (
                        <div className="agent-found-banner">TARGET FOUND</div>
                      )}
                    </>
                  ) : (
                    <div className="agent-feed-waiting">
                      <div className="loading-spinner" />
                      <span>WAITING FOR FEED...</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
