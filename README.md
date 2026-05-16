# AgentiAI — Session 6: Agentic Architecture

> **EAG V3 · Session 6 Assignment** — Build a multi-role agentic system with four cognitive layers, typed Pydantic contracts, durable memory, and MCP tool dispatch.
>
> ---
>
> ## Overview
>
> This repository implements the **Session 6 Agentic Architecture** from the EAG V3 course at The School of AI. The agent decomposes user queries into bounded goals and solves them iteratively through four named cognitive roles: **Memory**, **Perception**, **Decision**, and **Action** — each backed by typed Pydantic contracts and wired together by a central agent loop.
>
> The LLM Gateway V3 (`localhost:8101`) is the sole substrate for every LLM call. MCP stdio transport handles all tool dispatch. No third-party agentic frameworks are used.
>
> ---
>
> ## Architecture
>
> The agent is structured around four cognitive roles that communicate via typed Pydantic schemas:
>
> | Role | Responsibility | LLM Call? |
> |------|---------------|-----------|
> | **Memory** | Typed service storing facts, preferences, tool outcomes, and scratchpad entries. Exposes `read()` and `record_outcome()`. | Only for ambiguous classification writes |
> | **Perception** | Orchestrator. Reads query + memory hits + history, emits a typed goal list with `done` flags. Runs every iteration. | Yes — every iteration (pinned to Gemini via `provider="g"`) |
> | **Decision** | Picks next action for one bounded goal. Returns either a plain-text answer or a single `ToolCall`. | Yes — once per iteration when a goal is unfinished |
> | **Action** | Pure MCP dispatch. Pushes large payloads (>4 KB) to the artifact store. No LLM call. | No |
>
> Two supporting components:
> - **ArtifactStore** — content-addressable file store for raw bytes (fetched pages, large tool outputs)
> - - **LLM Gateway V3** — routes all LLM calls; supports `auto_route` for perception/memory/decision tiers and structured output via `response_format`
>  
>   - ### Control Flow
>  
>   - ```
>     Each iteration:
>       memory.read(query, history)          → hits[]
>       perception.observe(query, hits, ...) → Observation(goals)
>       [if all goals done] → break
>       decision.next_step(goal, hits, ...)  → DecisionOutput (answer | tool_call)
>       [if answer] → append to history, continue
>       action.execute(tool_call)            → (descriptor, artifact_id?)
>       memory.record_outcome(...)
>       append to history, iterate
>     ```
>
> ---
>
> ## Module Structure
>
> ```
> AgentiAI/
> ├── agent6.py          # Main agent loop — wires all four roles
> ├── memory.py          # Memory service (read, remember, record_outcome, filter, relevant)
> ├── perception.py      # Perception role — goal decomposition and tracking
> ├── decision.py        # Decision role — answer or tool_call selection
> ├── action.py          # Action role — pure MCP tool dispatch + artifact storage
> ├── schemas.py         # Pydantic v2 contracts: MemoryItem, Goal, Observation, ToolCall, DecisionOutput, Artifact
> ├── mcp_server.py      # MCP server exposing 9 tools (web_search, fetch_url, get_time, currency_convert, read_file, list_dir, create_file, update_file, edit_file)
> ├── llm_gatewayV3/     # LLM Gateway V3 — routes all LLM calls
> ├── state/             # Runtime state (excluded from git)
> │   ├── memory.json    # Durable memory persisted across runs
> │   └── artifacts/     # Binary artifact store (art:<sha256-prefix>.bin + .json)
> ├── .gitignore
> ├── LICENSE
> └── README.md
> ```
>
> ---
>
> ## Pydantic Contracts
>
> Every boundary between roles is a Pydantic v2 model defined in `schemas.py`:
>
> - `MemoryItem` — kind ∈ {fact, preference, tool_outcome, scratchpad}, keywords, descriptor, value, artifact_id
> - - `Artifact` — content-addressable handle (`art:<sha256-prefix>`), content_type, size_bytes, descriptor
>   - - `Goal` — id, text, done: bool, attach_artifact_id
>     - - `Observation` — goals: list[Goal]
>       - - `ToolCall` — name, arguments: dict
>         - - `DecisionOutput` — answer: str | None, tool_call: ToolCall | None (exactly one populated)
>          
>           - ---
>
> ## Setup & Usage
>
> ### Prerequisites
>
> - Python 3.11+
> - - `uv` for dependency management
>   - - A `.env` file with API keys for: Gemini, Tavily, DuckDuckGo (ddgs), Crawl4AI
>     - - LLM Gateway V3 running at `localhost:8101`
>      
>       - ### Install & Run
>      
>       - ```bash
>         # Install dependencies with uv
>         uv sync
>
>         # Start the LLM Gateway V3
>         cd llm_gatewayV3 && uv run python gateway.py
>
>         # Run the agent
>         uv run python agent6.py
>         ```
>
> ---
>
> ## Assignment Target Queries
>
> The agent must correctly answer all four target queries:
>
> ### Query A — Shannon Wikipedia (artifact attach test)
> ```
> Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his
> birth date, death date, and three key contributions to information theory.
> ```
> **Tests:** artifact attachment path (250 KB page → ArtifactStore → Perception attaches to next goal)
>
> ### Query B — Tokyo activities with weather constraint (multi-goal + memory carryover)
> ```
> Find 3 family-friendly things to do in Tokyo this weekend.
> Check Saturday's weather forecast there and tell me which one is most appropriate.
> ```
> **Tests:** multi-goal decomposition, sequential tool calls, memory carryover across iterations
>
> ### Query C — Mom's birthday (durable memory across two runs)
> ```
> Run 1: My mom's birthday is 15 May 2026. Remember that and give me
>        a calendar reminder for two weeks before and on the day.
> Run 2: When is mom's birthday?
> ```
> **Tests:** durable memory persistence in `state/memory.json` across separate runs
>
> ### Query D — Asyncio research (multi-source synthesis)
> ```
> Search for 'Python asyncio best practices', read the top 3 results,
> and give me a short numbered list of the advice they agree on.
> ```
> **Tests:** multi-artifact fetch and attachment, synthesis from multiple sources
>
> ---
>
> ## Deliverables
>
> - [x] Four code modules with clear separation of concerns (`memory.py`, `perception.py`, `decision.py`, `action.py`) plus `agent6.py` and `schemas.py`
> - [ ] - [ ] All four target queries produce correct final answers (terminal output captured from clean `state/`)
> - [ ] - [ ] Memory persists across runs in `state/memory.json` (Query C durable-memory behaviour verified)
> - [ ] - [ ] All four cognitive layers backed by typed Pydantic v2 contracts
> - [ ] - [ ] LLM Gateway V3 is the sole substrate for every LLM call
> - [ ] - [ ] `state/` directory excluded by `.gitignore` and cleanable between attempts
> - [ ] - [ ] README includes actual terminal output for all four queries
> - [ ] - [ ] YouTube demo link with all four queries end-to-end
> - [ ] - [ ] Perception and Decision prompt + Validation JSON (Proof of Prompt)
>
> - [ ] ---
>
> - [ ] ## Constraints
>
> - [ ] - Pydantic v2 on every role boundary
> - [ ] - `uv` for Python dependency management — no manual virtualenv activation
> - [ ] - MCP server stdio transport for all tool calls
> - [ ] - No third-party agentic frameworks (LangGraph, LangChain, CrewAI, etc.)
>
> - [ ] ---
>
> - [ ] ## License
>
> - [ ] This project is licensed under the [Apache 2.0 License](LICENSE).
