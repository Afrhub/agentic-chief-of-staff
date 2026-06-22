"""Pull business signals from an MCP connector (Model Context Protocol).

A connected integration with config kind="mcp" declares {mcp_server, tool,
maps_to, confidence}. This module calls that server's tool and maps each
returned row to an AlertSignal — so adding a tool is config, not adapter code,
which is what lets dCern span industries.

Activation: needs the official `mcp` SDK (`pip install mcp`). It is lazily
imported so the app boots and all existing collectors run without it;
configuring an MCP source without the SDK installed surfaces a clear, caught
error on that one source's sync only.

ponytail: the streamable-HTTP transport follows the SDK's documented client
pattern; the row->signal mapping below is unit-tested with a fake result.
Lighting up a live pull needs a real connector URL + token.
"""
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def collect(server_url, token, tool, signal_type, confidence=0.8, args=None):
    """Call the MCP tool, map its rows to AlertSignals. Raises on transport
    error so the caller marks that source's sync failed."""
    rows = _fetch_tool_rows(server_url, token, tool, args or {})
    return rows_to_signals(rows, signal_type, confidence)


def _fetch_tool_rows(server_url, token, tool, args):
    return asyncio.run(_fetch_async(server_url, token, tool, args))


async def _fetch_async(server_url, token, tool, args):
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as e:
        raise RuntimeError(
            "MCP source configured but the `mcp` SDK is not installed (pip install mcp)."
        ) from e

    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with streamablehttp_client(server_url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            return _rows_from_result(result)


def _rows_from_result(result) -> list:
    """Normalise an MCP tool result into a list of dict rows. Prefers
    structuredContent; falls back to text content blocks."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        for key in ("items", "results", "data", "rows"):
            if isinstance(structured.get(key), list):
                return list(structured[key])
        return [structured]
    rows = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            rows.append({"text": text})
    return rows


def rows_to_signals(rows: list, signal_type: str, confidence: float = 0.8) -> list:
    from coordinator import AlertSignal
    return [
        AlertSignal(
            type=signal_type,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            data=(r if isinstance(r, dict) else {"value": r}),
        )
        for r in rows
    ]


if __name__ == "__main__":
    # ponytail self-check: result-normalisation + mapping (no live server needed).
    # Put backend/ on the path so `from coordinator import` resolves when this
    # file is run directly (in-app it's imported with backend/ already on path).
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    class _Structured:
        structuredContent = {"items": [{"id": 1}, {"id": 2}]}
        content = []

    class _Text:
        structuredContent = None
        content = [type("B", (), {"text": "hello"})()]

    assert _rows_from_result(_Structured()) == [{"id": 1}, {"id": 2}]
    assert _rows_from_result(_Text()) == [{"text": "hello"}]
    sigs = rows_to_signals([{"a": 1}, "x"], "support_spike", 0.8)
    assert len(sigs) == 2 and sigs[0].type == "support_spike" and sigs[0].confidence == 0.8
    assert sigs[1].data == {"value": "x"}
    print("mcp_adapter self-check ok")
