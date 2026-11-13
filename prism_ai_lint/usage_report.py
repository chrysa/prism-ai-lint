"""Text rendering of a `--usage` analysis (D-050)."""

from __future__ import annotations

from prism_ai_lint._runtime import _loc


class UsageReport:
    """Render the dict returned by `UsageAnalyzer.analyze` as a short terminal report, most costly first."""

    @staticmethod
    def _n(value: int) -> str:
        for unit, size in (("M", 1_000_000), ("k", 1_000)):
            if value >= size:
                return f"{value / size:.1f}{unit}"
        return str(value)

    def render(self, data: dict, project: str) -> str:
        if not data["sessions"]:
            return _loc(
                f"USAGE — aucune session Claude Code trouvée pour {project}",
                f"USAGE — no Claude Code session found for {project}",
            )
        t, n = data["totals"], self._n
        sent = t["input"] + t["cache_read"] + t["cache_write"]
        share = 100 * t["cache_write"] / sent if sent else 0.0
        lines = [
            _loc(
                f"USAGE — {data['sessions']} session(s), {t['calls']} appels au modèle, {data['compactions']} compactage(s)",
                f"USAGE — {data['sessions']} session(s), {t['calls']} model calls, {data['compactions']} compaction(s)",
            ),
            f"  input {n(t['input'])} · cache read {n(t['cache_read'])} · cache write {n(t['cache_write'])} "
            f"({share:.1f}%) · output {n(t['output'])}",
        ]
        lines += self._section(
            _loc("CONTEXTE INJECTÉ PAR LES HOOKS", "CONTEXT INJECTED BY HOOKS"),
            [f"{i['count']:>5} × {i['hook']:<22} ~{n(i['tokens'])} tok  “{i['preview']}…”" for i in data["injections"]],
        )
        lines += self._section(
            _loc("SORTIES D'OUTILS", "TOOL OUTPUT"),
            [
                f"{x['tool'][:34]:<34} {x['calls']:>5} {_loc('appels', 'calls')}  ~{n(x['tokens'])} tok"
                for x in data["tools"]
            ],
        )
        lines += self._section(
            _loc("FICHIERS LUS PLUSIEURS FOIS", "FILES READ MORE THAN ONCE"),
            [f"{r['count']:>5} × {r['path']}" for r in data["repeated_reads"]],
        )
        lines += self._section(
            _loc("SERVEURS MCP EN ÉCHEC DE CONNEXION", "MCP SERVERS FAILING TO CONNECT"),
            [f"{m['server']}: {m['sessions']} session(s)" for m in data["mcp_failures"]],
        )
        lines.append(
            _loc(
                "Mesures locales (journaux de Claude Code) ; rien n'est envoyé. Leviers : prism-ai-lint --details.",
                "Local measurements (Claude Code transcripts); nothing is sent. Levers: prism-ai-lint --details.",
            )
        )
        return "\n".join(lines)

    @staticmethod
    def _section(title: str, rows: list[str]) -> list[str]:
        return ["", title, *(f"  {r}" for r in rows)] if rows else []
