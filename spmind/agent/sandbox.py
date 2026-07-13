"""Execution guardrails for SP-Mind (the ``--sandbox`` flag).

Registers a ``PreToolUse`` hook that blocks obviously destructive shell
commands before they run. This is a policy layer on top of the SDK permission
system — defense-in-depth for autonomous runs (``--dangerously-skip-permissions``),
not a substitute for OS-level isolation.

The SDK also ships a native OS-level sandbox (``ClaudeAgentOptions.sandbox``);
we intentionally use a command-level deny-list here because the imaging tools
must reach the Docker/Singularity runtime, which a strict OS sandbox can break.
"""

from __future__ import annotations

import re
from typing import Any

from claude_agent_sdk import HookMatcher

# (pattern, human-readable reason). Kept deliberately conservative: only
# commands that are almost never legitimate inside an analysis workflow.
_BLOCKED: list[tuple[re.Pattern[str], str]] = [
    # rm with a recursive/force flag targeting a root or home path
    # (handles /, /*, ~, ~/, $HOME, $HOME/ with an optional trailing slash).
    (re.compile(r"\brm\b[^|;&\n]*\s-[a-zA-Z]*[rf][a-zA-Z]*\b[^|;&\n]*?\s(/\*|/|~|\$HOME)/?(\s|$)"), "recursive delete of a root/home path"),
    (re.compile(r":\(\)\s*\{.*\|\s*:"), "fork bomb"),
    (re.compile(r"\bmkfs\b"), "filesystem format"),
    (re.compile(r"\bdd\b.*\bof=/dev/"), "raw write to a block device"),
    (re.compile(r">\s*/dev/(sd|nvme|disk)"), "overwrite of a block device"),
    (re.compile(r"\bchmod\s+-R\s+777\s+/(\s|$)"), "world-writable chmod on /"),
    (re.compile(r"\b(shutdown|reboot|halt|poweroff)\b"), "host power/state change"),
    (re.compile(r"\bcurl\b.*\|\s*(sudo\s+)?(ba)?sh\b"), "pipe-to-shell of remote script"),
    (re.compile(r"\bwget\b.*\|\s*(sudo\s+)?(ba)?sh\b"), "pipe-to-shell of remote script"),
    (re.compile(r"\bgit\s+push\b.*--force"), "force push"),
]


async def _guardrail_hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
    """Deny destructive Bash commands; allow everything else."""
    command = (input_data.get("tool_input") or {}).get("command", "") or ""
    for pattern, reason in _BLOCKED:
        if pattern.search(command):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"SP-Mind sandbox blocked a dangerous command ({reason}). "
                        f"Command: {command.strip()[:200]}"
                    ),
                }
            }
    return {}


def build_sandbox_hooks() -> dict[str, list[HookMatcher]]:
    """Return a hooks dict enforcing the command guardrails on the Bash tool."""
    return {"PreToolUse": [HookMatcher(matcher="Bash", hooks=[_guardrail_hook])]}
