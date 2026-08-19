# Q-GPT Capacity Load Rig (Locust)

A Locust rig that generates the **doable** inputs for the capacity calculator.
Built structure-first (Option A): all logic, the S12 weighted mix, per-scenario
tags, load shapes, and custom metrics are in place. The exact HTTP endpoints and
payloads are **Onyx defaults marked `TODO CONFIRM`** — verify them with a 5‑minute
browser capture before the first real run (see *Before you run*).

> **Not runnable yet against staging.** Do not point this at a real environment
> until the four prerequisites below are met.

## Layout

| File | Purpose |
|---|---|
| `load_config.json` | Every tunable (host, auth, S12 mix %, file sizes, timeouts, endpoints). Retune here — never in code. |
| `settings.py` | Loads the config + env-var overrides (secrets, CI). |
| `api.py` | The API contract: endpoint paths + payload builders. **This is the file to confirm.** |
| `support.py` | Auth, synthetic files, SSE stream parsing, custom-metric recording. |
| `locustfile.py` | The user class + weighted, tagged scenario tasks. |
| `shapes.py` | Opt-in load shapes for the infra-profile scenarios (knee / burst / soak). |

## Scenario coverage

| Task (tag) | Calculator rows | Measures |
|---|---|---|
| `stateless_prompt` (`s01`,`s08`) | S01, S08 | baseline sessions/node, held-stream duration, output tokens |
| `conversation_prompt` (`s02`) | S02 | conversation-history token amplification |
| `rag_document_query` (`s03`) | S03, S12 | vector-search QPS, RAG context tokens |
| `ingest_light` (`s04`) | S04 | light file ingestion time |
| `ingest_heavy` (`s05`) | S05, S16 | heavy ingestion, worker capacity, NAT egress |
| `agentic_mcp_prompt` (`s06`) | S06, S07 | MCP calls per prompt, agentic call count |
| shape `step` | S18 | utilisation knee / safe operating point |
| shape `burst` | S15 | HA floor + burst headroom |
| shape `soak` | S20 | autoscaler scale-up / scale-down |

Rows **not** covered here are the caveated/derived ones from the analysis:
S09 (reasoning multiplier — read from provider token counts), S10 (OpenRouter
concurrency — a provider limit, get from the account), S11/S12 cost & routing
(modelling), S13 (binding constraint — computed from a heavy-mix run), S19 (SLA
wording — business). See the capacity-calculator notes.

## Reading the results

Locust's default rows give latency/RPS/failures per endpoint. The calculator
quantities are emitted as extra **`metric:*`** rows (via `support.record_metric`):

| Row | Feeds |
|---|---|
| `metric:stream_hold_ms` | S08 held-stream duration |
| `metric:ttft_ms` | time-to-first-token |
| `metric:output_tokens` | S08 output tokens per prompt |
| `metric:rag_prompt_tokens` | S03 RAG context tokens |
| `metric:mcp_calls` | S06/S07 MCP calls per prompt |
| `metric:ingest_ms` | S04/S05 ingestion seconds |

The `response_time` column of those rows carries the value; read its
median/percentiles. Export with `--csv` for the model.

## Before you run (prerequisites)

1. **Confirm the API contract.** Follow the capture steps at the top of `api.py`,
   then update `endpoints`/`auth` in `load_config.json` and the payload builders.
2. **Set credentials via env** (never commit them):
   ```
   export QGPT_LOAD_USER=...        # or QGPT_LOAD_API_KEY with auth mode api_key
   export QGPT_LOAD_PASSWORD=...
   ```
3. **Keep `stub_model: true`** so you measure Q-GPT infra, not OpenRouter. Confirm
   the backend maps `stub_model_name` to a cheap/mock model.
4. **Use an isolated tenant / non-mutating mode.** The agentic and ingestion tasks
   can create real data; point at a throwaway tenant before running at load.

## Running (once the above is done)

Install: `pip install locust`

```bash
# Full weighted mix, web UI at http://localhost:8089
locust -f load/locustfile.py

# One scenario in isolation (e.g. vector-search capacity S03)
locust -f load/locustfile.py --tags s03 --headless -u 50 -r 5 -t 5m --csv reports/load_s03

# Infra-profile via a shape (pick one)
QGPT_LOAD_SHAPE=step  locust -f load/shapes.py --headless --csv reports/load_knee
QGPT_LOAD_SHAPE=burst locust -f load/shapes.py --headless --csv reports/load_burst
QGPT_LOAD_SHAPE=soak  locust -f load/shapes.py --headless --csv reports/load_soak
```

`-u` users, `-r` spawn rate, `-t` duration. Drop `--headless` to drive it from the UI.
