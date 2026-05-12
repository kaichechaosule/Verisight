# Verisight（洞真）

Verisight is a CLI-first web search and evidence verification harness for coding agents such as OpenCode and OpenClaw. It searches public sources, extracts known URLs, ranks evidence, checks factual claims, and returns structured JSON. The agent remains responsible for reading the evidence, preserving citations, and stating uncertainty.

Verisight is useful when an agent needs fresh information, provider fallback, source-backed answers, or a deterministic claim-verification pass without adding another LLM layer.

## Quickstart

Install from a checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Run a keyless search with DuckDuckGo:

```bash
verisight search "current Python release" --providers duckduckgo --compact
```

Inspect configured providers:

```bash
verisight providers
```

Every command prints JSON. A compact `search` response looks like this:

```json
{
  "query": "current Python release",
  "mode": "search",
  "providers_used": ["duckduckgo"],
  "results": [
    {"title": "Python Release Python 3.x", "url": "https://www.python.org/...", "snippet": "..."}
  ],
  "citations": [
    {"url": "https://www.python.org/...", "title": "Python Release Python 3.x"}
  ],
  "diagnostics": [{"provider": "duckduckgo", "ok": true}]
}
```

For final answers, use the `citations` and inspect `diagnostics` before claiming the search was exhaustive.

## Provider setup

Configure whichever providers you want to use. DuckDuckGo works without an API key and is the default free fallback.

| Provider | Search | Extract | API key | Best for | Provider-specific options |
| --- | --- | --- | --- | --- | --- |
| Brave | yes | no | `BRAVE_API_KEY` | broad web and news search | `result_filter`, `spellcheck`, `text_decorations`, `extra_snippets`, `offset` |
| DuckDuckGo | yes | no | none | free fallback web search | `backend`; `page` is validated but currently ignored |
| Exa | yes | no | `EXA_API_KEY` | semantic docs/code/research search | `type`, `category`, `livecrawl`, `include_text`, `exclude_text`, `highlights`, `summary`, `subpages` |
| Tavily | yes | no | `TAVILY_API_KEY` | agent-oriented research search | `search_depth`, `topic`, `chunks_per_source`, `include_images`, `include_image_descriptions`, `auto_parameters` |
| Jina | no | yes | optional `JINA_API_KEY` | URL extraction | Jina options are not applied in the search flow |

```bash
export BRAVE_API_KEY="..."
export EXA_API_KEY="..."
export TAVILY_API_KEY="..."
export JINA_API_KEY="..."   # optional, extraction only
```

## Command guide

Use the lightest command that can produce enough evidence.

| Command | Use it for | Example |
| --- | --- | --- |
| `search` | one-shot configurable search | `verisight search "latest Grok DeepSearch API" --mode research --compact` |
| `deep` | multi-round research with follow-up queries and extraction | `verisight deep "compare Grok DeepSearch and ChatGPT Deep Research" --strict --compact` |
| `verify` | factual claim checking with verdict metadata | `verisight verify "xAI live search requires the Responses API" --source-profile official --strict --compact` |
| `extract` | reading a known URL through Verisight's JSON contract | `verisight extract "https://docs.x.ai/docs/guides/live-search"` |
| `providers` | provider availability, capabilities, and option schemas | `verisight providers` |
| `route` | preview mode/provider routing for a query | `verisight route "latest OpenAI API docs"` |

`extract` is a utility command, not a search mode. Jina is intentionally excluded from search routing and is used for URL extraction when available.

## Common search options

These options are available on `search`, `deep`, and `verify`.

| Option | Purpose |
| --- | --- |
| `--compact` | smaller JSON for token-sensitive agent use |
| `--providers brave,exa,...` | manually constrain search providers |
| `--source-profile balanced\|official\|community` | prefer broad, authoritative, or community/forum sources |
| `--strict` | increase deterministic search/extraction breadth for important claims |
| `--allowed-domains` / `--excluded-domains` | keep or remove domains, including subdomains |
| `--from-date` / `--to-date` | request date filtering when dates are available |
| `--time-range day\|week\|month\|year` | request relative freshness filtering |
| `--country` / `--language` | pass provider-native region and language hints when supported |
| `--safe-search off\|moderate\|strict` | request provider-native safety filtering when supported |
| `--include-raw-content true\|markdown\|text` | request provider-native raw content when supported |
| `--include-answer true\|basic\|advanced` | request provider-native answer or summary generation when supported |

Provider-native support varies. Check diagnostics to see whether a constraint was handled natively or post-processed by Verisight after retrieval.

## Provider-specific options

Use provider-specific options when a provider capability matters to the answer. Pass them as JSON or through a file:

```bash
verisight search "latest model release" \
  --providers brave \
  --provider-options '{"brave":{"result_filter":["web","news"],"extra_snippets":true}}'

verisight search "semantic docs search" \
  --providers exa \
  --provider-options '{"exa":{"type":"neural","livecrawl":"fallback","summary":true}}'

verisight search "free fallback search" \
  --providers duckduckgo \
  --provider-options '{"duckduckgo":{"backend":"html","page":2}}'
```

