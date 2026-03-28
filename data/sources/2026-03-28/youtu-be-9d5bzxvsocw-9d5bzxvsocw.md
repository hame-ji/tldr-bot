Title: Anthropic's Harness Design for Long-Running AI Agents

TL;DR: Anthropic released a guide on building orchestration harnesses for long-running AI agents, detailing structural solutions for failure modes like context anxiety and poor self-evaluation.

Key points:
- An agent harness acts as an orchestration layer that wraps an AI model with prompts, tools, constraints, and feedback loops to ensure reliable task execution.
- Models often exhibit "context anxiety" by prematurely rushing to finish tasks as their context window fills, a problem mitigated by context compaction or complete context resets.
- Agents naturally struggle to evaluate their own work critically, requiring an adversarial setup with separate generator and evaluator agents to enforce objective quality standards.
- Implementing a planner agent prevents underscoping by expanding simple prompts into comprehensive, structured specifications before the code generation phase begins.

Why it matters:
- Proper harness architecture enables AI to reliably execute complex, multi-hour engineering tasks by breaking down work, verifying outputs against hard constraints, and cleanly handing off context.

Evidence:
- Anthropic successfully used these harness principles to build a 2D retro game engine in a 6-hour autonomous coding session and a browser-based digital audio workstation in 4 hours for approximately $125.
- By utilizing Opus 4.6 with a 1 million token context window, Anthropic was able to simplify their architecture and remove sprint-based context resets in favor of continuous context compaction.

Caveat:
- The speaker expresses skepticism regarding Anthropic's claim that Opus 4.6 eliminates the need for context resets, noting that it is financially beneficial for the company when users send massive, 1 million token requests.
