# CONSIDERATIONS.md — Technical Scenarios & Ideal Behavior

> Prepared for: Mem0 CTO review of Flow
> Focus: Developer-facing use cases only. How does Flow behave when real developers hit real scenarios?
>
> Each scenario includes **Ideal Behavior** and **Actual Behavior** (verified against code + runtime tests on 2026-03-05).

---

## 1. Memory Accuracy

### 1.1 "A developer decides on Redis in session 1, then abandons it in session 5. What does `flow wake` tell them?"

**Ideal Behavior:** mem0's reconciliation produces one current-state memory: *"Switched from Redis to Memcached after Redis proved too complex."* The old fact is updated, not left as a stale duplicate. `flow wake` never surfaces contradictory advice.

**Actual Behavior: GAP.** Runtime-tested against mem0. After adding "chose Redis" then "abandoned Redis, switched to Memcached," mem0 produced **3 separate memories**: (1) "Implemented Redis as the caching layer," (2) "Abandoned Redis due to complexity," (3) "Switched to Memcached." The stale "Implemented Redis" memory persists without noting it was abandoned. mem0's reconciliation did NOT update or delete it — it treated all three as independent facts. `flow wake` could surface the stale Redis memory as if it's still current.

---

### 1.2 "What if a session has zero meaningful work — dev opened the project, read files, closed it?"

**Ideal Behavior:** No git diff + no commits + read-only AI conversation = zero extracted facts. `flow stop` skips the mem0 write entirely: *"No meaningful activity detected — session not stored."* Prevents memory pollution from browsing sessions.

