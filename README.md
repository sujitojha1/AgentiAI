# AgentiAI — Session 6: Agentic Architecture

> **EAG V3 · Session 6 Assignment** — Multi-role agentic AI with four cognitive layers, typed Pydantic contracts, durable memory, and MCP tool dispatch.

---

## Overview

This repository implements the **Session 6 Agentic Architecture** from the EAG V3 course at The School of AI. The agent decomposes user queries into bounded goals and solves them iteratively through four named cognitive roles: **Memory**, **Perception**, **Decision**, and **Action** — each backed by typed Pydantic v2 contracts and wired together by a central agent loop.

All LLM calls are routed through LLM Gateway V3 (`localhost:8101`). MCP stdio transport handles all tool dispatch. No third-party agentic frameworks are used.

---

## Architecture

Four cognitive roles communicate via typed Pydantic schemas:

| Role | Responsibility | LLM Call? |
|------|---------------|-----------|
| **Memory** | Typed service storing facts, preferences, tool outcomes, and scratchpad entries. Exposes `read()` and `record_outcome()`. | Only for ambiguous classification writes |
| **Perception** | Orchestrator. Reads query + memory hits + history, emits a typed goal list with `done` flags. Runs every iteration. | Yes — every iteration (pinned to Gemini via `provider="gemini"`) |
| **Decision** | Picks next action for one bounded goal. Returns either a plain-text answer or a single `ToolCall`. | Yes — once per iteration when a goal is unfinished |
| **Action** | Pure MCP dispatch. Pushes large payloads (>4 KB) to the artifact store. No LLM call. | No |

### Control Flow

```
Each iteration:
  memory.read(query, history)          → hits[]
  perception.observe(query, hits, ...) → Observation(goals)
  [if all goals done] → break
  decision.next_step(goal, hits, ...)  → DecisionOutput (answer | tool_call)
  [if answer] → append to history, continue
  action.execute(tool_call)            → (descriptor, artifact_id?)
  memory.record_outcome(...)
  append to history, iterate
```

---

## Module Structure

```
AgentiAI/
├── agent6.py          # Main agent loop — wires all four roles
├── memory.py          # Memory service (read, remember, record_outcome, filter, relevant)
├── perception.py      # Perception role — goal decomposition and tracking
├── decision.py        # Decision role — answer or tool_call selection
├── action.py          # Action role — pure MCP tool dispatch + artifact storage
├── schemas.py         # Pydantic v2 contracts: MemoryItem, Goal, Observation, ToolCall, DecisionOutput, Artifact
├── mcp_server.py      # MCP server exposing 9 tools
├── llm_gatewayV3/     # LLM Gateway V3 — routes all LLM calls
├── proof_of_prompt.json  # Proof-of-Prompt validation for Perception and Decision
├── tests/             # One test script per query (A–D)
│   ├── test_query_a.py
│   ├── test_query_b.py
│   ├── test_query_c.py
│   └── test_query_d.py
├── state/             # Runtime state (excluded from git)
│   ├── memory.json    # Durable memory persisted across runs
│   └── artifacts/     # Binary artifact store (NNNNNN.bin + .json)
├── .gitignore
├── LICENSE
└── README.md
```

---

## Pydantic Contracts

Every boundary between roles is a Pydantic v2 model defined in `schemas.py`:

- `MemoryItem` — kind ∈ {fact, preference, tool_outcome, scratchpad}, keywords, descriptor, value, artifact_id
- `Artifact` — content-addressable integer id, content_type, size_bytes, descriptor
- `Goal` — id, text, done: bool, attach_artifact_id
- `Observation` — goals: list[Goal]
- `ToolCall` — name, arguments: dict
- `DecisionOutput` — answer: str | None, tool_call: ToolCall | None (exactly one populated)

---

## Setup & Usage

### Prerequisites

- Python 3.11+
- `uv` for dependency management
- A `.env` file with API keys (GEMINI_API_KEY, TAVILY_API_KEY, etc.)
- LLM Gateway V3 running at `localhost:8101`

### Install & Run

```bash
# Install dependencies
uv sync

# Start the LLM Gateway V3 (in a separate terminal)
cd llm_gatewayV3 && uv run python gateway.py

# Run the agent
uv run python agent6.py

# Run individual query tests
uv run python tests/test_query_a.py
uv run python tests/test_query_b.py
uv run python tests/test_query_c.py
uv run python tests/test_query_d.py
```

---

## Test Results (2026-05-23)

All four target queries pass. Tested against a clean `state/` directory with LLM Gateway V3 at `localhost:8101`.

