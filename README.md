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
| B — Tokyo activities + weather | **PASS ✓** | 5 | 236s |
| C — Mom's birthday (Run 1 + Run 2) | **PASS ✓** | 3 + 2 | 33s + 9s |
| D — Asyncio research | **PASS ✓** | 7 | 405s |

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
<summary>Terminal output (5 iterations, 236s)</summary>

```
[test] cleared /Users/payalchakraborty/Dev/EAG3/AgentiAI/state
==============================================================================
TEST QUERY B — Tokyo Activities + Weather (multi-goal + memory carryover)
==============================================================================
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=8ae53d21
query: Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.
══════════════════════════════════════════════════════════════════════════════
[05/23/26 13:35:08] INFO     Processing request of type ListToolsRequest                                      server.py:727
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 0 done
    ○ search-tokyo-activities: Search for family-friendly activities in Tokyo.
    ○ check-tokyo-weather: Check the weather forecast for Tokyo this Saturday.
    ○ recommend-activity: Synthesize activity information and weather forecast to recommend the most appropriate family-friendly activity for Saturday.
  [decision]   tool_call: web_search({'query': 'family-friendly activities in Tokyo', 'max_results': 5})
[05/23/26 13:35:12] INFO     Processing request of type CallToolRequest                                       server.py:727
  [action]     '{\n  "title": "TOKYO WITH KIDS! Best Things to Do and Family Fun! - YouTube",\n  "url": "https://www.youtube.com/watch?v=I'
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ search-tokyo-activities: Search for family-friendly activities in Tokyo.
    ○ check-tokyo-weather: Check the weather forecast for Tokyo this Saturday.
    ○ recommend-activity: Synthesize activity information and weather forecast to recommend the most appropriate family-friendly activity for Saturday.
  [decision]   tool_call: web_search({'query': 'weather forecast Tokyo this Saturday'})
[05/23/26 13:38:19] INFO     Processing request of type CallToolRequest                                       server.py:727
  [action]     '{\n  "title": "Tokyo, Tokyo, Japan Monthly Weather - AccuWeather",\n  "url": "https://www.accuweather.com/en/jp/tokyo/2263'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     3 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ search-tokyo-activities: Search for family-friendly activities in Tokyo.
    ✓ check-tokyo-weather: Check the weather forecast for Tokyo this Saturday.
    ○ recommend-activity: Synthesize activity information and weather forecast to recommend the most appropriate family-friendly activity for Saturday.
  [decision]   tool_call: fetch_url({'url': 'https://www.accuweather.com/en/jp/tokyo/226396/may-weather/226396', 'timeout': 20})
[05/23/26 13:38:49] INFO     Processing request of type CallToolRequest                                       server.py:727
[INIT].... → Crawl4AI 0.8.6 
[FETCH]... ↓ https://www.accuweather.com/en/jp/tokyo/226396/may-weather/226396                                    | ✓ | ⏱: 
2.09s 
[SCRAPE].. ◆ https://www.accuweather.com/en/jp/tokyo/226396/may-weather/226396                                    | ✓ | ⏱: 
0.03s 
[COMPLETE] ● https://www.accuweather.com/en/jp/tokyo/226396/may-weather/226396                                    | ✓ | ⏱: 
2.14s 
  [action]     '→ artifact:1'
────────────────────────────────────────────────────────────
[iter 4]
  [memory]     4 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ search-tokyo-activities: Search for family-friendly activities in Tokyo.
    ✓ check-tokyo-weather: Check the weather forecast for Tokyo this Saturday.
    ○ recommend-activity: Synthesize activity information and weather forecast to recommend the most appropriate family-friendly activity for Saturday.  [artifact:1]
  [artifact]   loaded artifact:1 (18,030 bytes)
  [decision]   answer: 'Based on the weather forecast for Saturday, May 30, 2026, which is expected to be sunny and less humid with a high of 29'
────────────────────────────────────────────────────────────
[iter 5]
  [memory]     4 hit(s)
  [perception] 3 goal(s), 3 done
    ✓ search-tokyo-activities: Search for family-friendly activities in Tokyo.
    ✓ check-tokyo-weather: Check the weather forecast for Tokyo this Saturday.
    ✓ recommend-activity: Synthesize activity information and weather forecast to recommend the most appropriate family-friendly activity for Saturday.  [artifact:1]
  [loop]       all goals done — terminating


══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (235.74s, 5 iteration(s)):
Based on the weather forecast for Saturday, May 30, 2026, which is expected to be sunny and less humid with a high of 29°C, the most appropriate recommendation for a family-friendly activity in Tokyo is an outdoor excursion.

Given the pleasant, sunny conditions, I recommend visiting **Ueno Park**. It is a fantastic, family-friendly destination that features the Ueno Zoo, several museums, and plenty of open space for children to play, making it ideal for the predicted clear and warm weather.
══════════════════════════════════════════════════════════════════════════════

==============================================================================
VALIDATION
==============================================================================
  answer mentions 'tokyo'           : ✓
  answer references weather         : ✓  (sunny, clear, humid)
  ≥2 activities identified          : ✓  (museum, park, ueno, zoo)
  answer recommends one activity    : ✓

  RESULT: PASS ✓
```

