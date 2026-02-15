"""Keryx – parallel building-exploration agents powered by a vision LLM.

Usage:
    modal deploy agents/agents.py

Requires app.py to be deployed first (provides the GetImage class).
"""

import base64
import json
import uuid

import modal

# ---------------------------------------------------------------------------
# Model registry – add new vision-language models here
# ---------------------------------------------------------------------------

SUPPORTED_MODELS: dict[str, str] = {
    "qwen3-vl-2b": "Qwen/Qwen3-VL-2B-Instruct",
    # "qwen3-vl-8b": "Qwen/Qwen3-VL-8B-Instruct",
    # "qwen2.5-vl-3b": "Qwen/Qwen2.5-VL-3B-Instruct",
}
DEFAULT_MODEL = "qwen3-vl-2b"
MODEL_ID = SUPPORTED_MODELS[DEFAULT_MODEL]

MAX_STEPS = 15

# ---------------------------------------------------------------------------
# Trajectory bounds (from trajectory_postprocessed.csv) – keeps agents
# inside the mapped building volume.
# ---------------------------------------------------------------------------

BOUNDS = {
    "x": (-200, 200),
    "y": (-200, 200),
    "z": (-100, 100),
}

# ---------------------------------------------------------------------------
# Modal resources
# ---------------------------------------------------------------------------

app = modal.App("keryx-agents")

model_vol = modal.Volume.from_name("keryx-model-cache", create_if_missing=True)
cancel_dict = modal.Dict.from_name("keryx-cancel", create_if_missing=True)

MODEL_DIR = "/model-cache"


def download_model():
    """Pre-download model weights into the volume (runs at image build)."""
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_ID, local_dir=f"{MODEL_DIR}/{MODEL_ID}")


# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------

agent_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.11.0",
        "transformers",
        "qwen-vl-utils==0.0.14",
        "Pillow",
        "torch",
        "huggingface_hub",
    )
    .run_function(download_model, volumes={MODEL_DIR: model_vol})
)

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a building-exploration agent.  You navigate by requesting camera
views at specific 3D positions and yaw angles.

## World info
- yaw is in degrees (0-360).  0 = initial forward direction.
- You may move up to 2 m per step on any axis and rotate up to 90 deg.

## Your task
The user asked: "{query}"
Explore the building to find what they asked for.

## How to respond
Each turn you will receive an image from your current position.  Look at
the image, consider your trajectory so far, then output **only** a JSON
object (no markdown, no extra text) in one of these two forms:

If you have NOT found the target:
{{"action": "move", "x": <float>, "y": <float>, "z": <float>, "yaw": <float>, "reasoning": "<1-2 sentences>"}}

If you CAN SEE the target in the current image:
{{"action": "found", "description": "<describe what you see and where it is>"}}

