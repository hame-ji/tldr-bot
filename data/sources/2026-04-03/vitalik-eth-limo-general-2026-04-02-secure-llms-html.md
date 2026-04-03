Title: Privacy-First Local LLM Agent Architecture

TL;DR: A practical blueprint for running local-first AI agents with strict sandboxing, human-in-the-loop confirmations, and privacy-preserving remote fallbacks to mitigate data exfiltration and prompt injection risks.

Key points:
- Use declarative OS configurations (NixOS) and `llama-server` for reproducible, high-performance local inference on consumer GPUs.
- Enforce strict isolation via `bubblewrap` sandboxes and a mandatory human confirmation firewall for messaging and wallet interactions.
- Replace cloud search with local knowledge dumps and anonymized search wrappers to minimize telemetry leakage.
- Implement multi-layer privacy for remote model fallbacks using ZK-APIs, mixnets, TEEs, and local input sanitization.

Why it matters:
- Shifts AI agent development from default cloud dependency to user-controlled infrastructure, directly addressing prompt injection, silent data exfiltration, and ecosystem-wide security negligence.

Evidence:
- Consumer GPUs (RTX 5090/4090) achieve ~90 tokens/sec on Qwen3.5:35B, while security audits found ~15% of OpenClaw skills contained malicious instructions.
- Side-by-side testing showed a custom `pi` agent with SearXNG outperformed packaged "Local Deep Research" tools.

Caveat:
- The author explicitly notes this is an experimental starting point rather than a hardened production system, and acknowledges current local hardware cannot reliably handle complex or novel programming tasks.
