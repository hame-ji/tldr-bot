Title: Scaling AI Agent Workflows with Parallel Tooling and Custom Skills

TL;DR: An Adobe principal engineer shares practical strategies for managing parallel AI coding agents, building custom skills, and mitigating the technical debt caused by agent-generated code.

Key points:
- Transitioning from terminal-based CLI agents to unified orchestration tools allows developers to manage multiple agent tasks asynchronously without losing track of background processes.
- Custom wrapper scripts, such as an AI-specific Git executable, can prevent models from making undesirable commits like accidentally pushing markdown scratchpads.
- Complex coding tasks must be broken down into smaller chunks to avoid context compaction loops that degrade an agent's reasoning abilities over long sessions.
- Because models start every session without historical project context, strict codebase legibility and concise documentation are critical to preventing rapid technical debt accumulation.
- Providing explicit instructions like "never ask for approvals" forces agents to attempt solutions autonomously rather than pausing workflows for trivial permissions.

Why it matters:
- As AI agents become integrated into daily development, engineering efficiency relies heavily on building customized infrastructure to supervise, constrain, and coordinate multiple models effectively.

Evidence:
- A massive 153-file pull request was successfully completed by delegating tasks across 60 parallel agents.
- A continuous integration rule was implemented to automatically fail builds if the project's agent instruction file exceeded 30,000 characters.

Caveat:
- The workflow heavily relies on specific, sometimes experimental third-party tools and models, which may not be universally available or approved in all corporate environments.