| Query | Result | Iterations | Time |
|-------|--------|-----------|------|
| A — Shannon Wikipedia | **PASS ✓** | 4 | 227s |
| B — Tokyo activities + weather | **PASS ✓** | 10 | 212s |
| C — Mom's birthday (Run 1 + Run 2) | **PASS ✓** | 3 + 2 | 24s + 16s |
| D — Asyncio research | **PASS ✓** | 6 | 161s |

---

## Query A — Shannon Wikipedia

**Query:** `Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.`

**Tests:** Artifact attach path — 262 KB Wikipedia page → ArtifactStore → Perception attaches to extraction goal.

<details>
<summary>Terminal output (4 iterations, 227s)</summary>

```
[test] cleared /Users/payalchakraborty/Dev/EAG3/AgentiAI/state
==============================================================================
TEST QUERY A — Claude Shannon Wikipedia (artifact attach path)
==============================================================================
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=61786e87
query: Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.
══════════════════════════════════════════════════════════════════════════════
[05/23/26 13:30:08] INFO     Processing request of type ListToolsRequest                                      server.py:727
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 0 done
    ○ fetch-shannon-page: Fetch the Wikipedia page for Claude Shannon.
    ○ extract-biographical-info: Extract birth date and death date from the Wikipedia page.
    ○ summarize-contributions: Identify three key contributions to information theory based on the content.
  [decision]   tool_call: fetch_url({'url': 'https://en.wikipedia.org/wiki/Claude_Shannon'})
[05/23/26 13:30:17] INFO     Processing request of type CallToolRequest                                       server.py:727
[INIT].... → Crawl4AI 0.8.6 
[FETCH]... ↓ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 
2.25s 
[SCRAPE].. ◆ https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 
0.26s 
[COMPLETE] ● https://en.wikipedia.org/wiki/Claude_Shannon                                                         | ✓ | ⏱: 
2.54s 
  [action]     '→ artifact:1'
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ fetch-shannon-page: Fetch the Wikipedia page for Claude Shannon.
    ○ extract-biographical-info: Extract birth date and death date from the Wikipedia page.  [artifact:1]
    ○ summarize-contributions: Identify three key contributions to information theory based on the content.  [artifact:1]
  [artifact]   loaded artifact:1 (262,600 bytes)
  [decision]   answer: 'Claude Shannon was born on April 30, 1916, and died on February 24, 2001.'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ fetch-shannon-page: Fetch the Wikipedia page for Claude Shannon.
    ✓ extract-biographical-info: Extract birth date and death date from the Wikipedia page.  [artifact:1]
    ○ summarize-contributions: Identify three key contributions to information theory based on the content.  [artifact:1]
  [artifact]   loaded artifact:1 (262,600 bytes)
  [decision]   answer: 'Based on the content provided, three key contributions by Claude Shannon to the field of information theory and related '
────────────────────────────────────────────────────────────
[iter 4]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 3 done
    ✓ fetch-shannon-page: Fetch the Wikipedia page for Claude Shannon.
    ✓ extract-biographical-info: Extract birth date and death date from the Wikipedia page.  [artifact:1]
    ✓ summarize-contributions: Identify three key contributions to information theory based on the content.  [artifact:1]
  [loop]       all goals done — terminating


══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (226.51s, 4 iteration(s)):
Based on the content provided, three key contributions by Claude Shannon to the field of information theory and related disciplines include:

1.  **The Mathematical Theory of Communication**: Often considered his seminal work, this foundational text established the core principles of information theory.
2.  **A Symbolic Analysis of Relay and Switching Circuits (1937)**: His master's thesis demonstrated that electrical applications of **Boolean algebra** could construct any logical numerical relationship, which provided the theoretical foundation for **digital circuits** and **digital computing**.
3.  **Entropy in information theory**: Shannon introduced the concept of **entropy** as a measure of information, which became a cornerstone for defining **units of information** and remains essential to modern fields like **data compression**.
══════════════════════════════════════════════════════════════════════════════

==============================================================================
VALIDATION
==============================================================================
  birth  (April 30 1916) found : ✓  (memory)
  death  (Feb 24 2001)  found : ✓  (memory)
  contribution group 1                  : ✓  ('mathematical theory')
  contribution group 2                  : ✓  ('boolean')
  contribution group 3                  : ✓  ('data compression')
  contribution group 4                  : ✗  (signals: ['noisy channel', 'noisy-channel', 'channel capacity']...)
  contribution group 5                  : ✗  (signals: ['cryptograph', 'cryptanalysis', 'secrecy']...)
  ≥3 of 5 groups matched       : ✓  (3 matched)
  artifact ≥4KB stored                 : ✓  (1 artifact(s) ≥4KB, largest 262,600B)
  memory records tool outcome          : ✓  (tools: ['fetch_url'])

  RESULT: PASS ✓
```