Do NOT revisit positions you have already been to.
"""


# ---------------------------------------------------------------------------
# AgentRunner class
# ---------------------------------------------------------------------------


@app.cls(
    image=agent_image,
    gpu="H200",
    volumes={MODEL_DIR: model_vol},
    timeout=600,
    scaledown_window=300,
)
class AgentRunner:
    """Hosts the VLM and exposes send_agent for multi-turn exploration."""

    @modal.enter()
    def setup(self):
        from vllm import LLM

        self.llm = LLM(
            model=f"{MODEL_DIR}/{MODEL_ID}",
            trust_remote_code=True,
            max_model_len=16384,
            dtype="half",
            enable_prefix_caching=True,
        )
        self.get_image_cls = modal.Cls.from_name("keryx", "GetImage")

    # ------------------------------------------------------------------ #

    @modal.method()
    def send_agent(
        self,
        query: str,
        start_x: float,
        start_y: float,
        start_z: float,
        start_yaw: float,
        agent_id: int,
        session_key: str,
    ) -> dict:
        """Run one exploration agent as a continuous multi-turn conversation.

        The conversation history (messages list) is accumulated across
        turns so the LLM retains full context of every image it has seen
        and every decision it has made.  vLLM's prefix caching reuses the
        KV cache for all prior turns automatically.

        Returns dict with keys:
            found, agent_id, description, final_image_b64,
            steps, trajectory
        """
        from vllm import SamplingParams

        x, y, z, yaw = start_x, start_y, start_z, start_yaw
        trajectory: list[dict] = []
        last_image_b64 = ""
        sampling = SamplingParams(temperature=0.7, max_tokens=300)

        print(f"\n{'='*60}")
        print(f"[Agent {agent_id}] START  query={query!r}")
        print(f"[Agent {agent_id}]        pos=({x:.2f}, {y:.2f}, {z:.2f})  yaw={yaw:.1f}")
        print(f"{'='*60}")

        # Persistent conversation – system prompt is set once
        sys_text = SYSTEM_PROMPT.format(query=query)
        messages: list[dict] = [
            {"role": "system", "content": [{"type": "text", "text": sys_text}]},
        ]

        for step in range(MAX_STEPS):
            # -- cancel check -------------------------------------------
            try:
                if cancel_dict[session_key]:
                    print(f"[Agent {agent_id}] CANCELLED at step {step}")
                    return self._result(False, agent_id, "Cancelled",
                                        last_image_b64, step, trajectory)
            except KeyError:
                pass

            # -- call getImageRemote ------------------------------------
            print(f"\n[Agent {agent_id}] Step {step}")
            print(f"[Agent {agent_id}]   getImageRemote(x={x:.4f}, y={y:.4f}, z={z:.4f}, yaw={yaw:.2f})")

            get_image = self.get_image_cls()
            result = get_image.getImageRemote.remote(x, y, z, yaw)

            src_idx = result["source_idx"]
            src_ts = result.get("source_timestamp_s", result.get("source_filename", "?"))
            img_bytes: bytes = result["image_png"]
            img_b64 = base64.b64encode(img_bytes).decode("ascii")
            last_image_b64 = img_b64

            print(f"[Agent {agent_id}]   -> source_idx={src_idx}  source={src_ts}  image_bytes={len(img_bytes)}")

            trajectory.append({
                "x": x, "y": y, "z": z, "yaw": yaw,
                "step": step, "source": src_ts,
            })

            # -- append new user turn with the image --------------------
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Position: ({x:.2f}, {y:.2f}, {z:.2f}), yaw={yaw:.1f}. "
                            f"Step {step}/{MAX_STEPS}."
                        ),
                    },
                ],
            })

            # -- VLM inference (full conversation, KV cache reused) -----
            outputs = self.llm.chat(messages, sampling_params=sampling)
            raw_text = outputs[0].outputs[0].text.strip()
            print(f"[Agent {agent_id}]   LLM reasoning: {raw_text}")

            # -- append assistant response to conversation history ------
            messages.append({"role": "assistant", "content": raw_text})

            # -- parse JSON action --------------------------------------
            action = self._parse_action(raw_text)
            if action is None:
                print(f"[Agent {agent_id}]   (parse failed – rotating 30 deg)")
                yaw = (yaw + 30) % 360
                continue

            print(f"[Agent {agent_id}]   Parsed action: {action}")

            if action.get("action") == "found":
                desc = action.get("description", "")
                print(f"\n[Agent {agent_id}] *** FOUND at step {step}: {desc} ***\n")
                return self._result(True, agent_id, desc,
                                    last_image_b64, step, trajectory)

            if action.get("action") == "move":
                x = self._clamp(float(action.get("x", x)), *BOUNDS["x"])
                y = self._clamp(float(action.get("y", y)), *BOUNDS["y"])
                z = self._clamp(float(action.get("z", z)), *BOUNDS["z"])
                yaw = float(action.get("yaw", yaw)) % 360
            else:
                yaw = (yaw + 30) % 360

        print(f"[Agent {agent_id}] Max steps reached")
        return self._result(False, agent_id,
                            "Max steps reached without finding target",
                            last_image_b64, MAX_STEPS, trajectory)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _result(found, agent_id, description, image_b64, steps, trajectory):
        return {
            "found": found,
            "agent_id": agent_id,
            "description": description,
            "final_image_b64": image_b64,
            "steps": steps,
            "trajectory": trajectory,
        }

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    @staticmethod
    def _parse_action(text: str) -> dict | None:
        """Best-effort JSON extraction from LLM output."""
        # Strip markdown fences if present
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
        # Try to find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# spawn_agent – Modal function that runs a single agent
# ---------------------------------------------------------------------------


@app.function(image=agent_image, gpu="H200", volumes={MODEL_DIR: model_vol}, timeout=600)
def spawn_agent(
    query: str,
    x: float,
    y: float,
    z: float,
    yaw: float,
    agent_id: int,
    session_key: str,
) -> dict:
    """Run a single exploration agent as a standalone Modal function.

    This is the unit of parallelism — call .spawn() N times from main()
    to search concurrently.

    Returns dict with keys:
        found, agent_id, description, final_image_b64, steps, trajectory
    """
    runner = AgentRunner()
    return runner.send_agent.remote(
        query=query,
        start_x=x, start_y=y, start_z=z,
        start_yaw=yaw,
        agent_id=agent_id,
        session_key=session_key,
    )


# ---------------------------------------------------------------------------
# Local entrypoint – launches N agents in parallel, first success wins
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def main(
    query: str = "find the nearest bathroom",
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
    yaw: float = 0.0,
    n: int = 1,
):
    """Launch n parallel agents.  First one to find the target wins.

    Usage:
        modal run agents/agents.py --query "find the nearest bathroom" --n 3
    """
    import time

    session_key = str(uuid.uuid4())
    cancel_dict[session_key] = False

    print(f"\n{'#'*60}")
    print(f"# Launching {n} agent(s)  query={query!r}")
    print(f"# start=({x:.2f}, {y:.2f}, {z:.2f})  yaw={yaw:.1f}")
    print(f"# session={session_key}")
    print(f"{'#'*60}\n")

    # Spawn N agents with different starting yaw offsets
    handles = []
    for i in range(n):
        agent_yaw = (yaw + (i % 2) * 180) % 360
        print(f"Spawning agent {i}  yaw={agent_yaw:.1f}")
        h = spawn_agent.spawn(
            query=query,
            x=x, y=y, z=z,
            yaw=agent_yaw,
            agent_id=i,
            session_key=session_key,
        )
        handles.append(h)

    # Poll until one agent finds the target or all finish
    completed = [False] * n
    results: list[dict | None] = [None] * n
    winner = None

    while not all(completed):
        time.sleep(2)
        for i, h in enumerate(handles):
            if completed[i]:
                continue
            try:
                r = h.get(timeout=0)
            except TimeoutError:
                continue
            except Exception as exc:
                print(f"Agent {i} errored: {exc}")
                completed[i] = True
                continue

            completed[i] = True
            results[i] = r
            print(f"\nAgent {i} finished: found={r['found']}  steps={r['steps']}")
            if r.get("description"):
                print(f"  description: {r['description']}")

            if r["found"] and winner is None:
                winner = r
                # Signal all other agents to stop
                cancel_dict[session_key] = True
                print(f"\n>>> Agent {i} found the target – cancelling others <<<\n")

    # Cleanup
    try:
        del cancel_dict[session_key]
    except KeyError:
        pass

    # Print final result
    final = winner
    if final is None:
        final = max(
            (r for r in results if r is not None),
            key=lambda r: r["steps"],
            default=None,
        )

    if final:
        print(f"\n{'='*60}")
        if final["found"]:
            print(f"RESULT: Agent {final['agent_id']} found the target in {final['steps']} steps")
        else:
            print(f"RESULT: No agent found the target. Best effort from agent {final['agent_id']}.")
        print(f"  description: {final['description']}")
        print(f"  trajectory points: {len(final['trajectory'])}")
        if final["final_image_b64"]:
            print(f"  final image: {len(final['final_image_b64'])} chars base64")
        print(f"{'='*60}\n")
    else:
        print("\nAll agents failed.")
