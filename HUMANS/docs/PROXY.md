# Engram Proxy Guide

This document covers `engram-proxy`, the optional live request proxy that sits between a supported AI platform and the upstream model API.

- If you want the fast setup path, read [QUICKSTART.md](QUICKSTART.md).
- If you want the passive observer workflow first, read [SIDECAR.md](SIDECAR.md).
- If you want the MCP server contract, read [MCP.md](MCP.md).
- If something breaks, read [HELP.md](HELP.md).

---

## What the proxy does

`engram-proxy` is the active counterpart to `engram-sidecar`.

Instead of waiting for transcripts after the fact, it sits in the live API path and can:

- inject Engram context into model requests before they reach the upstream API,
- trigger `memory_session_flush` when context pressure gets too high,
- extract checkpoint-worthy material from non-streaming responses,
- optionally run the sidecar-style ACCESS/session observer in process with `--with-sidecar`.

The proxy is intentionally opt-in. If you stop using it, the sidecar-only path still works.

For most users, the safest default is to run the proxy with `--with-sidecar`. That keeps the live intervention layer and the ACCESS/session bookkeeping layer aligned. Skip the sidecar bridge only if you explicitly want live mediation without automatic session recording.

## What you gain over sidecar-only

| Mode | What it gives you |
| --- | --- |
| Sidecar only | Transcript-derived ACCESS logging and session recording after the interaction completes |
| Proxy only | Live context injection, token-aware flushes, automatic checkpointing |
| Proxy + `--with-sidecar` | Live intervention plus post-turn ACCESS logging and session lifecycle recording from proxy-observed traffic |

The proxy does not replace the memory repo or the governed MCP tool surface. It routes back into the same Engram read/write contracts.

## Current scope

The current implementation supports:

- OpenAI-style `chat/completions` traffic,
- Anthropic-style `messages` traffic,
- streaming and non-streaming pass-through,
- optional in-process sidecar observation,
- local configuration through CLI flags, environment variables, and advanced request headers.

The current implementation does not support:

- hosted chat surfaces that do not allow a custom API base URL,
- automatic checkpointing for streaming deltas,
- automatic project-aware injection unless the client can send `X-Engram-Project`,
- direct ACCESS attribution for every discovery tool result. Automatic ACCESS remains strongest for direct `memory_read_file` retrievals.

## Quick setup

### 1. Install the server runtime

The proxy reuses the same runtime dependencies as `engram-mcp` and `engram-sidecar`.

```bash
python -m pip install -e ".[server]"
```

### 2. Confirm the repo root

By default the proxy resolves the memory repo root in this order:

1. `--repo-root`
2. `MEMORY_REPO_ROOT`
3. `AGENT_MEMORY_ROOT`
4. file-relative detection from the installed package

If your Engram checkout is not the current working tree, set `MEMORY_REPO_ROOT` or pass `--repo-root` explicitly.

### 3. Start the proxy

Anthropic upstream example:

```bash
engram-proxy --upstream https://api.anthropic.com --model-context-window 200000 --with-sidecar
```

OpenAI upstream example:

```bash
engram-proxy --upstream https://api.openai.com --model-context-window 128000 --with-sidecar
```

If `ANTHROPIC_API_KEY` is set, the proxy defaults upstream discovery to `https://api.anthropic.com`. If `OPENAI_API_KEY` is set and Anthropic is not, it defaults to `https://api.openai.com`. Otherwise the internal fallback is `http://127.0.0.1:8401`, which is mainly useful for local chaining and tests.

You do not need a separate long-running `engram-mcp` process for the default proxy workflow. `engram-proxy` loads the Engram tool registry in process.

### 4. Verify the first real run

After the first real interaction through the proxy, confirm:

- the client still reaches the upstream model normally,
- injected context appears when you expect it to,
- if `--with-sidecar` is enabled, new session data appears under `core/memory/activity/YYYY/MM/DD/chat-NNN/`,
- if a context-pressure flush actually fires, the active session directory gains a `checkpoint.md` entry.