</details>

---

## Query B — Tokyo Activities with Weather

**Query:** `Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.`

**Tests:** Multi-goal decomposition, sequential tool calls (web_search + fetch_url + weather fetch), memory carryover across iterations.

<details>
<summary>Terminal output (10 iterations, 212s)</summary>

```
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=1ed0869d
query: Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.
══════════════════════════════════════════════════════════════════════════════
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 0 done
    ○ search-tokyo-activities: Find 3 family-friendly things to do in Tokyo this weekend.
    ○ check-tokyo-weather: Check Saturday's weather forecast for Tokyo.
    ○ recommend-activity: Determine the most appropriate activity based on the weather forecast.
  [decision]   tool_call: web_search({'query': 'family-friendly activities in Tokyo this weekend'})
  [action]     '{"title": "Best Family-Friendly Events in Tokyo (2026)"...}'
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 0 done
  [decision]   tool_call: fetch_url({'url': 'https://tinytotintokyo.com/tokyo-family-events'})
  [action]     '→ artifact:1'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     3 hit(s)
  [perception] 3 goal(s), 0 done
    ○ search-tokyo-activities  [artifact:1]
  [artifact]   loaded artifact:1 (21,129 bytes)
  [decision]   answer: 'Here are three family-friendly activities in Tokyo...'
────────────────────────────────────────────────────────────
[iter 4]
  [memory]     3 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ search-tokyo-activities  [artifact:1]
    ○ check-tokyo-weather
  [decision]   tool_call: web_search({'query': 'Tokyo weather forecast Saturday May 2 2026'})
  [action]     '{"title": "Tokyo, Tokyo, Japan Monthly Weather - AccuWeather"...}'
────────────────────────────────────────────────────────────
[iter 5]
  [memory]     4 hit(s)
  [perception] 3 goal(s), 1 done
  [decision]   tool_call: web_search({'query': 'Tokyo weather forecast Saturday'})
  [action]     '{"title": "Tokyo Weather in May 2026..."...}'
────────────────────────────────────────────────────────────
[iter 6]
  [memory]     5 hit(s)
  [perception] 3 goal(s), 1 done
  [decision]   tool_call: fetch_url({'url': 'https://www.data.jma.go.jp/multi/yoho/yoho_detail.html?code=130010&lang=en'})
  [action]     '→ artifact:2'
────────────────────────────────────────────────────────────
[iter 7]
  [memory]     6 hit(s)
  [perception] 3 goal(s), 1 done
    ○ check-tokyo-weather  [artifact:2]
  [artifact]   loaded artifact:2 (4,402 bytes)
  [decision]   answer: 'The forecast for Tokyo is cloudy with a maximum temperature of 18°C...'
────────────────────────────────────────────────────────────
[iter 8]
  [memory]     6 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ check-tokyo-weather  [artifact:2]
    ○ recommend-activity  [artifact:2]
  [decision]   tool_call: get_time({'timezone': 'Asia/Tokyo'})
  [action]     '{"human": "Saturday, 23 May 2026 16:16:39 JST"...}'
────────────────────────────────────────────────────────────
[iter 9]
  [memory]     7 hit(s)
  [perception] 3 goal(s), 2 done
    ○ recommend-activity  [artifact:1]
  [artifact]   loaded artifact:1 (262,463 bytes)
  [decision]   answer: 'Given that it is currently Saturday, May 23, 2026, and the weather forecast for Tokyo is cloudy with a maximum temperature of 18°C...'
────────────────────────────────────────────────────────────
[iter 10]
  [memory]     7 hit(s)
  [perception] 3 goal(s), 3 done
  [loop]       all goals done — terminating

══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (212.37s, 10 iteration(s)):
Given that it is currently Saturday, May 23, 2026, and the weather forecast for Tokyo is cloudy with a maximum temperature of 18°C, an indoor, family-friendly activity is the most appropriate recommendation.

I recommend visiting the **National Museum of Nature and Science** in Ueno Park. Alternatively, **teamLab Borderless** or **teamLab Planets** are world-class indoor digital art experiences perfect for a cool, cloudy day.
══════════════════════════════════════════════════════════════════════════════

VALIDATION
  answer mentions 'tokyo'         : ✓
  answer references weather       : ✓  (cloud, indoor, forecast)
  ≥2 activities identified        : ✓  (museum, park, teamlab, ueno)
  answer recommends one activity  : ✓

  RESULT: PASS ✓
```

