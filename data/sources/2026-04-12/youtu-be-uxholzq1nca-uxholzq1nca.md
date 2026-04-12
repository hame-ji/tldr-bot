Title: Anthropic's Managed Agents Architecture and Implementation

TL;DR: Anthropic's new Claude Managed Agents allow developers to build, host, and orchestrate secure AI agents directly on Anthropic's infrastructure without managing servers.

Key points:
- Managed Agents abstract away infrastructure and security management, offering a low-code alternative to self-hosting with the standard Claude SDK.
- The underlying architecture decouples the system into an orchestrator, append-only session logs for memory, and a stateless harness that routes tool calls.
- API keys and credentials are kept secure in a vault and injected only at runtime, ensuring the model never directly accesses the raw keys.
- Agents can be generated and configured either through natural language in the Claude console or programmatically via the TypeScript SDK.

Why it matters:
- By handling state recovery and secure runtime tool execution internally, this architecture removes the heavy engineering burden of building reliable, fault-tolerant agentic systems from scratch.

Evidence:
- The service charges $0.08 per session hour while active, in addition to standard API token usage rates.
- In a practical test, a Managed Agent successfully used the Sonnet model to securely read markdown files from a private GitHub repository and answer user queries via a customized Slack bot integration.

Caveat:
- Usage is billed entirely through the API and is not covered by Claude Pro or Team subscriptions, and integrating with unlisted channels outside of the curated defaults requires writing custom code.
