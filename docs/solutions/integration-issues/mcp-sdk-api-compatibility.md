---
title: "MCP SDK 1.x NotificationOptions Import Fix"
category: integration-issues
tags: [mcp, python, api-breaking-change]
date: 2026-04-11
module: avatar/mcp_server
---

## Problem

MCP server fails to start with:
```
AttributeError: module 'mcp.types' has no attribute 'NotificationOptions'
Did you mean: 'NotificationParams'?
```

## Root Cause

MCP SDK v1.x moved `NotificationOptions` from `mcp.types` to `mcp.server.lowlevel.server`.

## Solution

Change the import:

```python
# ❌ WRONG (old API)
import mcp.types as types
notification_options = types.NotificationOptions()

# ✅ CORRECT (MCP SDK 1.x)
from mcp.server.lowlevel.server import NotificationOptions
notification_options = NotificationOptions()
```

## Files Modified

- `avatar/mcp_server/server.py` - Lines 23 and 668

## Verification

```bash
source venv/bin/activate
python -m avatar.mcp_server.server
# Should start without errors
```

## References

- MCP SDK version: 1.x
- Error location: server.py initialization
- Related: get_capabilities() method