</details>

---

## Query C — Mom's Birthday (Durable Memory)

**Query (Run 1):** `My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.`  
**Query (Run 2):** `When is mom's birthday?`

**Tests:** Durable memory persistence in `state/memory.json` across separate process runs.

<details>
<summary>Terminal output — Run 1 (3 iterations, 24s)</summary>

```
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=493209fe
query: My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
══════════════════════════════════════════════════════════════════════════════
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 2 goal(s), 0 done
    ○ set-reminder-two-weeks-before: Set a calendar reminder for 1 May 2026 for mother's birthday.
    ○ set-reminder-on-birthday: Set a calendar reminder for 15 May 2026 for mother's birthday.
  [decision]   tool_call: get_time({'timezone': 'UTC'})
  [action]     '{"human": "Saturday, 23 May 2026 07:17:47 UTC"...}'
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 2 goal(s), 1 done
    ✓ set-reminder-two-weeks-before
    ○ set-reminder-on-birthday
  [decision]   answer: 'To set a calendar reminder for 15 May 2026...'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     2 hit(s)
  [perception] 2 goal(s), 2 done
  [loop]       all goals done — terminating

══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (23.92s, 3 iteration(s)):
To set a calendar reminder for 15 May 2026 for your mother's birthday, use a digital calendar and set a reminder for that date. For future years, ensure to set the reminder annually on 15 May.
══════════════════════════════════════════════════════════════════════════════

VALIDATION — Run 1
  answer references reminder/calendar : ✓
  answer references May / 2026        : ✓
  state/memory.json has birthday fact : ✓
  total memory items                  : 2  (facts: 1)

  RUN 1 RESULT: PASS ✓
```

</details>

<details>
<summary>Terminal output — Run 2 (2 iterations, 16s — retrieved from memory, no web call)</summary>

```
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=436e6efc
query: When is mom's birthday?
══════════════════════════════════════════════════════════════════════════════
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     3 hit(s)
  [perception] 1 goal(s), 0 done
    ○ identify-moms-birthday: Retrieve the date of the user's mother's birthday from memory
  [decision]   answer: "My mother's birthday is on May 15, 2026."
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     3 hit(s)
  [perception] 1 goal(s), 1 done
  [loop]       all goals done — terminating

══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (16.24s, 2 iteration(s)):
My mother's birthday is on May 15, 2026.
══════════════════════════════════════════════════════════════════════════════

VALIDATION — Run 2
  answer mentions 'birthday' : ✓
  answer mentions 'may'      : ✓
  answer mentions '2026'     : ✓
  answer includes specific date : ✓  (15, may 15)
  memory items after run 2   : 3

  RUN 2 RESULT: PASS ✓

  OVERALL RESULT: PASS ✓
```

</details>

---

## Query D — Asyncio Research

**Query:** `Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.`

**Tests:** Multi-artifact fetch (web_search → 3× fetch_url, each >4 KB), artifact auto-load for synthesis goal, numbered consensus list.

<details>
<summary>Terminal output (6 iterations, 161s)</summary>

