#!/usr/bin/env python3
"""Wait for MCP server to be ready via JSON-RPC ping.

Reads JSON-RPC request from stdin and writes response to stdout.
Exit codes:
    0: MCP server responded with pong
    1: Invalid response or missing pong
"""
import asyncio
import json
import sys


async def main() -> int:
    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ping", "arguments": {}}}
    sys.stdout.write(json.dumps(req) + "\n")
    await asyncio.sleep(0)
    line = sys.stdin.readline()
    data = json.loads(line)
    text = data["result"]["content"][0]["text"]
    payload = json.loads(text)
    return 0 if payload.get("pong") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
