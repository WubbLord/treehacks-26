import { Bot, Zap, Target } from "lucide-react";

export function AgentPage() {
  return (
    <section className="agent-page">
      <div className="status-bar">
        <span className="pose">AGENT MODE</span>
        <span className="status">SYSTEM INITIALIZING</span>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          padding: "var(--space-16) var(--space-8)",
          gap: "var(--space-8)",
          background: "var(--swiss-muted)",
          borderBottom: "var(--border-4) solid var(--swiss-black)",
        }}
        className="swiss-grid-pattern"
      >
        <div
          style={{
            width: "120px",
            height: "120px",
            border: "var(--border-4) solid var(--swiss-black)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "var(--swiss-white)",
          }}
        >
          <Bot size={64} strokeWidth={2} />
        </div>

        <h2
          style={{
            fontSize: "clamp(2rem, 5vw, 3.5rem)",
            fontWeight: 900,
            textTransform: "uppercase",
            letterSpacing: "-0.02em",
            margin: 0,
            textAlign: "center",
          }}
        >
          AUTONOMOUS MODE
        </h2>

        <p
          style={{
            fontSize: "1.125rem",
            maxWidth: "40rem",
            textAlign: "center",
            lineHeight: 1.6,
          }}
        >
          AI-driven navigation system currently under development. The agent will
          utilize learned policies for intelligent pathfinding and autonomous
          exploration of reconstructed environments.
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "var(--space-6)",
            width: "100%",
            maxWidth: "800px",
            marginTop: "var(--space-8)",
          }}
        >
          <div
            style={{
              padding: "var(--space-6)",
              border: "var(--border-2) solid var(--swiss-black)",
              background: "var(--swiss-white)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            <Zap size={32} strokeWidth={2} />
            <h3
              style={{
                fontSize: "1rem",
                fontWeight: 900,
                textTransform: "uppercase",
                letterSpacing: "-0.01em",
                margin: 0,
              }}
            >
              REAL-TIME
            </h3>
            <p style={{ fontSize: "0.875rem", margin: 0, opacity: 0.8 }}>
              Millisecond decision latency
            </p>
          </div>

          <div
            style={{
              padding: "var(--space-6)",
              border: "var(--border-2) solid var(--swiss-black)",
              background: "var(--swiss-white)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
            }}
          >
            <Target size={32} strokeWidth={2} />
            <h3
              style={{
                fontSize: "1rem",
                fontWeight: 900,
                textTransform: "uppercase",
                letterSpacing: "-0.01em",
                margin: 0,
              }}
            >
              PRECISION
            </h3>
            <p style={{ fontSize: "0.875rem", margin: 0, opacity: 0.8 }}>
              Sub-centimeter accuracy
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

