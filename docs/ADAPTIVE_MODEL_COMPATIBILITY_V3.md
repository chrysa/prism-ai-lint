# Adaptive model compatibility — implementation contract

Status: proposed, no runtime behavior changed. Base: develop. Date: 2026-11-11.

## Scope and compatibility

PRISM must remain a dependency-free deterministic linter. The optional AI subsystem is both (a) an analyzer that can invoke compatible inference endpoints and (b) a read-only auditor of model references in agent configurations. A model being recognized does not imply it is executable. Unknown IDs are allowed, never automatically labelled obsolete.

The model registry stores provider, canonical ID, aliases, source URL, verified timestamp, lifecycle status (known/unknown/deprecated/retired), context limit when verified, pricing when verified, modality, tool-calling and structured-output capabilities, and protocol requirements. Missing capabilities are UNKNOWN, never assumed false or true. Model catalog snapshots are locally cached, signed or checksummed, schema-versioned and manually overridable. Catalog updates never modify agent permissions.

## Provider strategy

1. OpenAI-compatible HTTP adapter: configurable base URL, authentication by environment variable, capability probes, explicit TLS and timeout policy. Do not assume every compatible endpoint supports tools, JSON schema or /models.
2. Ollama adapter: local discovery and invocation; avoid silent cloud routing.
3. Native Anthropic and Gemini adapters for divergent semantics.
4. Optional LiteLLM and gateway adapter, with no mandatory runtime dependency.
5. Extensible provider registry; unknown models accepted through explicit configuration and probed only with user consent.

Implement Protocol interfaces for ModelCatalog, Provider, ModelRouter and SemanticAnalyzer. Separate transport from policy. Prefer stdlib for core; optional dependencies belong to extras.

## Routing and privacy

Order of decisions: hard privacy policy -> task capabilities -> endpoint availability -> budget -> quality benchmark -> latency. Local-first is a preference, not a guarantee of local execution: when cloud is forbidden, fail closed. Cloud disabled by default. Never transmit secrets, credentials, private paths or raw unredacted configuration. Redaction failures stop export. Prompt injection in analyzed files is treated as untrusted content, not instructions. Provider outputs cannot execute code, enable permissions, write files, or block CI by default.

Fallback only among policy-eligible models, with max attempts, deadlines and a bounded monetary budget. Preserve deterministic lint results if the AI subsystem fails.

## Test-first acceptance criteria

- Baseline: make check, make cov, make selfcheck, make docker-test, Python 3.13/3.14; capture SHA and machine-readable reports. Do not claim a green baseline before running.
- No network traffic when AI is disabled, in pre-commit, or with cloud forbidden.
- Unknown model IDs are accepted and marked unverified; aliases resolve without silently changing the configured model.
- Capability mismatch is reported, not silently substituted.
- Invalid provider JSON, timeout, 429, 5xx, missing key, offline endpoint, malformed model list, and context overflow are handled without modifying files.
- Secrets and prompt injection payloads never appear in outbound requests or logs.
- No AI finding can bypass the guard, weaken deny/ask rules, or alter critical content without human approval.
- Adapter contract tests use fake HTTP servers; integration tests are opt-in and secret-gated.
- Benchmark corpus: at least 100 annotated fixtures across Claude Code, Codex, Gemini CLI, Cursor, Windsurf, MCP, hooks, skills and permissions; track precision, recall, false positives, cost, latency and version.
- Preserve existing coverage floor (60%); target >=90% on new safety-critical routing and redaction modules, with branch coverage where practical.

## Incremental PR dependency chain

P0 baseline and tests -> P0 registry/schema and lifecycle checker -> P0 provider Protocol and local/OpenAI-compatible adapters -> P1 native/optional providers -> P1 routing/privacy -> P1 semantic review -> P1 benchmark -> P2 SARIF, GitHub and CHRYSA AI Gateway/portfolio/Notion integration.

Each PR: failing regression test first, Ruff, mypy, pytest, pre-commit, Docker test, changelog, migration note, rollback, security review. No merge on billing-related missing checks without independent reproducible local evidence and explicit authorization.

## Existing decisions to preserve

D-040 Codex and Claude alignment only tightens; D-044 DESIGN.md report-only; D-045 safe allow baseline; D-046 untrusted plugin consent; D-047 model-per-task heuristic remains a compatibility fallback until measured routing is enabled. Reconcile this document with existing V1 P0/P1 specs before coding; do not duplicate previously implemented functionality.

## Definition of done

A clean install remains fully functional offline without credentials. Every supported provider is covered by a contract test. Catalog entries carry evidence and freshness metadata. Any model can be declared without changing core code, while execution requires a supported protocol and verified capabilities. Security invariants and deterministic findings are unchanged.
