Title: Anthropic's Internal Claude Code Skills

TL;DR: The developers of Claude Code rely on specialized AI skills to automate complex engineering tasks like parallel repository refactoring, code verification, and workflow generation.

Key points:
- The Batch skill parallelizes tasks by assigning agents to isolated work trees, ensuring concurrent changes do not interfere before merging back to the main branch.
- The Simplify skill deploys multiple agents to evaluate code against various metrics, removing duplicates and refining clarity.
- Internal tools like the Verify and Tech Debt skills run automated tests, detect redundant code, and refactor isolated components into shared libraries.
- The Skillify command analyzes an active user session to automatically extract, document, and generate reusable workflow skills.
- The DDUP skill parses repository inputs using the GitHub CLI to search for and flag duplicate issue tickets.

Why it matters:
- Integrating specialized AI agents directly into the CLI to manage isolated work trees, issue tracking, and repetitive refactoring provides a practical blueprint for highly autonomous software engineering environments.

Evidence:
- The Simplify skill specifically spawns three separate agents to rigorously evaluate codebase changes.
- The DDUP skill comments on potential duplicate GitHub issues only when it reaches a set 70% certainty threshold.

Caveat:
- Many of the most impactful tools highlighted, including Verify, Skillify, DDUP, and Tech Debt, are internal Anthropic utilities hidden behind CLI flags and are not available out-of-the-box for public users.
