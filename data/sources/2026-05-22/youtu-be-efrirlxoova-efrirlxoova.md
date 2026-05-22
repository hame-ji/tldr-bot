Title: Context Scoping for Coding Agents in Large Codebases

TL;DR: Anthropic recommends scoping coding agents to specific subdirectories and using progressive disclosure for skills to efficiently manage context in large codebases.

Key points:
- Initialize coding agents within the specific subdirectory of a given task to restrict their working directory and context limits.
- Store localized coding conventions in directory-specific configuration files rather than loading all global rules into the agent's context at once.
- Utilize "progressive disclosure" to offload specialized workflows and domain knowledge, loading them only when the current task necessitates it.
- Define agent skills with a brief description that the agent evaluates first before deciding to load the complete skill instructions.

Why it matters:
- Dynamically loading expertise and limiting working directories prevents context bloat, helping coding agents maintain focus and accuracy when executing tasks in complex repositories.

Evidence:
- The workflow utilizes directory-level `claude.md` files for local conventions and standalone `skill.md` files that agents selectively load based on their initial descriptions.