If you want the most conservative rollout, start with a normal sidecar setup from [SIDECAR.md](SIDECAR.md), confirm that path first, and then add the proxy on top.

## Per-platform setup

The examples below are intentionally operator-facing. They document the verified `engram-proxy` command plus the host setting you need to change, but they do not guess hidden Claude Code or Cursor config-file snippets. Those storage formats and field labels are host-version-dependent and should not be treated as stable unless separately verified.

### Claude Code

Use the proxy only if your Claude Code setup exposes a custom Anthropic base URL or equivalent provider endpoint override.

Operator example:

1. Start the proxy locally.

```bash
export MEMORY_REPO_ROOT=/path/to/Engram
export ANTHROPIC_API_KEY=your-real-key
engram-proxy --upstream https://api.anthropic.com --model-context-window 200000 --with-sidecar
```

2. In Claude Code, open the provider or Anthropic settings and look for a field such as `Base URL`, `API Base URL`, `Custom Endpoint`, or equivalent.
3. Set that value to `http://127.0.0.1:8400`.
4. Keep your normal `ANTHROPIC_API_KEY` configured in Claude Code. The proxy forwards upstream auth headers unchanged.
5. Leave your model selection unchanged.
6. Open the repo as usual. The proxy will now inject context before requests, flush when configured thresholds are crossed, and optionally feed sidecar-style ACCESS/session writes.

Smoke test:

- ask for one short prompt and confirm the request still succeeds,
- if `--with-sidecar` is enabled, confirm a new session appears under `core/memory/activity/YYYY/MM/DD/chat-NNN/`,
- if you later run a context-heavy session, confirm a `checkpoint.md` appears only when a real flush threshold is crossed.

Default behavior note:

- Unless you have separately verified a way to add custom request headers, treat Claude Code as a `memory_context_home` path by default.
- Project-aware injection needs `X-Engram-Project`, and this guide does not assume Claude Code can send that header natively.

If your Claude Code build does not expose a custom base URL setting, use the sidecar-only path from [SIDECAR.md](SIDECAR.md).

### Cursor

Cursor is the clearest proxy candidate because it already supports custom model endpoints for some providers.

Operator example for Anthropic traffic:

1. Start the proxy with the Anthropic upstream.

```bash
export MEMORY_REPO_ROOT=/path/to/Engram
export ANTHROPIC_API_KEY=your-real-key
engram-proxy --upstream https://api.anthropic.com --model-context-window 200000 --with-sidecar
```

2. In Cursor, open the model or provider settings and look for the Anthropic base URL or provider endpoint override.
3. Set it to `http://127.0.0.1:8400`.
4. Keep the normal Anthropic API key configured in Cursor.
5. Leave your model selection unchanged.

Operator example for OpenAI-style traffic:

1. Start the proxy with the OpenAI upstream.

```bash
export MEMORY_REPO_ROOT=/path/to/Engram
export OPENAI_API_KEY=your-real-key
engram-proxy --upstream https://api.openai.com --model-context-window 128000 --with-sidecar
```

2. In Cursor, open the provider settings for the OpenAI-style endpoint you want to preserve.
3. Set that base URL to `http://127.0.0.1:8400`.
4. Keep the normal provider API key configured in Cursor.
5. Leave your model selection unchanged.

Smoke test for either path:

- run one short prompt and confirm the response still succeeds,
- confirm the host continues to use the provider model you expected,
- if `--with-sidecar` is enabled, confirm a new activity session appears after the interaction.

Default behavior note:

- Like Claude Code, Cursor should be treated as a `memory_context_home` path unless you have separately verified custom-header support or a wrapper that adds `X-Engram-Project`.
- Do not assume native Cursor settings can send `X-Engram-*` headers just because they can change the upstream base URL.

