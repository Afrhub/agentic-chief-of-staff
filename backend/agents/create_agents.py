#!/usr/bin/env python3
"""Create the dCern environment + 5 axis agents + coordinator in YOUR Anthropic
workspace, straight from the YAML configs — no `ant` install needed.

Run it where your Anthropic key lives (your machine, or the Render shell):

    ANTHROPIC_API_KEY=sk-ant-... \
      backend/.venv/bin/python backend/agents/create_agents.py

It prints the env-var lines to paste onto the dCern service (Render). Then
refresh the Claude Console → the agents appear under the workspace your key
belongs to. Creating agents is free (no inference); running sessions costs.
Re-running creates fresh objects — archive duplicates in the Console.
"""
import os
import sys

import httpx
import yaml

API = "https://api.anthropic.com/v1"
HDR = {
    "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "anthropic-version": "2023-06-01",
    "anthropic-beta": "managed-agents-2026-04-01",
    "content-type": "application/json",
}
HERE = os.path.dirname(os.path.abspath(__file__))
AXES = ["money", "customers", "comms", "meetings", "ops"]


def _load(name: str) -> dict:
    with open(os.path.join(HERE, name)) as f:
        return yaml.safe_load(f)


def _create(path: str, body: dict) -> dict:
    r = httpx.post(f"{API}/{path}", headers=HDR, json=body, timeout=60)
    if r.status_code >= 300:
        sys.exit(f"FAILED creating {path}: {r.status_code} {r.text}")
    return r.json()


def main():
    if not HDR["x-api-key"]:
        sys.exit("Set ANTHROPIC_API_KEY first (see this file's docstring).")

    env = _create("environments", _load("environment.yaml"))
    print(f"DCERN_ENV_ID={env['id']}")

    ids = []
    for axis in AXES:
        a = _create("agents", _load(f"{axis}.agent.yaml"))
        ids.append(a["id"])
        print(f"{axis.upper()}_AGENT_ID={a['id']}")

    coord = _load("coordinator.agent.yaml")
    coord["multiagent"] = {"type": "coordinator", "agents": ids}  # real roster
    c = _create("agents", coord)
    print(f"COORDINATOR_AGENT_ID={c['id']}")

    print("\n✓ Created. Set the lines above on the dCern service, then refresh the "
          "Claude Console (Managed Agents → Agents) to see them.")


if __name__ == "__main__":
    main()