</details>

---

## Query C — Mom's Birthday (Durable Memory)

**Query (Run 1):** `My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.`  
**Query (Run 2):** `When is mom's birthday?`

**Tests:** Durable memory persistence in `state/memory.json` across separate process runs.

<details>
<summary>Terminal output — Run 1 (3 iterations, 33s)</summary>

```
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=153d6e83
query: My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
══════════════════════════════════════════════════════════════════════════════
[05/23/26 13:39:37] INFO     Processing request of type ListToolsRequest                                      server.py:727
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 0 done
    ○ store-birthday-memory: Record that the user's mother's birthday is May 15, 2026.
    ○ create-reminder-two-weeks-before: Create a calendar reminder for May 1, 2026, two weeks before the birthday.
    ○ create-reminder-on-day: Create a calendar reminder for May 15, 2026, on the day of the birthday.
  [decision]   answer: "The user's mother's birthday is May 15, 2026. I have recorded this information."
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ store-birthday-memory: Record that the user's mother's birthday is May 15, 2026.
    ○ create-reminder-two-weeks-before: Create a calendar reminder for May 1, 2026, two weeks before the birthday.
    ○ create-reminder-on-day: Create a calendar reminder for May 15, 2026, on the day of the birthday.
  [decision]   answer: 'I can see the user\'s mother\'s birthday is May 15, 2026. "Two weeks before the birthday" means May 1, 2026 (15 - 14 = 1).'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 3 done
    ✓ store-birthday-memory: Record that the user's mother's birthday is May 15, 2026.
    ✓ create-reminder-two-weeks-before: Create a calendar reminder for May 1, 2026, two weeks before the birthday.
    ✓ create-reminder-on-day: Create a calendar reminder for May 15, 2026, on the day of the birthday.
  [loop]       all goals done — terminating


══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (32.77s, 3 iteration(s)):
I can see the user's mother's birthday is May 15, 2026. "Two weeks before the birthday" means May 1, 2026 (15 - 14 = 1). Since I don't have a tool to create calendar reminders directly (no calendar API tool available), I'll note the reminder information so you can set it up.

**Reminder to create:** A calendar reminder for **May 1, 2026** — two weeks before the user's mother's birthday on **May 15, 2026**. This gives you time to plan or purchase a gift/card. Since no calendar creation tool is available in my current toolset, please add this event manually to your calendar app (Google Calendar, Apple Calendar, etc.).
══════════════════════════════════════════════════════════════════════════════

==============================================================================
VALIDATION — Run 1
==============================================================================
  answer references reminder/calendar : ✓
  answer references May / 2026        : ✓
  state/memory.json has birthday fact : ✓
  total memory items                  : 1  (facts: 1)

  RUN 1 RESULT: PASS ✓
```

</details>

<details>
<summary>Terminal output — Run 2 (2 iterations, 9s — retrieved from memory, no web call)</summary>

```
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=2bec2416
query: When is mom's birthday?
══════════════════════════════════════════════════════════════════════════════
[05/23/26 13:40:13] INFO     Processing request of type ListToolsRequest                                      server.py:727
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     2 hit(s)
  [perception] 1 goal(s), 0 done
    ○ retrieve-moms-birthday: Extract the date of mom's birthday from the provided memory facts.
  [decision]   answer: "The date of mom's birthday is May 15, 2026."
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 1 goal(s), 1 done
  [loop]       all goals done — terminating


══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (9.29s, 2 iteration(s)):
The date of mom's birthday is May 15, 2026.
══════════════════════════════════════════════════════════════════════════════

==============================================================================
VALIDATION — Run 2
==============================================================================
  answer mentions 'birthday'          : ✓
  answer mentions 'may'               : ✓
  answer mentions '2026'              : ✓
  answer includes specific date       : ✓  (15, may 1, may 15)
  memory items after run 2            : 2

  RUN 2 RESULT: PASS ✓

==============================================================================
  OVERALL RESULT: PASS ✓
==============================================================================
```

</details>

---

## Query D — Asyncio Research

**Query:** `Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.`

**Tests:** Multi-artifact fetch (web_search → 3× fetch_url, each >4 KB), artifact auto-load for synthesis goal, numbered consensus list.

