"""Running totals of a `--usage` analysis (D-050). Counts and sizes only, never content."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

PREVIEW_CHARS = 60
TOP = 10


class UsageTotals:
    """Running totals of one `--usage` analysis (D-050): usage per API response, injections, tools, reads."""

    def __init__(self) -> None:
        self.usage_by_id: dict[str, dict] = {}
        self.injections: dict[tuple[str, str], list] = {}
        self.tool_names: dict[str, str] = {}
        self.tools: dict[str, Counter] = defaultdict(Counter)
        self.reads: Counter = Counter()
        self.mcp_failures: Counter = Counter()
        self.compactions = 0

    @staticmethod
    def _size(content: Any) -> int:
        if isinstance(content, str):
            return len(content)
        if isinstance(content, list):
            return sum(len(c.get("text", "")) if isinstance(c, dict) else len(str(c)) for c in content)
        return 0

    def add(self, rec: dict, failed: set[str]) -> None:
        kind = rec.get("type")
        if kind == "assistant":
            self._assistant(rec.get("message") or {})
        elif kind == "user":
            self._user(rec.get("message") or {})
        elif kind == "attachment":
            self._attachment(rec.get("attachment") or {}, failed)
        elif kind == "system" and rec.get("subtype") == "compact_boundary":
            self.compactions += 1

    def _assistant(self, msg: dict) -> None:
        usage, mid = msg.get("usage"), msg.get("id")
        if isinstance(usage, dict) and mid:
            self.usage_by_id[str(mid)] = usage  # one API response may be written as several records
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                name = str(block.get("name", "?"))
                self.tool_names[str(block.get("id"))] = name
                self.tools[name]["calls"] += 1
                path = (block.get("input") or {}).get("file_path") if name == "Read" else None
                if isinstance(path, str):
                    self.reads[path] += 1

    def _user(self, msg: dict) -> None:
        content = msg.get("content")
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                name = self.tool_names.get(str(block.get("tool_use_id")), "?")
                size = self._size(block.get("content"))
                self.tools[name]["chars"] += size

    def _attachment(self, att: dict, failed: set[str]) -> None:
        kind = att.get("type")
        if kind == "hook_additional_context":
            items = att.get("content")
            text = "\n".join(str(i) for i in items) if isinstance(items, list) else str(items or "")
            key = (str(att.get("hookName") or att.get("hookEvent") or "?"), text[:PREVIEW_CHARS])
            entry = self.injections.setdefault(key, [0, 0])
            entry[0] += 1
            entry[1] += len(text) // 4
        elif kind == "deferred_tools_delta":
            for server in att.get("failedMcpServers") or []:
                if isinstance(server, dict) and server.get("name"):
                    failed.add(str(server["name"]))

    def result(self, sessions: int) -> dict:
        totals = Counter()
        for u in self.usage_by_id.values():
            totals["input"] += int(u.get("input_tokens") or 0)
            totals["output"] += int(u.get("output_tokens") or 0)
            totals["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
            totals["cache_write"] += int(u.get("cache_creation_input_tokens") or 0)
        injections = [
            {"hook": h, "preview": p, "count": c, "tokens": t}
            for (h, p), (c, t) in sorted(self.injections.items(), key=lambda kv: -kv[1][1])
        ]
        tools = [
            {"tool": n, "calls": c["calls"], "chars": c["chars"], "tokens": c["chars"] // 4}
            for n, c in sorted(self.tools.items(), key=lambda kv: -kv[1]["chars"])
        ]
        return {
            "usage_schema_version": 1,
            "sessions": sessions,
            "totals": {
                "calls": len(self.usage_by_id),
                **{k: totals[k] for k in ("input", "output", "cache_read", "cache_write")},
            },
            "compactions": self.compactions,
            "injections": injections[:TOP],
            "tools": tools[:TOP],
            "repeated_reads": [{"path": p, "count": c} for p, c in self.reads.most_common(TOP) if c > 1],
            "mcp_failures": [{"server": s, "sessions": c} for s, c in self.mcp_failures.most_common()],
        }