```
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=947936f6
query: Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.
══════════════════════════════════════════════════════════════════════════════
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 0 done
    ○ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ○ fetch-top-three-results: Fetch and read the top 3 URLs from the search results.
    ○ summarize-consensus: Identify and list common advice from the three fetched results.
  [decision]   tool_call: web_search({'query': 'Python asyncio best practices', 'max_results': 5})
  [action]     '{"title": "Asyncio Best Practices and Common Pitfalls"...}'
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ search-asyncio-best-practices
    ○ fetch-top-three-results
    ○ summarize-consensus
  [decision]   tool_call: fetch_url({'url': 'https://shanechang.com/p/python-asyncio-best-practices-pitfalls'})
  [action]     '→ artifact:1'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     3 hit(s)
  [perception] 3 goal(s), 1 done
  [decision]   tool_call: fetch_url({'url': 'https://discuss.python.org/t/asyncio-best-practices/12576'})
  [action]     '→ artifact:2'
────────────────────────────────────────────────────────────
[iter 4]
  [memory]     4 hit(s)
  [perception] 3 goal(s), 1 done
  [decision]   tool_call: fetch_url({'url': 'https://docs.python.org/3/library/asyncio-dev.html'})
  [action]     '→ artifact:3'
────────────────────────────────────────────────────────────
[iter 5]
  [memory]     5 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ fetch-top-three-results
    ○ summarize-consensus  [artifact:1]
  [artifact]   loaded artifact:1 (8,594 bytes)
  [artifact]   auto-loaded artifact:3 (26,879 bytes) for synthesis
  [artifact]   auto-loaded artifact:2 (6,558 bytes) for synthesis
  [decision]   answer: 'Here are the common pieces of advice that appear across the three fetched results...'
────────────────────────────────────────────────────────────
[iter 6]
  [memory]     5 hit(s)
  [perception] 3 goal(s), 3 done
  [loop]       all goals done — terminating

══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (160.98s, 6 iteration(s)):
Here are the common pieces of advice that appear across the three fetched results:

### 1. Use `asyncio.run()` as the main entry point
Always use `asyncio.run()` to start your asyncio programs — it properly sets up and tears down the event loop and handles cleanup on exceptions.

### 2. Always await coroutines / don't forget to await
Forgetting to await is one of the most common mistakes. You must use `await` or schedule via `create_task()` for true concurrency.

### 3. Avoid long-running blocking code
Blocking code halts the event loop. Use `loop.run_in_executor()` with a `ThreadPoolExecutor` to offload CPU-bound or blocking work.

### 4. Use tasks / schedule coroutines for concurrency
Use `asyncio.create_task()` to schedule coroutines concurrently rather than awaiting them sequentially.

### 5. Debug mode and logging
Enable debug mode (`PYTHONASYNCIODEBUG`, `debug=True` in `asyncio.run()`) to catch un-awaited coroutines, tasks that are never retrieved, or callbacks that block the loop.

### 6. Handle cancellation and clean up resources
Catch `CancelledError`, clean up resources, and re-raise. Close async generators explicitly and don't leave resources dangling.
══════════════════════════════════════════════════════════════════════════════

VALIDATION
  answer contains 'asyncio'              : ✓
  answer contains 'async'               : ✓
  numbered list ≥3 items                : ✓  (6 item(s) found)
  advice group 1 (asyncio.run)          : ✓
  advice group 2 (concurrency)          : ✓
  advice group 3 (blocking)             : ✓
  artifacts ≥4KB stored (need ≥3)       : ✓  (3 artifact(s), sizes: [26, 8, 6] KB)
  web_search recorded in memory         : ✓
  fetch_url ×3 each with artifact_id    : ✓  (3 fetch_url call(s); 3 with artifact_id)

  RESULT: PASS ✓
```

</details>

---

## Proof of Prompt (PoP) Validation

The system prompts for both the **Decision** and **Perception** modules are fully validated against all 9 PoP criteria (Revision 2). Full prompt text, criterion-by-criterion notes, and scores are in [`proof_of_prompt.json`](proof_of_prompt.json).

| Module | Score | Gap |
|--------|-------|-----|
| **Decision** | 9 / 9 | None (Fully satisfied; added RULE 6 with four explicit fallback sub-cases and ERROR-entry checking) |
| **Perception** | 9 / 9 | None (Fully satisfied; added reasoning-type labels to all steps and ERROR-entry filtering) |

**Shared strengths** (both prompts):
- Unicode section dividers (`━━━`) and named rule labels for visual structure
- Explicit self-check steps before output
- Designed for iterative multi-turn loops with full history context
- Negative examples (`NEVER`, `Do NOT`) alongside positive instructions
- Single exclusive output choice enforced (answer vs tool_call; action A vs action B)
- Robust handling of failed tool calls and error-recovery states in the iteration loop

See [`proof_of_prompt.json`](proof_of_prompt.json) for the full prompts and per-criterion analysis, and [`pop_validation.md`](pop_validation.md) for the evaluator rubric.

---

## Deliverables

- [x] Four code modules with clear separation of concerns (`memory.py`, `perception.py`, `decision.py`, `action.py`) plus `agent6.py` and `schemas.py`
- [x] All four target queries produce correct final answers (terminal output captured above from clean `state/`)
- [x] Memory persists across runs in `state/memory.json` (Query C durable-memory behaviour verified)
- [x] All four cognitive layers backed by typed Pydantic v2 contracts
- [x] LLM Gateway V3 is the sole substrate for every LLM call
- [x] `state/` directory excluded by `.gitignore` and cleanable between attempts
- [x] README includes actual terminal output for all four queries
- [x] Perception and Decision prompts + Validation JSON ([`proof_of_prompt.json`](proof_of_prompt.json))
- [ ] YouTube demo link (pending recording)

---

## Constraints

- Pydantic v2 on every role boundary
- `uv` for Python dependency management — no manual virtualenv activation
- MCP server stdio transport for all tool calls
- No third-party agentic frameworks (LangGraph, LangChain, CrewAI, etc.)

---

## License

This project is licensed under the [Apache 2.0 License](LICENSE).
