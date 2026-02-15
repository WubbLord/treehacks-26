#!/usr/bin/env python3
"""Keryx MCP Server – Ask about a building and get answers from AI exploration agents."""

import json
import os

import httpx
from fastmcp import FastMCP, Context

AGENT_API_URL = os.environ.get(
    "AGENT_API_URL",
    "https://zhangbrwubb--keryx-agents-api.modal.run",
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

    # Step 1: Create session via POST
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AGENT_API_URL}/sessions",
            json={
                "query": query,
                "num_agents": num_agents,
                "start_x": 0.0,
                "start_y": 0.0,
                "start_z": 0.0,
                "start_yaw": 0.0,
            },
        )
        resp.raise_for_status()
        session_id = resp.json()["session_id"]

    viewer_url = f"{FRONTEND_URL}/agent/{session_id}"
    await ctx.info(f"Watch the exploration live: {viewer_url}")

    # Step 2: Consume SSE stream via GET
    result_description = None
    result_found = False
    max_step_seen = 0
    total_steps = 15

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        async with client.stream(
            "GET",
            f"{AGENT_API_URL}/sessions/{session_id}/stream",
            headers={"Accept": "text/event-stream"},
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
                        pose = event.get("start_pose", {})
                        await ctx.info(
                            f"Agent {event['agent_id']} started at "
                            f"({pose.get('x', 0):.1f}, {pose.get('y', 0):.1f})"
                        )

                    elif event_type == "agent_step":
                        step = event.get("step", 0)
                        agent_id = event.get("agent_id", "?")
                        reasoning = event.get("reasoning", "")
                        if step > max_step_seen:
                            max_step_seen = step
                            await ctx.report_progress(step, total_steps)
                        await ctx.info(
                            f"Agent {agent_id} step {step}/{total_steps}: {reasoning}"
                        )

                    elif event_type == "agent_found":
                        result_found = True
                        result_description = event.get("description", "")
                        await ctx.info(
                            f"Agent {event.get('agent_id')} FOUND IT: "
                            f"{result_description}"
                        )

                    elif event_type == "agent_done":
                        await ctx.info(
                            f"Agent {event.get('agent_id')} finished "
                            f"without finding target"
                        )

                    elif event_type == "session_complete":
                        if not result_description:
                            result_description = event.get("description", "")
                        break

                    elif event_type == "error":
                        msg = event.get("message", "Unknown error")
                        await ctx.error(f"Error: {msg}")

    await ctx.report_progress(1, 1)

    # Final answer
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
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8765)