If you can only configure a hosted provider with no base-URL override, the proxy is not the right integration surface.

### Host-specific limitation summary

- Changing the base URL is enough to route live model traffic through the proxy.
- It is usually not enough to unlock project-aware injection, because that requires `X-Engram-Project`.
- Treat the advanced header surface below as a wrapper or custom-client integration path, not as something the default Claude Code or Cursor UI necessarily exposes.

### ChatGPT and other hosted chat UIs

Hosted ChatGPT does not expose a custom API base URL, so `engram-proxy` is not a viable integration there. Use the normal repo/bootstrap instructions from [QUICKSTART.md](QUICKSTART.md) and, where supported, sidecar-only or manual export/import workflows.

## Configuration reference

### CLI flags

| Flag | Purpose | Default |
| --- | --- | --- |
| `--host` | Proxy listen host. | `127.0.0.1` |
| `--port` | Proxy listen port. | `8400` |
| `--upstream` | Upstream model API base URL. | Auto-detect from API key, else `http://127.0.0.1:8401` |
| `--request-timeout` | Upstream request timeout in seconds. | `60` |
| `--model-context-window` | Default context window for compaction-flush calculations when the client does not send one. | Unset |
| `--flush-threshold` | Fraction of context capacity that triggers `memory_session_flush`. | `0.85` |
| `--reset-threshold` | Fraction below which the flush monitor re-arms. | `0.6` |
| `--enable-injection` / `--no-injection` | Enable or disable live context injection. | Injection enabled |
| `--enable-checkpointing` / `--no-checkpointing` | Enable or disable automatic response checkpointing. | Checkpointing enabled |
| `--with-sidecar` | Enable in-process ACCESS/session observation. | Off |
| `--repo-root` | Memory repo root override. | Auto-detected |
| `--state-file` | Override the local proxy/sidecar state path. | `~/.engram/proxy/<repo-hash>.json` |

### Environment variables

| Variable | Purpose |
| --- | --- |
| `MEMORY_REPO_ROOT` | Primary repo-root override shared with `engram-mcp`. |
| `AGENT_MEMORY_ROOT` | Alternate repo-root override. |
| `MEMORY_CORE_PREFIX` | Content-root override when the managed tree lives under `core/`. |
| `PROXY_HOST` | Default listen host. |
| `PROXY_PORT` | Default listen port. |
| `PROXY_REQUEST_TIMEOUT` | Default upstream timeout in seconds. |
| `PROXY_UPSTREAM_URL` | Explicit upstream base URL override. |
| `PROXY_MODEL_CONTEXT_WINDOW` | Default context window for flush calculations. |
| `PROXY_FLUSH_THRESHOLD` | Default context-pressure flush threshold. |
| `PROXY_RESET_THRESHOLD` | Default compaction reset threshold. |
| `PROXY_ENABLE_INJECTION` | Default injection toggle. |
| `PROXY_ENABLE_CHECKPOINTING` | Default checkpointing toggle. |
| `PROXY_WITH_SIDECAR` | Default sidecar-bridge toggle. |

### Advanced request headers

These headers are consumed by the proxy and stripped before upstream forwarding:

| Header | Purpose |
| --- | --- |
| `X-Engram-Project` | Route injection to `memory_context_project` instead of `memory_context_home`. |
| `X-Engram-Session-Id` | Attach a canonical session id for flushes, checkpoints, and sidecar observation. |
| `X-Engram-Model-Context-Window` | Per-request context window override for compaction-flush calculations. |
| `X-Engram-Max-Context-Chars` | Explicit injection budget override. |
| `X-Engram-Include-Plan-Sources` | Control plan-source inclusion for project injection. |
| `X-Engram-Include-Project-Index` | Control project-index inclusion for home injection. |

If none of these headers are available, the proxy still works, but it falls back to home-context injection and can only run compaction flushes when a default model context window is configured.