**Actual Behavior: GAP.** Verified in code + test. `Formatter.format()` ([formatter.py:21-37](flow/formatter.py#L21-L37)) produces a chunk even when turns, git_diff, and git_log are all empty: `"Session of 30 minutes in test-project with no recorded AI activity or file changes."` This chunk is then stored to mem0 via `add_chunks()`. Flow does not skip storage for empty sessions — it pollutes the memory store with a "no activity" fact.

---

### 1.3 "After 500+ sessions, does the memory store get noisy?"

**Ideal Behavior:** Quality *improves* over time. mem0's reconciliation refines existing memories rather than appending. Memory count should plateau (not grow linearly). After a year, the store is a curated knowledge base of decisions and patterns — not a log dump.

**Actual Behavior: UNCERTAIN.** Cannot be fully verified without a long-running deployment. However, the 1.1 runtime test suggests mem0's reconciliation is less aggressive than assumed — it ADDs new facts more often than it UPDATEs existing ones. Memory count may grow roughly linearly rather than plateauing. Flow has no pruning, dedup, or compaction logic of its own — it fully delegates to mem0.

---

## 2. Session Lifecycle

### 2.1 "Developer forgets `flow stop` and starts a new session."

**Ideal Behavior:** `flow start` detects the stale session via `state.json`. If the PID is dead: auto-recover by running stop on the stale session first, then start the new one. If the PID is alive (overlapping session): reject with *"Session already active. Run `flow stop` first."*

**Actual Behavior: PARTIAL.** Verified in code ([session.py:87-99](flow/session.py#L87-L99)). `start()` does detect stale sessions and checks PID liveness via `os.kill(pid, 0)`. If PID is dead, it deletes state.json and proceeds. If PID is alive, it rejects. **Gap:** It does NOT auto-run `flow stop` on the stale session — the stale session's data (AI logs, git diff) is silently discarded. Only the state file is cleaned up.

---

### 2.2 "Machine crashes mid-session. No `flow stop` ever runs."

**Ideal Behavior:** Next `flow start` detects the orphaned `state.json` with a dead PID. Attempts crash recovery: reads whatever AI logs and git activity occurred since the session start time. Stores partial data with `recovery: true` metadata. Never silently discards an orphaned session.

**Actual Behavior: GAP.** Same as 2.1. `start()` detects the orphan and deletes state.json but does NOT attempt any data collection or recovery. The crashed session's data is lost entirely. No `recovery: true` metadata, no partial storage.

---

### 2.3 "Developer runs `flow start` in a monorepo subfolder. Which project gets tracked?"

**Ideal Behavior:** Uses `git rev-parse --show-toplevel` — the monorepo root becomes the project. All work shares one memory space. Acceptable for v1; future `flow start --project billing-service` allows override.

**Actual Behavior: MATCHES.** Verified in code ([session.py:55-66](flow/session.py#L55-L66)). `_detect_project()` calls `git rev-parse --show-toplevel` and uses `Path(path).name` as the project name. No `--project` override flag exists yet, but the v1 behavior matches the ideal.

---

### 2.4 "Developer has concurrent sessions across different projects in different terminals."

**Ideal Behavior:** Each session is independent, keyed by project path. `flow start` in project A doesn't conflict with project B. `flow stop` in A only collects A's data.

**Actual Behavior: GAP.** Verified in code ([session.py:53](flow/session.py#L53)). `STATE_PATH` is a single file: `~/.local/share/flow/state.json`. It's not keyed by project. Starting a session in project B while project A is active will fail with "Session already active for A." Concurrent sessions across projects are impossible.

---

## 3. Retrieval & Briefing

### 3.1 "`flow wake` on a project with 50+ sessions. Which memories surface?"

**Ideal Behavior:** Biased toward recency: last 2-3 sessions' facts always surface, even if older memories are semantically closer. Briefing leads with "where you left off" and includes broader context only if directly relevant. The developer should be working within 60 seconds.

**Actual Behavior: PARTIAL.** Verified in code ([retriever.py:62-68](flow/retriever.py#L62-L68)). `wake()` searches with `limit=5` and the query "what was I working on, what was blocked, what comes next." This relies entirely on mem0's semantic search ranking — there is NO recency bias. mem0 returns by embedding similarity, not by date. The most recent session's facts could be outranked by older, semantically closer memories. No time-based weighting or sorting exists.

---

### 3.2 "Developer hasn't touched a project in 6 months. Is the briefing still useful?"

**Ideal Behavior:** This is Flow's core value prop. The briefing should be *more* detailed for longer absences: (1) what the project does, (2) what was last worked on, (3) key decisions and why, (4) the next step. The synthesis detects the time gap and adjusts: *"It's been about 6 months. Here's where things stand..."*

**Actual Behavior: PARTIAL.** Verified in code ([retriever.py:26-32](flow/retriever.py#L26-L32), [retriever.py:91-110](flow/retriever.py#L91-L110)). The prompt does include `{days_away}` and `_days_since_last_session()` estimates the gap. However, the prompt is static — it doesn't change behavior for 2 days vs 180 days. Same "3-5 sentence briefing" format regardless of gap length. No conditional logic for longer absences (e.g., include more context, broader summary). The LLM *might* adjust tone based on seeing "180 days," but it's not instructed to.

---

### 3.3 "`flow ask 'how did I handle auth?'` — but I handled it differently in 3 projects."

**Ideal Behavior:** Synthesis presents all approaches with project attribution and temporal ordering, then identifies the trajectory: *"In project A you used JWT. In B you went stateless with Redis refresh tokens. In C you delegated to Clerk. Your recent preference leans toward managed auth for side projects."*

**Actual Behavior: MATCHES.** Verified in code ([retriever.py:13-23](flow/retriever.py#L13-L23), [retriever.py:42-60](flow/retriever.py#L42-L60)). `SYNTHESIS_PROMPT` explicitly instructs: "Be specific about which project, when, and what the outcome was. Where their approach evolved across projects, note that evolution explicitly." Results include project name (`agent_id`) and `session_date` in the context. The prompt design matches the ideal behavior.

---

### 3.4 "Can `flow ask` surface patterns the developer hasn't explicitly noticed?"

**Example:** Developer always abandons ORMs after initial adoption across 4 projects.

**Ideal Behavior:** Broad queries like *"what are my recurring patterns?"* should identify cross-project patterns: *"You've adopted and replaced an ORM in 4 projects. Each time you cited query complexity as the reason for switching to raw SQL."* This emergent insight is Flow's highest-value capability.

**Actual Behavior: DEPENDS ON MEM0 + LLM.** The `SYNTHESIS_PROMPT` says "synthesize what the developer actually did and decided across their projects" but doesn't explicitly instruct pattern detection. Whether patterns emerge depends on: (1) mem0 search returning the relevant ORM memories for a broad query like "recurring patterns," and (2) the LLM connecting them. Likely works for direct queries ("how did I handle ORMs?") but unlikely for truly open-ended pattern discovery since mem0 search is query-specific, not exhaustive.

---

### 3.5 "First session on a new project — cold start. What happens?"

**Ideal Behavior:** `flow wake` returns: *"No sessions recorded yet."* But `flow start` still injects context from git log (recent commits) even without mem0 memories. The developer gets *something* on day one.

**Actual Behavior: PARTIAL.** Verified in code. `flow wake` correctly returns "No sessions recorded for {project} yet." ([retriever.py:70-71](flow/retriever.py#L70-L71)). However, `flow start`'s context injection ([context.py:53-55](flow/context.py#L53-L55)) returns empty if `_gather_memories()` finds nothing — it does NOT fall back to git log. The developer gets nothing on day one from `flow start`.

---

## 4. Multi-Tool & Data Ingestion

### 4.1 "Developer uses Cursor and Claude Code in the same session."

**Ideal Behavior:** All parsers run independently, turns merged chronologically. If the same question appears in both tools within 60 seconds (copy-paste), deduplicate. Stored as one unified session.

**Actual Behavior: PARTIAL.** Verified in code ([collector.py:21-35](flow/collector.py#L21-L35)). All parsers run independently, turns are merged and sorted by timestamp (`turns.sort(key=lambda t: t.timestamp)`). Stored as a single session. **Gap:** No duplicate detection. If the developer copy-pastes the same question into Cursor and Claude Code, both will appear in the stored session as separate turns.

---

### 4.2 "6-hour session with 500+ turns. Does `flow stop` choke?"

**Ideal Behavior:** Cap at a configurable maximum (e.g., 10 chunks = 100 turns). Prioritize the most recent turns. Drop older turns with a note: *"Session truncated: stored last 100 of 500 turns."* Complete in <10 seconds for typical sessions.

**Actual Behavior: GAP.** Verified via test. 500 turns produces **50 chunks**, each requiring a separate `memory.add()` call (= 50 LLM extraction calls). No cap on chunk count. No truncation of turn count. No prioritization of recent turns. A 500-turn session would take minutes and cost significantly more than the stated ~$0.001/session.

---

### 4.3 "AI tool is still running and writing logs when `flow stop` is called."

**Ideal Behavior:** Parser handles incomplete JSON lines gracefully (skip unparseable trailing line). For Cursor's SQLite, use WAL-mode-aware reads. A race condition should never crash `flow stop` or corrupt memories.

**Actual Behavior: MOSTLY MATCHES.** Verified in code. Claude Code parser ([claude_code.py:40-41](flow/parsers/claude_code.py#L40-L41)) wraps each line in `try/except json.JSONDecodeError: continue` — incomplete trailing lines are skipped. Codex parser ([codex.py:34-35](flow/parsers/codex.py#L34-L35)) same pattern. Cursor parser ([cursor.py:47](flow/parsers/cursor.py#L47)) opens SQLite in read-only mode (`file:{path}?mode=ro`), which is WAL-safe. All parsers have outer `try/except` guards. Race conditions won't crash `flow stop`.

---

## 5. Context Injection

### 5.1 "Developer has their own CLAUDE.md content. Does Flow overwrite it?"

**Ideal Behavior:** Flow uses `<!-- flow:start -->` / `<!-- flow:end -->` markers. Only content between markers is touched. Developer content outside is never modified. Markers appended to end of file if they don't exist yet.

**Actual Behavior: MATCHES.** Verified in code + test ([context.py:108-131](flow/context.py#L108-L131)). `_write_file()` uses regex to find and replace content between markers only. If no markers exist, the block is appended. Developer content outside markers is preserved across multiple injections. Tested with two sequential injections — works correctly.

---

### 5.2 "Injected context is wrong. Can the developer correct it?"

**Ideal Behavior:** Developer can delete the marker block — next `flow start` regenerates from mem0. For persistent corrections, `flow forget "incorrect fact"` (future) removes it from mem0 directly. Developer must always feel in control.

**Actual Behavior: PARTIAL.** Deleting the marker block works — next `flow start` regenerates it from mem0. **Gap:** No `flow forget` command exists. The developer has no way to delete or correct memories via the CLI. The only option is to manually interact with the mem0 Python API or delete the Qdrant database entirely.

---

## 6. Privacy & Data Control

### 6.1 "Data is local, but API calls send data to OpenAI/Anthropic. What exactly leaves the machine?"

**Ideal Behavior:** Flow is transparent: conversation text (not raw code/diffs) is sent for embedding and extraction. During `flow init`, state this clearly. For privacy-sensitive users, support a fully local mode: local embeddings + local LLM (Ollama) + local Qdrant.

**Actual Behavior: GAP.** Verified in code. `flow init` ([cli.py:181-235](flow/cli.py#L181-L235)) does NOT inform the user about what data is sent to APIs. No privacy notice. Conversation text AND truncated git diffs are sent to the LLM for fact extraction (via mem0). The embedder is hardcoded to OpenAI's `text-embedding-3-small` ([memory.py:51-53](flow/memory.py#L51-L53)) — no local mode option. No Ollama/local LLM support in config.

---

### 6.2 "Secrets accidentally captured in AI conversations — API keys, tokens."

**Ideal Behavior:** Formatter runs a basic secret scanner before passing to mem0. Pattern-match common formats (AWS keys, GitHub tokens, JWTs). Detected secrets redacted as `[REDACTED]` before storage. Defense in depth alongside the extraction prompt's exclusion rules.

**Actual Behavior: GAP.** Verified in code. No secret scanning exists anywhere in the pipeline. `Formatter` ([formatter.py](flow/formatter.py)) does truncation and chunking only — no content inspection. Secrets in AI conversation logs pass through to mem0 unredacted. The extraction prompt says to ignore "tool invocations and raw output," but that's an LLM instruction, not a guarantee.

---

### 6.3 "Can the developer delete specific memories or wipe a project's memory?"

**Ideal Behavior:** `flow forget --project auth-service` deletes all project memories. `flow forget "that Redis experiment"` searches, shows matches, prompts for confirmation. `flow reset` wipes everything with double confirmation. Control is non-negotiable for trust.

**Actual Behavior: GAP.** Verified in code. No `forget`, `reset`, or any memory management commands exist in the CLI ([cli.py](flow/cli.py)). The developer has zero ability to inspect, delete, or modify stored memories through Flow's interface.

---

## 7. Reliability

### 7.1 "OpenAI embedding API is down. What happens to `flow stop`?"

**Ideal Behavior:** Catch the failure, write formatted chunks to a fallback file. Print: *"Embedding service unavailable. Session saved locally — will retry on next `flow stop`."* Next successful stop processes pending failures first. Developer never loses session data to a transient outage.

**Actual Behavior: PARTIAL.** Verified in code ([cli.py:96-117](flow/cli.py#L96-L117), [memory.py:96-136](flow/memory.py#L96-L136)). If `FlowMemory` initialization succeeds but individual chunk adds fail, `add_chunks()` continues processing remaining chunks and writes a combined fallback file if all fail. If `FlowMemory()` constructor itself fails (can't connect to Qdrant), the outer `try/except` in `stop()` catches it and writes a fallback. **Gap:** No retry logic. Failed sessions are written to `~/.local/share/flow/failed/` but are never retried automatically on the next `flow stop`. They sit on disk indefinitely.

---

### 7.2 "Developer rebases or force-pushes between sessions. Does that break anything?"

**Ideal Behavior:** Memories are semantic facts, not commit references. A rebase doesn't invalidate *"was implementing OAuth via Passport.js."* If the base commit no longer exists, `flow stop` falls back to `git log --since=<session_start>`. Already-stored memories are unaffected.

**Actual Behavior: PARTIAL.** Verified in code ([collector.py:52-77](flow/collector.py#L52-L77)). If `git diff <base_commit>` fails (commit no longer exists after rebase), the subprocess returns a non-zero exit code but `_git_diff()` catches it via the broad `except` and returns `""`. `_git_log()` uses `--since=` which doesn't depend on specific commits. Already-stored memories are indeed unaffected (semantic, not commit-bound). **Gap:** The `git diff` failure is silent — Flow doesn't fall back to `git diff HEAD~10` or any alternative. It just returns empty, losing the diff data entirely. The `git log` still works, so the session isn't completely empty.

---

### 7.3 "Two projects have the same directory name but are different repos."

**Ideal Behavior:** Project identity should use git remote URL or absolute path, not just the directory name. Two projects both named "api" in different locations get separate memory spaces.

**Actual Behavior: GAP.** Verified in code ([session.py:65](flow/session.py#L65)). `_detect_project()` uses `Path(path).name` as the project name, which becomes the `agent_id` in mem0. Two repos at `/Users/dev/work/api` and `/Users/dev/personal/api` both get `agent_id="api"` — they share the same memory space. Memories from one will contaminate the other.

---

## 8. Scale & Performance

### 8.1 "What's the latency of `flow wake`?"

**Ideal Behavior:** <3 seconds. mem0 search ~0.5s (local Qdrant + one embedding call), LLM synthesis ~1-2s (Haiku). Cache briefings: if `flow wake` runs twice in 5 minutes without a new session, return cached.

**Actual Behavior: PARTIAL.** The architecture is correct for low latency: one mem0 search + one LLM call ([retriever.py:62-89](flow/retriever.py#L62-L89)). Uses Haiku by default (fast model). **Gap:** No caching. Every `flow wake` call hits the embedding API + LLM regardless of whether anything changed. No latency monitoring or logging.

---

### 8.2 "1,000+ memories in Qdrant. Does search degrade?"

**Ideal Behavior:** No. Qdrant handles millions of vectors efficiently. At 1,000 memories, vector search is <50ms. The bottleneck is the embedding API call, not the store. Year-of-use disk footprint: <100MB.

**Actual Behavior: LIKELY MATCHES.** Qdrant embedded mode is well-tested at this scale. The architecture doesn't introduce any performance bottlenecks beyond what Qdrant provides. No verification at scale yet, but the design is sound.

---

## Summary: Gap Count

| Status | Count | Scenarios |
|--------|-------|-----------|
| **MATCHES** | 4 | 2.3, 3.3, 4.3, 5.1 |
| **PARTIAL** | 8 | 2.1, 3.1, 3.2, 3.5, 4.1, 7.1, 7.2, 8.1 |
| **GAP** | 8 | 1.1, 1.2, 2.2, 2.4, 4.2, 6.1, 6.2, 6.3, 7.3 |
| **UNCERTAIN** | 2 | 1.3, 3.4, 8.2 |

### Critical Gaps (would be asked about in a CTO review):
1. **1.1 — mem0 reconciliation doesn't actually reconcile contradictions** (runtime-verified)
2. **2.4 — No concurrent sessions** (single state.json)
3. **4.2 — No chunk cap** (500 turns = 50 LLM calls)
4. **6.3 — No memory deletion commands** (developer has zero control)
5. **7.3 — Project name collision** (directory name, not full path)
