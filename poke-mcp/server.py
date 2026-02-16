#!/usr/bin/env python3
"""Keryx MCP Server – Ask about a building and get answers from AI exploration agents."""

import json
import os
from urllib.parse import urlencode

import httpx
from fastmcp import FastMCP, Context

AGENT_STREAM_URL = os.environ.get(
    "AGENT_STREAM_URL",
    "https://zhangbrwubb--keryx-agents-stream-agents.modal.run",
)
FRONTEND_URL = os.environ.get(
    "FRONTEND_URL", "https://1996-68-65-169-134.ngrok-free.app"
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
    await ctx.info(f"Launching {num_agents} agent(s) to search for: {query}")
    await ctx.report_progress(0, 1)

    # Send viewer link so the user can watch live
    viewer_params = urlencode({"q": query, "n": num_agents})
    viewer_url = f"{FRONTEND_URL}/agent?{viewer_params}"
    await ctx.info(f"Watch the exploration live: {viewer_url}")

    # Consume the single-POST SSE stream (same endpoint the frontend uses)
    result_description = None
    result_found = False
    max_step_seen = 0
    total_steps = 15
    agents_active = set()
    agents_finished = set()

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        async with client.stream(
            "POST",
            AGENT_STREAM_URL,
            json={
                "query": query,
                "num_agents": num_agents,
                "start_x": 0.0,
                "start_y": 0.0,
                "start_z": 0.0,
                "start_yaw": 0.0,
            },
            headers={"Content-Type": "application/json"},
        ) as stream:
            buffer = ""
            async for chunk in stream.aiter_text():
                buffer += chunk
                lines = buffer.split("\n")
                buffer = lines.pop()

                for line in lines:
                    trimmed = line.strip()
                    if not trimmed.startswith("data: "):
                        continue
                    json_str = trimmed[6:]
                    if json_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    if event_type == "agent_started":
                        agent_id = event.get("agent_id")
                        agents_active.add(agent_id)
                        pose = event.get("start_pose", {})
                        await ctx.info(
                            f"Agent {agent_id} started at "
                            f"({pose.get('x', 0):.1f}, {pose.get('y', 0):.1f}, "
                            f"{pose.get('z', 0):.1f}, yaw={pose.get('yaw', 0):.0f}°) "
                            f"[{len(agents_active)} agent(s) active]"
                        )

                    elif event_type == "agent_step":
                        step = event.get("step", 0)
                        agent_id = event.get("agent_id", "?")
                        reasoning = event.get("reasoning", "")
                        action = event.get("action", "move")
                        pose = event.get("pose", {})
                        t = event.get("total_steps", total_steps)
                        if t:
                            total_steps = t

                        if step > max_step_seen:
                            max_step_seen = step
                            await ctx.report_progress(step, total_steps)

                        pos_str = (
                            f"({pose.get('x', 0):.1f}, {pose.get('y', 0):.1f}, "
                            f"yaw={pose.get('yaw', 0):.0f}°)"
                        )
                        await ctx.info(
                            f"Agent {agent_id} step {step}/{total_steps} "
                            f"@ {pos_str} [{action}]: {reasoning}"
                        )

                    elif event_type == "agent_found":
                        agent_id = event.get("agent_id")
                        result_found = True
                        result_description = event.get("description", "")
                        steps_taken = event.get("steps", "?")
                        agents_finished.add(agent_id)
                        await ctx.info(
                            f"Agent {agent_id} FOUND TARGET after {steps_taken} steps: "
                            f"{result_description}"
                        )

                    elif event_type == "agent_done":
                        agent_id = event.get("agent_id")
                        steps_taken = event.get("steps", "?")
                        agents_finished.add(agent_id)
                        remaining = len(agents_active) - len(agents_finished)
                        await ctx.info(
                            f"Agent {agent_id} finished after {steps_taken} steps "
                            f"(no target) — {remaining} agent(s) still searching"
                        )

                    elif event_type == "session_complete":
                        if not result_description:
                            result_description = event.get("description", "")
                        break

                    elif event_type == "error":
                        msg = event.get("message", "Unknown error")
                        agent_id = event.get("agent_id")
                        prefix = f"Agent {agent_id}" if agent_id is not None else "Session"
                        await ctx.error(f"{prefix} error: {msg}")

    await ctx.report_progress(1, 1)

    # Final answer
    if result_found and result_description:
        return (
            f"Found it!\n\n"
            f"{result_description}\n\n"
            f"Watch the exploration: {viewer_url}"
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
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8765)