For most operators, these headers should be treated as advanced integration hooks rather than default host settings. Claude Code and Cursor examples in this guide assume base-URL overrides only, not native custom-header support.

## Local state file

When you run the proxy with `--with-sidecar`, it keeps a small local JSON state file outside the repo by default:

```text
~/.engram/proxy/<repo-hash>.json
```

That file exists to keep the in-process sidecar bridge stable across restarts. In practice, it preserves local observer state such as canonical session-id allocation so repeated proxy runs do not churn `chat-NNN` assignment.

If you are not using `--with-sidecar`, the state file is largely irrelevant. If you intentionally want a fresh observer state, pass a different `--state-file` path or remove the existing one, with the same caveat as the sidecar: replay-related stability is lost when you reset local state.

## Latency expectations

The design target remains under roughly 200 ms of extra latency per request in steady state, but the cost is not uniform.

- Context injection adds local tool-call and file-read time before the upstream request starts.
- Token counting is cheap in steady state, but a threshold-crossing flush performs a governed write and is therefore the most expensive request-side event.
- Automatic checkpointing runs after non-streaming responses are already relayed to the client, so it should not change first-byte latency and usually does not meaningfully affect end-user wait time.
- `--with-sidecar` processing runs off the response path through an observation queue, so ACCESS/session bookkeeping should not materially slow the proxied request.

If latency matters more than live intervention, use the sidecar-only workflow instead.

## Troubleshooting

### The platform cannot use the proxy at all

If the platform does not allow a custom API base URL, `engram-proxy` is not the right integration surface. Use [SIDECAR.md](SIDECAR.md) where possible, or the normal file-based bootstrap path.

### Requests never reach the proxy

Confirm that the platform's provider base URL points to `http://127.0.0.1:8400` and that `engram-proxy` is still running on the same host/port.

### The proxy starts, but no context is injected

The current injector only runs on supported JSON request formats: OpenAI-style `/v1/chat/completions` and Anthropic-style `/v1/messages`. Also check that injection was not disabled with `--no-injection` or `PROXY_ENABLE_INJECTION=0`.

### Upstream authentication fails

The proxy forwards upstream auth headers but does not invent them. Keep your normal provider API key configured in the client.

### The wrong upstream provider is selected automatically

Automatic upstream selection is intentionally simple. If both `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are present, Anthropic wins the fallback order. Set `--upstream` or `PROXY_UPSTREAM_URL` explicitly whenever you want deterministic routing.

### Context injection works, but flushes never trigger

Compaction flushes need a model context window. Set `--model-context-window`, export `PROXY_MODEL_CONTEXT_WINDOW`, or arrange for the client to send `X-Engram-Model-Context-Window`.

### The proxy always injects home context, not project context

Project-aware injection requires `X-Engram-Project`. Without it, the proxy deliberately falls back to `memory_context_home`.

### Automatic checkpoints do not appear for streaming sessions

The current checkpoint monitor only inspects non-streaming JSON responses after the final body is available. Streaming responses are still passed through, but they are not auto-checkpointed.

### Sidecar-style ACCESS logging seems sparse

That is expected right now for broad discovery traffic. The strongest automatic ACCESS attribution remains direct `memory_read_file` retrievals with concrete file paths.

### Port 8400 is already in use

Start the proxy on a different port with `--port <port>` and update the platform's provider base URL to match.

## Upgrade path from sidecar-only

The safest rollout path is:

1. Start with [SIDECAR.md](SIDECAR.md) to verify that ACCESS logging and session recording are healthy in your environment.
2. Add `engram-proxy` only for platforms that can point at a local base URL.
3. Start the proxy with `--with-sidecar` so the live intervention layer and the passive bookkeeping layer stay aligned.
4. If the proxy proves too heavy or awkward for a given tool, stop it and fall back to sidecar-only mode. No data migration is required.

This keeps the proxy optional and reversible, which is the intended deployment model.
