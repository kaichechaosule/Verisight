# Verisight（洞真）

CLI-first web search and evidence verification for coding agents such as OpenCode and OpenClaw. Verisight searches, extracts, ranks, classifies evidence, and returns JSON; the agent remains responsible for the final answer.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Configure any search providers you want to use:

| Provider | Environment variable | Role |
| --- | --- | --- |
| Brave | `BRAVE_API_KEY` | Fast broad web search |
| DuckDuckGo | None | Free backup web search |
| Exa | `EXA_API_KEY` | Semantic docs/code/research search |
| Tavily | `TAVILY_API_KEY` | Agent-oriented research search |
| Jina | Optional `JINA_API_KEY` | URL extraction only |

## Core commands

```bash
verisight search "latest Grok DeepSearch API" --mode research --compact
verisight deep "compare Grok DeepSearch and ChatGPT Deep Research" --strict --compact
verisight verify "grok-4.20-multi-agent supports 16 agents" --source-profile official --strict --compact
```

Use `search` for configurable one-shot search, `deep` for multi-round research, and `verify` for claim checking with a verdict.

## Agent options

Common options for `search`, `deep`, and `verify`:

- `--compact`: smaller JSON for token-sensitive agent use.
- `--source-profile balanced|official|community`: choose general, authoritative, or forum/community sources.
- `--strict`: increase deterministic search depth and extraction breadth without adding LLM calls.
- `--country` / `--language`: pass provider-native region and language hints when supported.
- `--safe-search off|moderate|strict`: request provider-native safe search filtering when supported.
- `--time-range day|week|month|year`: request relative freshness filtering when supported.
- `--include-raw-content [true|markdown|text]`: request provider-native raw content when supported.
- `--include-answer [true|basic|advanced]`: request provider-native answer/summary generation when supported.

Advanced filters:

- `--allowed-domains` / `--excluded-domains`: keep or remove domains, including subdomains.
- `--from-date` / `--to-date`: filter when result dates are available.
- `--providers`: manually select search providers.

Provider-native support varies. Verisight reports diagnostics showing which requested parameters were handled natively and which were applied as post-processing fallbacks.

Forum/community sources are useful for discovery, debugging, and user reports. They should not be treated as primary evidence for high-confidence factual verdicts.

## Output contract

All commands print JSON. `search` returns ranked `results`, `citations`, `diagnostics`, and routing metadata. `deep` adds per-round `iterations` and an `evidence_graph`. `verify` returns `verdict`, `confidence`, evidence buckets, query groups, and uncertainty metadata.

The verdict engine is deterministic and rule-based. Inspect evidence before making high-stakes claims; non-English claims may fall back to `insufficient` or `neutral` more often until Unicode-aware claim parsing is added.

## Advanced / debug commands

```bash
verisight providers
verisight route "latest Grok DeepSearch API"
verisight extract "https://docs.x.ai/docs/guides/live-search"
```

`extract` reads a known URL through Verisight's JSON contract. It is a utility command, not a search mode. Jina is intentionally excluded from search routing and is used internally by `deep` and `verify` for extraction when available.

## Agent skill

Agent skill packaging is maintained outside this repository so the CLI package stays focused on Verisight itself.
