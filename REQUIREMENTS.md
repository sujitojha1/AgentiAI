# Requirements Specification — AgentiAI Session 6: Agentic Architecture

> **Standard**: IEEE 830 / ISO/IEC 29148 · **Format**: EARS (Easy Approach to Requirements Syntax)
> **Project**: AgentiAI — EAG V3 Session 6 Assignment
> **Repo**: sujitojha1/AgentiAI
> **Date**: 2025-05-16
> **Status Legend**: ✅ Met · ❌ Not Met · 🔄 In Progress · ⬜ Not Started

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [Constraints](#5-constraints)
6. [Traceability Matrix](#6-traceability-matrix)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for the **AgentiAI Session 6** assignment. It provides full traceability between stated requirements, implementation issues, and verification test cases, following IEEE 830 / ISO/IEC 29148 conventions and EARS syntax.

### 1.2 Scope

The system is a multi-role agentic AI that decomposes user queries into bounded goals and solves them iteratively through four cognitive roles: **Memory**, **Perception**, **Decision**, and **Action**. All LLM calls are routed through LLM Gateway V3; all tool calls use MCP stdio transport.

### 1.3 Definitions

| Term | Definition |
|------|-----------|
| EARS | Easy Approach to Requirements Syntax (shall / when / where / while / if-then) |
| MCP | Model Context Protocol — stdio-transport tool dispatch |
| Pydantic V2 | Python data-validation library used for typed role contracts |
| ArtifactStore | Content-addressable binary store for large payloads > 4 KB |
| LLM Gateway V3 | Local proxy at localhost:8101 routing all LLM calls |
| Goal | A bounded sub-task emitted by Perception with a done flag |

### 1.4 References

| Ref | Source |
|-----|--------|
| [ISSUE-3] | Setup: Project structure, uv environment, .env config, llm_gatewayV3 running |
| [ISSUE-4] | Implement schemas.py — Pydantic v2 contracts for all role boundaries |
| [ISSUE-5] | Implement memory.py — typed Memory service with read, write, and persist |
| [ISSUE-6] | Implement action.py — ArtifactStore + pure MCP dispatch |
| [ISSUE-7] | Implement perception.py — Orchestrator with goal decomposition and tracking |
| [ISSUE-8] | Implement decision.py — single LLM call returning answer or tool_call |
| [ISSUE-9] | Implement agent6.py — main agent loop wiring all four roles |
| [ISSUE-10] | Test Query A: Shannon Wikipedia — artifact attach path |
| [ISSUE-11] | Test Query B: Tokyo activities with weather — multi-goal + memory carryover |
| [ISSUE-12] | Test Query C: Mom's birthday — durable memory across two runs |
| [ISSUE-13] | Test Query D: Asyncio research — multi-source synthesis |
| [ISSUE-14] | Deliverables: Capture terminal output, record YouTube demo, extract prompts |
| [ISSUE-15] | Documenting project requirement to give traceability to project completion |

---

## 2. System Overview

Control flow per iteration:

```
memory.read(query, history)         → hits[]
perception.observe(query, hits)     → Observation(goals)
[if all goals done]                 → break
decision.next_step(goal, hits)      → DecisionOutput (answer | tool_call)
[if answer]                         → append to history, continue
action.execute(tool_call)           → (descriptor, artifact_id?)
memory.record_outcome(...)
append to history, iterate
```

---

## 3. Functional Requirements

> **Syntax**: EARS — *"The system shall …"*, *"When [trigger], the system shall …"*, *"If [condition], then the system shall …"*

---

### FR-01 Project Setup

**Reference**: [ISSUE-3] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01.1 | The system shall manage all Python dependencies using `uv` (no manual virtualenv activation). | Must Have | ⬜ |
| FR-01.2 | The system shall read all API keys (GEMINI_API_KEY, TAVILY_API_KEY, etc.) from a `.env` file. | Must Have | ⬜ |
| FR-01.3 | The system shall exclude the `state/` directory from version control via `.gitignore`. | Must Have | ⬜ |
| FR-01.4 | When LLM Gateway V3 is started, it shall be accessible at `localhost:8101` and respond to a health-check endpoint. | Must Have | ⬜ |
| FR-01.5 | The repository shall follow the module structure: agent6.py, memory.py, perception.py, decision.py, action.py, schemas.py, mcp_server.py. | Must Have | ⬜ |

---

### FR-02 Pydantic Schemas

**Reference**: [ISSUE-4] · **Status**: ✅ Met

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-02.1 | The system shall define a `MemoryItem` Pydantic v2 model with fields: kind in {fact, preference, tool_outcome, scratchpad}, keywords, descriptor, value, artifact_id. | Must Have | ✅ |
| FR-02.2 | The system shall define an `Artifact` Pydantic v2 model with content-addressable handle, content_type, size_bytes, descriptor. | Must Have | ✅ |
| FR-02.3 | The system shall define a `Goal` Pydantic v2 model with fields: id, text, done: bool, attach_artifact_id. | Must Have | ✅ |
| FR-02.4 | The system shall define an `Observation` Pydantic v2 model containing goals: list[Goal]. | Must Have | ✅ |
| FR-02.5 | The system shall define a `ToolCall` Pydantic v2 model with fields: name, arguments: dict. | Must Have | ✅ |
| FR-02.6 | The system shall define a `DecisionOutput` Pydantic v2 model where exactly one of answer or tool_call is populated. | Must Have | ✅ |
| FR-02.7 | All inter-role data shall be exchanged exclusively via the Pydantic v2 schemas defined in schemas.py. | Must Have | ✅ |

---

### FR-03 Memory Module

**Reference**: [ISSUE-5] · **Status**: ✅ Met

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-03.1 | The Memory module shall expose a `read(query, history, kinds, top_k=8)` method returning keyword-overlap ranked MemoryItem hits using pure Python (no LLM). | Must Have | ✅ |
| FR-03.2 | The Memory module shall expose a `record_outcome(tool_call, result_text, artifact_id, ...)` method that creates a kind=tool_outcome MemoryItem and persists it to state/memory.json without any LLM call. | Must Have | ✅ |
| FR-03.3 | When classifying raw text via `remember()`, the Memory module shall make a single LLM call pinned to Gemini (provider="gemini") to determine kind, keywords, descriptor, value, and confidence. | Must Have | ✅ |
| FR-03.4 | The Memory module shall persist all stored items to `state/memory.json` so that data survives process restarts; items shall be loaded lazily on first access and written after every update. | Must Have | ✅ |
| FR-03.5 | The Memory module shall expose a `filter(kinds, goal_id, recent)` method for exact-match structured retrieval and a `relevant(query, kinds, top_k=5)` method for LLM-scored retrieval via gateway auto_route="memory". | Should Have | ✅ |

---

### FR-04 Perception Module

**Reference**: [ISSUE-7] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-04.1 | The Perception module shall act as the orchestrator: on every iteration it shall read the query, memory hits, and history, then emit a typed Observation(goals). | Must Have | ⬜ |
| FR-04.2 | The Perception module shall make one LLM call per iteration, pinned to Gemini via provider="g". | Must Have | ⬜ |
| FR-04.3 | When all goals in the Observation have done=True, the Perception module shall signal loop termination. | Must Have | ⬜ |
| FR-04.4 | The Perception module shall support multi-goal decomposition (emit more than one Goal per query when appropriate). | Must Have | ⬜ |
| FR-04.5 | If a goal has an attach_artifact_id, the Perception module shall include the artifact reference in the next iteration context. | Must Have | ⬜ |

---

### FR-05 Decision Module

**Reference**: [ISSUE-8] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-05.1 | The Decision module shall make exactly one LLM call per unfinished goal per iteration. | Must Have | ⬜ |
| FR-05.2 | The Decision module shall return a DecisionOutput where either answer or tool_call is populated, never both. | Must Have | ⬜ |
| FR-05.3 | When DecisionOutput.answer is populated, the agent loop shall append the answer to history and continue without dispatching a tool. | Must Have | ⬜ |
| FR-05.4 | When DecisionOutput.tool_call is populated, the agent loop shall pass it to the Action module for execution. | Must Have | ⬜ |

---

### FR-06 Action Module

**Reference**: [ISSUE-6] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-06.1 | The Action module shall dispatch all tool calls via MCP stdio transport and shall make no LLM calls. | Must Have | ⬜ |
| FR-06.2 | When a tool response payload exceeds 4 KB, the Action module shall store it in the ArtifactStore and return an artifact_id instead of inline content. | Must Have | ⬜ |
| FR-06.3 | The ArtifactStore shall use content-addressable naming: art:<sha256-prefix>.bin for payload and .json for metadata. | Must Have | ⬜ |
| FR-06.4 | The Action module shall return a (descriptor, artifact_id?) tuple to the agent loop for each executed tool call. | Must Have | ⬜ |

---

### FR-07 Agent Loop

**Reference**: [ISSUE-9] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-07.1 | agent6.py shall wire the four roles (Memory, Perception, Decision, Action) into a single iterative loop following the defined control flow. | Must Have | ⬜ |
| FR-07.2 | The agent loop shall terminate when Perception reports all goals as done=True. | Must Have | ⬜ |
| FR-07.3 | The agent loop shall maintain a running history list across iterations, appending each answer or tool outcome. | Must Have | ⬜ |
| FR-07.4 | The agent loop shall call memory.record_outcome() after each Action execution. | Must Have | ⬜ |
| FR-07.5 | The system shall use no third-party agentic frameworks (LangGraph, LangChain, CrewAI, etc.). | Must Have | ⬜ |

---

### FR-08 MCP Server

**Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-08.1 | mcp_server.py shall expose at least 9 tools via MCP stdio transport: web_search, fetch_url, get_time, currency_convert, read_file, list_dir, create_file, update_file, edit_file. | Must Have | ⬜ |
| FR-08.2 | All tool calls from the Action module shall be dispatched exclusively through mcp_server.py. | Must Have | ⬜ |

---

### FR-09 LLM Gateway

**Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-09.1 | LLM Gateway V3 shall be the sole substrate for all LLM calls in Memory, Perception, and Decision modules. | Must Have | ⬜ |
| FR-09.2 | LLM Gateway V3 shall support auto_route for Perception/Memory/Decision tiers. | Must Have | ⬜ |
| FR-09.3 | LLM Gateway V3 shall support structured output via response_format. | Must Have | ⬜ |
| FR-09.4 | LLM Gateway V3 shall be running at localhost:8101 before the agent is started. | Must Have | ⬜ |

---

### FR-10 Test Queries

#### FR-10-A: Shannon Wikipedia (Artifact Attach Path)

**Reference**: [ISSUE-10] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-10-A.1 | When given Query A, the system shall fetch https://en.wikipedia.org/wiki/Claude_Shannon and extract his birth date, death date, and three key contributions to information theory. | Must Have | ⬜ |
| FR-10-A.2 | When the fetched Wikipedia page exceeds 4 KB, the system shall store it in the ArtifactStore and attach the artifact to the next Perception goal. | Must Have | ⬜ |
| FR-10-A.3 | The final answer for Query A shall include the birth date, death date, and three contributions as verified by terminal output. | Must Have | ⬜ |

#### FR-10-B: Tokyo Activities with Weather (Multi-Goal + Memory Carryover)

**Reference**: [ISSUE-11] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-10-B.1 | When given Query B, the system shall decompose the query into at least two goals: finding activities and checking weather. | Must Have | ⬜ |
| FR-10-B.2 | The system shall retrieve Saturday's Tokyo weather forecast using a tool call. | Must Have | ⬜ |
| FR-10-B.3 | The system shall carry memory across iterations to correlate the weather forecast with the activity recommendations. | Must Have | ⬜ |
| FR-10-B.4 | The final answer for Query B shall recommend the most weather-appropriate of the three activities. | Must Have | ⬜ |

#### FR-10-C: Mom's Birthday (Durable Memory Across Two Runs)

**Reference**: [ISSUE-12] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-10-C.1 | When given Run 1 of Query C, the system shall store 15 May 2026 as a durable MemoryItem in state/memory.json. | Must Have | ⬜ |
| FR-10-C.2 | When given Run 1 of Query C, the system shall produce calendar reminders for two weeks before and on the birthday. | Must Have | ⬜ |
| FR-10-C.3 | When given Run 2 of Query C in a separate process, the system shall retrieve the birthday from state/memory.json without re-asking. | Must Have | ⬜ |

#### FR-10-D: Asyncio Research (Multi-Source Synthesis)

**Reference**: [ISSUE-13] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-10-D.1 | When given Query D, the system shall search for 'Python asyncio best practices' and fetch the top 3 results. | Must Have | ⬜ |
| FR-10-D.2 | The system shall store each fetched result in the ArtifactStore if > 4 KB and attach artifact references to subsequent goals. | Must Have | ⬜ |
| FR-10-D.3 | The final answer for Query D shall provide a numbered list of advice that appears across multiple sources. | Must Have | ⬜ |

---

### FR-11 Deliverables

**Reference**: [ISSUE-14] · **Status**: ⬜ Not Started

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-11.1 | The repository shall contain four code modules with clear separation of concerns: memory.py, perception.py, decision.py, action.py, plus agent6.py and schemas.py. | Must Have | ⬜ |
| FR-11.2 | All four target queries (A–D) shall produce correct final answers; terminal output shall be captured from a clean state/ directory. | Must Have | ⬜ |
| FR-11.3 | Memory persistence across runs shall be verified for Query C (state/memory.json durable-memory behaviour). | Must Have | ⬜ |
| FR-11.4 | All four cognitive layers shall be backed by typed Pydantic v2 contracts. | Must Have | ⬜ |
| FR-11.5 | The state/ directory shall be excluded by .gitignore and be cleanable between attempts. | Must Have | ⬜ |
| FR-11.6 | The README shall include actual terminal output for all four queries. | Must Have | ⬜ |
| FR-11.7 | A YouTube demo link shall be included, showing all four queries end-to-end. | Must Have | ⬜ |
| FR-11.8 | Perception and Decision prompts and a Validation JSON (Proof of Prompt) shall be extracted and included in the repository. | Must Have | ⬜ |

---

## 4. Non-Functional Requirements

| ID | Category | Requirement | Priority | Status |
|----|----------|-------------|----------|--------|
| NFR-01 | Correctness | The system shall produce factually correct answers for all four test queries as validated against known ground truth. | Must Have | ⬜ |
| NFR-02 | Modularity | Each cognitive role shall be implemented in its own Python module; no role shall directly call another role's internal functions. | Must Have | ⬜ |
| NFR-03 | Typed Contracts | All inter-module data transfer shall use Pydantic v2 models; no raw dict passing between roles. | Must Have | ⬜ |
| NFR-04 | Dependency Mgmt | All Python packages shall be declared and installed via uv; no pip install commands shall be required. | Must Have | ⬜ |
| NFR-05 | Reproducibility | The state/ directory shall be cleanable without loss of code; re-running after cleaning shall produce the same final answers. | Must Have | ⬜ |
| NFR-06 | No Framework Lock-in | The solution shall not depend on LangGraph, LangChain, CrewAI, or any equivalent agentic framework. | Must Have | ⬜ |
| NFR-07 | Auditability | The terminal output for all four queries shall be captured and committed to the repository for external verification. | Should Have | ⬜ |
| NFR-08 | Licensing | The project shall be licensed under Apache 2.0. | Should Have | ✅ |

---

## 5. Constraints

| ID | Constraint | Source |
|----|-----------|--------|
| CON-01 | Python >= 3.11 | Assignment spec |
| CON-02 | Pydantic v2 on every role boundary | Assignment spec |
| CON-03 | uv for Python dependency management — no manual virtualenv | Assignment spec |
| CON-04 | MCP server stdio transport for all tool calls | Assignment spec |
| CON-05 | No third-party agentic frameworks (LangGraph, LangChain, CrewAI, etc.) | Assignment spec |
| CON-06 | LLM Gateway V3 must be running at localhost:8101 before agent start | Assignment spec |
| CON-07 | state/ directory excluded by .gitignore | Assignment spec |

---

## 6. Traceability Matrix

| Req ID | Description | GitHub Issue | Source File | Verification Method | Status |
|--------|-------------|-------------|-------------|---------------------|--------|
| FR-01.1–5 | Project Setup | [#3](https://github.com/sujitojha1/AgentiAI/issues/3) | .env, .gitignore, pyproject.toml | Manual setup check | ⬜ |
| FR-02.1–7 | Pydantic Schemas | [#4](https://github.com/sujitojha1/AgentiAI/issues/4) | schemas.py | Unit test schema instantiation | ✅ |
| FR-03.1–5 | Memory Module | [#5](https://github.com/sujitojha1/AgentiAI/issues/5) | memory.py | Query C (durable memory) | ✅ |
| FR-04.1–5 | Perception Module | [#7](https://github.com/sujitojha1/AgentiAI/issues/7) | perception.py | All queries (goal decomposition) | ⬜ |
| FR-05.1–4 | Decision Module | [#8](https://github.com/sujitojha1/AgentiAI/issues/8) | decision.py | All queries (answer/tool dispatch) | ⬜ |
| FR-06.1–4 | Action Module | [#6](https://github.com/sujitojha1/AgentiAI/issues/6) | action.py | Query A, D (ArtifactStore path) | ⬜ |
| FR-07.1–5 | Agent Loop | [#9](https://github.com/sujitojha1/AgentiAI/issues/9) | agent6.py | All queries (end-to-end) | ⬜ |
| FR-08.1–2 | MCP Server | — | mcp_server.py | Tool call dispatch tests | ⬜ |
| FR-09.1–4 | LLM Gateway | — | llm_gatewayV3/ | Gateway health check | ⬜ |
| FR-10-A.1–3 | Query A: Shannon | [#10](https://github.com/sujitojha1/AgentiAI/issues/10) | agent6.py | Terminal output — Query A | ⬜ |
| FR-10-B.1–4 | Query B: Tokyo | [#11](https://github.com/sujitojha1/AgentiAI/issues/11) | agent6.py | Terminal output — Query B | ⬜ |
| FR-10-C.1–3 | Query C: Birthday | [#12](https://github.com/sujitojha1/AgentiAI/issues/12) | memory.py, agent6.py | Two-run memory persistence test | ⬜ |
| FR-10-D.1–3 | Query D: Asyncio | [#13](https://github.com/sujitojha1/AgentiAI/issues/13) | agent6.py | Terminal output — Query D | ⬜ |
| FR-11.1–8 | Deliverables | [#14](https://github.com/sujitojha1/AgentiAI/issues/14) | README, YouTube, PoP JSON | Deliverable checklist review | ⬜ |
| NFR-01–08 | Non-Functional | — | All modules | Code review + output audit | ⬜ |

---

*This requirements document follows IEEE 830 / ISO/IEC 29148 structure and EARS syntax.*
*Update the Status column (⬜ → ✅ / ❌ / 🔄) as each requirement is implemented and verified.*
