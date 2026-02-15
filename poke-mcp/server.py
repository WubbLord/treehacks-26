#!/usr/bin/env python3
"""Keryx MCP Server – Ask about a building and get answers from AI exploration agents."""

import asyncio
import os
import re

from fastmcp import FastMCP, Context

AGENT_STREAM_URL = os.environ.get(
    "AGENT_STREAM_URL",
    "https://zhangbrwubb--keryx-agents-stream.modal.run",
)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://1996-68-65-169-134.ngrok-free.app")
PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT", "/Users/rohin/Desktop/code/treehacks-26"
)

mcp = FastMCP("Keryx")


@mcp.tool()
async def explore_building(
    query: str, num_agents: int = 2, *, ctx: Context
) -> str:
    """Search a building to answer a question. Launches AI vision agents that
    explore the building and report back what they find.

    Args:
        query: What to find (e.g. "where is the nearest bathroom", "find the fire exit")
        num_agents: Number of parallel search agents (default 2)
    """
    viewer_url = f"{FRONTEND_URL}/agent"

    await ctx.info(f"Launching {num_agents} agent(s) to search for: {query}")
    await ctx.info(f"Watch the exploration live: {viewer_url}")
    await ctx.report_progress(0, 1)

    # Run agents via Modal CLI so we get streamed container logs
    proc = await asyncio.create_subprocess_exec(
        "modal",
        "run",
        f"{PROJECT_ROOT}/agents/agents.py",
        "--query", query,
        "--n", str(num_agents),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    result_description = None
    result_found = False
    total_steps = 15
    max_step_seen = 0
    in_result_block = False

    async for raw_line in proc.stdout:
        line = raw_line.decode(errors="replace").strip()
        if not line:
            continue

        # --- relay interesting updates to Poke ---

        # Agent spawned
        if line.startswith("Spawning agent"):
            await ctx.info(line)

        # Agent step (from container logs)
        step_match = re.search(
            r"\[Agent (\d+)\]\s+Step (\d+)", line
        )
        if step_match:
            agent_id = step_match.group(1)
            step = int(step_match.group(2))
            if step > max_step_seen:
                max_step_seen = step
                await ctx.report_progress(step, total_steps)
            await ctx.info(f"Agent {agent_id} – step {step}/{total_steps}")

        # Agent reasoning
        if "LLM reasoning:" in line:
            reasoning = line.split("LLM reasoning:", 1)[1].strip()
            # Try to parse the JSON reasoning field out of the action JSON
            try:
                import json
                action = json.loads(reasoning)
                reasoning = action.get("reasoning", reasoning)
            except Exception:
                pass
            agent_prefix = ""
            m = re.search(r"\[Agent (\d+)\]", line)
            if m:
                agent_prefix = f"Agent {m.group(1)}: "
            await ctx.info(f"{agent_prefix}{reasoning}")

        # Agent found target
        if "*** FOUND" in line:
            await ctx.info(line)

        # Polling result from main()
        if "found the target" in line and ">>>" in line:
            await ctx.info(line.strip("> \n"))

        # Final result block
        if line.startswith("RESULT:"):
            in_result_block = True
            result_found = "found the target" in line
            await ctx.info(line)
        elif in_result_block and line.strip().startswith("description:"):
            result_description = line.split("description:", 1)[1].strip()
            in_result_block = False

    await proc.wait()
    await ctx.report_progress(1, 1)

    # --- final answer ---
    if result_found and result_description:
        return (
            f"Found it!\n\n"
            f"{result_description}\n\n"
            f"Watch the full exploration: {viewer_url}"
        )
    elif result_description:
        return (
            f"The agents searched the building but couldn't find \"{query}\".\n\n"
            f"Best effort: {result_description}\n\n"
            f"See what they explored: {viewer_url}"
        )
    else:
        return (
            f"Search completed but no clear result was returned.\n\n"
            f"Watch the exploration: {viewer_url}"
        )


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8765)