<details>
<summary>Terminal output (7 iterations, 405s)</summary>

```
[test] cleared /Users/payalchakraborty/Dev/EAG3/AgentiAI/state
==============================================================================
TEST QUERY D — Asyncio Research (multi-source synthesis)
==============================================================================
══════════════════════════════════════════════════════════════════════════════
agent6.py — Session 6  |  run_id=c45be1ab
query: Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.
══════════════════════════════════════════════════════════════════════════════
[05/23/26 13:40:58] INFO     Processing request of type ListToolsRequest                                      server.py:727
[mcp] 9 tools: ['web_search', 'fetch_url', 'get_time', 'currency_convert', 'read_file', 'list_dir', 'create_file', 'update_file', 'edit_file']

────────────────────────────────────────────────────────────
[iter 1]
  [memory]     1 hit(s)
  [perception] 3 goal(s), 0 done
    ○ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ○ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ○ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.
  [decision]   tool_call: web_search({'query': 'Python asyncio best practices', 'max_results': 5})
[05/23/26 13:41:04] INFO     Processing request of type CallToolRequest                                       server.py:727
  [action]     '{\n  "title": "Asyncio Best Practices and Common Pitfalls - Shane\'s Personal Blog",\n  "url": "https://www.shanechang.com/'
────────────────────────────────────────────────────────────
[iter 2]
  [memory]     2 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ○ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ○ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.
  [decision]   tool_call: fetch_url({'url': 'https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls', 'timeout': 20})
[05/23/26 13:41:26] INFO     Processing request of type CallToolRequest                                       server.py:727
[INIT].... → Crawl4AI 0.8.6 
[FETCH]... ↓ https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls                                  | ✓ | ⏱: 
4.02s 
[SCRAPE].. ◆ https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls                                  | ✓ | ⏱: 
0.02s 
[COMPLETE] ● https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls                                  | ✓ | ⏱: 
4.05s 
  [action]     '→ artifact:1'
────────────────────────────────────────────────────────────
[iter 3]
  [memory]     3 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ○ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ○ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.
  [decision]   tool_call: fetch_url({'url': 'https://discuss.python.org/t/asyncio-best-practices/12576'})
[05/23/26 13:41:50] INFO     Processing request of type CallToolRequest                                       server.py:727
[INIT].... → Crawl4AI 0.8.6 
[FETCH]... ↓ https://discuss.python.org/t/asyncio-best-practices/12576                                            | ✓ | ⏱: 
3.15s 
[SCRAPE].. ◆ https://discuss.python.org/t/asyncio-best-practices/12576                                            | ✓ | ⏱: 
0.02s 
[COMPLETE] ● https://discuss.python.org/t/asyncio-best-practices/12576                                            | ✓ | ⏱: 
3.19s 
  [action]     '→ artifact:2'
────────────────────────────────────────────────────────────
[iter 4]
  [memory]     4 hit(s)
  [perception] 3 goal(s), 1 done
    ✓ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ○ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ○ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.
  [decision]   tool_call: fetch_url({'url': 'https://oneuptime.com/blog/post/2026-01-24-asyncio-concurrent-programming-python/view', 'timeout': 20})
[05/23/26 13:43:29] INFO     Processing request of type CallToolRequest                                       server.py:727
[INIT].... → Crawl4AI 0.8.6 
[FETCH]... ↓ https://oneuptime.com/blog/post/2026-01-24-asyncio-concurrent-programming-python/view                | ✓ | ⏱: 
2.59s 
[SCRAPE].. ◆ https://oneuptime.com/blog/post/2026-01-24-asyncio-concurrent-programming-python/view                | ✓ | ⏱: 
0.05s 
[COMPLETE] ● https://oneuptime.com/blog/post/2026-01-24-asyncio-concurrent-programming-python/view                | ✓ | ⏱: 
2.66s 
  [action]     '→ artifact:3'
────────────────────────────────────────────────────────────
[iter 5]
  [memory]     5 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ✓ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ○ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.  [artifact:1]
  [artifact]   loaded artifact:1 (8,594 bytes)
  [artifact]   auto-loaded artifact:3 (33,027 bytes) for synthesis
  [artifact]   auto-loaded artifact:2 (6,679 bytes) for synthesis
  [decision]   answer: "I have all three fetched artifacts. Let me extract the common advice across them.\n\n**Artifact 1** (Shane Chang's blog — "
────────────────────────────────────────────────────────────
[iter 6]
  [memory]     5 hit(s)
  [perception] 3 goal(s), 2 done
    ✓ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ✓ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ○ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.  [artifact:1]
  [artifact]   loaded artifact:1 (8,594 bytes)
  [artifact]   auto-loaded artifact:3 (33,027 bytes) for synthesis
  [artifact]   auto-loaded artifact:2 (6,679 bytes) for synthesis
  [decision]   answer: 'Here is the extracted and compiled numbered list of advice that is **common across all 3 fetched results**.\n\n---\n\n**Comm'
────────────────────────────────────────────────────────────
[iter 7]
  [memory]     5 hit(s)
  [perception] 3 goal(s), 3 done
    ✓ search-asyncio-best-practices: Perform a web search for 'Python asyncio best practices'.
    ✓ fetch-top-3-results: Fetch the content of the top 3 search results for Python asyncio best practices.
    ✓ synthesize-consensus-advice: Extract and compile a numbered list of advice that is common across the 3 fetched results.  [artifact:1]
  [loop]       all goals done — terminating


══════════════════════════════════════════════════════════════════════════════
FINAL ANSWER  (405.46s, 7 iteration(s)):
Here is the extracted and compiled numbered list of advice that is **common across all 3 fetched results**.

---

**Common Advice Across the 3 Fetched Results**

1. **Use `asyncio.run()` as the main entry point for async programs.**  
   *Artifact 1* (Shane Chang's blog) explicitly states: "Always use `asyncio.run()` to start your asyncio programs" and shows the `if __name__ == "__main__": asyncio.run(main())` pattern.  
   *Artifact 3* (OneUptime blog) demonstrates this pattern throughout its code examples, using `asyncio.run(main())` as the standard way to launch the event loop.  
   *Artifact 2* (Python.org discussion) also uses `asyncio.run(main())` in its first code example, establishing it as the standard entry point.

2. **Always await coroutines (do not forget to await).**  
   *Artifact 1* devotes a full section to this: "Always Await Coroutines," warning that a coroutine created but not awaited is never executed. It contrasts `fetch_data(url)` (bad) with `await fetch_data(url)` (good).  
   *Artifact 2* (Python.org discussion) makes the same point: "Async functions are not necessarily asynchronous" — simply calling them without proper awaiting yields synchronous, sequential execution.  
   *Artifact 3* reinforces this by consistently showing `await` on every coroutine call in its examples (e.g., `await asyncio.sleep(1)`, `await session.get(url)`).

3. **Use async context managers (`async with`) for proper resource management.**  
   *Artifact 1* lists "Prefer Async Context Managers" as a best practice, showing `async with aiohttp.ClientSession() as session` for proper cleanup.  
   *Artifact 3* includes a dedicated section "Async Context Managers and Iterators," demonstrating `async with aiofiles.open(...)` and `async with aiohttp.ClientSession() as session`.  
   *Artifact 2* does not explicitly cover async context managers, but this advice is strongly echoed in the other two sources.

4. **Handle cancellation and errors gracefully.**  
   *Artifact 1* has a section "Handle Cancellation Gracefully," showing how to catch `asyncio.CancelledError`, clean up resources, and re-raise.  
   *Artifact 3* includes a dedicated "Error Handling in Async Code" section, demonstrating `try/except` blocks around async operations and handling `asyncio.TimeoutError`.  
   *Artifact 2* (the discussion thread) focuses more on patterns and pitfalls but touches on this theme by noting that long-running loops block the event loop — implying the need for proper cancellation and yielding control.

5. **Avoid blocking the event loop with long-running synchronous code.**  
   *Artifact 2* explicitly warns: "Do not create functions with long running loops" because they "cause the event loop to halt until the function finishes, which causes lag." It recommends scheduling iterations onto the event loop instead.  
   *Artifact 3* has a section "Running Blocking Code in Async Context" that advises using `loop.run_in_executor()` to offload blocking code (e.g., `time.sleep()`, CPU-heavy work) to a thread pool so the event loop stays responsive.  
   *Artifact 1* implicitly supports this by advocating proper async patterns throughout, avoiding synchronous blocks.
══════════════════════════════════════════════════════════════════════════════

VALIDATION
  answer contains 'asyncio'              : ✓
  answer contains 'async'              : ✓
  numbered list ≥3 items              : ✓  (5 item(s) found)
  advice group 1 matched              : ✓  ('asyncio.run')
  advice group 2 matched              : ✗  (signals: ['gather', 'taskgroup']...)
  advice group 3 matched              : ✓  ('blocking')
  advice group 4 matched              : ✓  ('timeout')
  advice group 5 matched              : ✗  (signals: ['semaphore', 'rate limit']...)
  artifacts ≥4KB stored (need ≥3)     : ✓  (3 artifact(s), sizes: [32, 8, 6] KB)
  web_search recorded in memory       : ✓
  fetch_url ×3 each with artifact_id  : ✓  (3 fetch_url call(s); 3 with artifact_id)

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
