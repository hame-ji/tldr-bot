Title: Claude Code's Unannounced "Auto Dream" Memory Consolidation

TL;DR: Anthropic has quietly introduced an asynchronous background process to Claude Code that automatically reviews, cleans, and organizes local session memories to prevent context bloat.

Key points:
- The Auto Dream feature operates in the background to consolidate memories without interrupting ongoing Claude Code usage.
- It scans local JSONL session transcripts to extract user feedback, important decisions, and recurring themes while identifying stale data.
- The process converts relative temporal references like "yesterday" into exact dates and resolves contradictory entries.
- A four-phase workflow (Orientation, Gathering Signal, Consolidation, and Pruning/Indexing) restructures the primary MEMORY.md file into a clean index referencing specific memories.

Why it matters:
- It directly addresses agent performance degradation caused by the accumulation of noisy, contradictory auto-memory data over prolonged use.

Evidence:
- The existence of the four internal phases was verified by using a proxy to extract the specific system prompts dictating the process.
- During a demonstrated execution, the tool successfully initiated a background memory consolidation across 913 previous sessions.

Caveat:
- Because the feature is currently unannounced by Anthropic, its functionality and implementation details may change.