The same object can be placed in a file:

```json
{
  "tavily": {"search_depth": "advanced", "auto_parameters": true},
  "exa": {"type": "neural", "livecrawl": "fallback", "summary": true},
  "brave": {"result_filter": ["web", "news"], "extra_snippets": true},
  "duckduckgo": {"backend": "html"}
}
```

```bash
verisight search "query" --provider-options-file search-options.json
```

Do not treat provider options as applied just because you requested them. Inspect `diagnostics[].provider_options_applied` and `diagnostics[].provider_options_ignored`.

## Output contract

All commands print JSON.

`search` returns:

- `query`, `mode`, and `providers_used`;
- ranked `results` with title, URL, snippet, provider, score, and metadata;
- `citations` for answer synthesis;
- provider `diagnostics`;
- `routing` metadata including selected mode and providers.

`deep` adds:

- per-round `iterations`;
- generated follow-up queries;
- extracted evidence from top results;
- an `evidence_graph` that links searches and extracted pages.

`verify` adds:

- deterministic `verdict` and `confidence`;
- `supporting_evidence` and `contradicting_evidence`;
- grouped verification queries;
- `verdict_metadata`, including uncertainty flags.

The verdict engine is deterministic and rule-based. It is not an LLM judge. Inspect the evidence before making high-stakes claims.

## Diagnostics guide

Diagnostics are the main difference between Verisight and a plain search wrapper. They tell the agent how complete the evidence set is.

| Field | Meaning |
| --- | --- |
| `ok` | whether the provider completed successfully |
| `latency_ms` / `attempts` / `circuit_state` | retry and circuit-breaker context |
| `native_params` | common request parameters handled directly by the provider |
| `post_processed_params` | common parameters Verisight applied after retrieval |
| `ignored_params` | common parameters that could not be honored |
| `provider_options_applied` | provider-specific options consumed by the provider implementation |
| `provider_options_ignored` | validated provider-specific options that are not implemented in that provider path |
| `provider_options_conflicts` | conflicts between requested options and the harness contract |

Example interpretation:

```json
{
  "provider": "duckduckgo",
  "ok": true,
  "provider_options_applied": {"backend": "html"},
  "provider_options_ignored": {
    "page": "provider option is validated but not implemented by this provider yet"
  }
}
```

This means the DuckDuckGo backend affected retrieval, but pagination did not. Do not claim page 2 was searched.

## Agent workflows

### Official API capability check

```bash
verisight verify "xAI live search is available on the Responses API" \
  --source-profile official \
  --allowed-domains docs.x.ai,x.ai \
  --strict \
  --compact
```

Use this for API support, pricing, legal, security, and version claims. Prefer official sources and inspect uncertainty flags.

### Community debugging research

```bash
verisight deep "Playwright Chromium timeout Windows antivirus CI resource limits" \
  --source-profile community \
  --strict \
  --compact
```

Community evidence is useful for symptoms and leads. Do not treat it as final proof without official or primary-source confirmation.

### Multi-provider semantic research

```bash
verisight search "RAG hallucination evaluation benchmark" \
  --providers exa,tavily,brave \
  --include-answer basic \
  --provider-options '{"exa":{"type":"neural","summary":true},"tavily":{"search_depth":"advanced"}}' \
  --compact
```

Use this when semantic coverage matters. Check which provider options were applied before describing the retrieval strategy.

### Known URL extraction

```bash
verisight extract "https://docs.python.org/3/using/windows.html"
```

Use extraction when the user gives a URL and asks what that page says. If extraction fails, report the failure instead of inventing page contents.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No results | run `verisight providers`; try `--providers duckduckgo`; broaden the query |
| Paid provider unavailable | check the relevant environment variable and provider diagnostics |
| Provider returned errors or timeouts | inspect `error`, `attempts`, and `circuit_state`; results may be incomplete |
| Filters did not behave as expected | inspect `native_params`, `post_processed_params`, and `ignored_params` |
| Provider option seemed ignored | inspect `provider_options_applied` and `provider_options_ignored` |
| DuckDuckGo backend fails | try `{"duckduckgo":{"backend":"auto"}}` or another backend |
| Jina does not appear in search routing | expected; Jina is extraction-only |
| Non-English verification looks weak | the deterministic claim parser may return `insufficient` or neutral evidence more often |

## Limitations

- Verisight is not an LLM and does not write final answers.
- Provider-native support varies by provider and API behavior.
- Some constraints are post-processed after retrieval, so they can reduce but not fully control what providers fetched.
- DuckDuckGo `page` is validated but not implemented in the current provider path.
- Jina is extraction-only in normal use; it is not a search provider.
- The verifier is rule-based and conservative; unsupported claims may return `insufficient` rather than a forced verdict.
- Community reports are not authoritative evidence for high-confidence factual claims.

## Agent skill

The Verisight agent skill is maintained separately so the CLI package stays focused on the evidence engine. See the standalone skill repository when using Verisight as an agent policy layer.
