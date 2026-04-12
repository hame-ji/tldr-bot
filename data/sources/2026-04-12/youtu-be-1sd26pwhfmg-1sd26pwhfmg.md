Title: LLMs Autonomously Exploiting Zero-Day Vulnerabilities

TL;DR: Recent language models can now autonomously discover and exploit complex zero-day vulnerabilities in critical software, significantly accelerating the cybersecurity threat landscape.

Key points:
- Language models released within the last few months can find and exploit bugs using basic scaffolding, a capability absent in models from just a year ago.
- The proficiency of these models in vulnerability research is growing exponentially, enabling them to comprehend and exploit intricate multi-agent systems.
- The sheer volume of AI-discovered bugs creates a massive backlog for defenders who must manually validate and patch them.
- Standard AI safety guardrails struggle to balance dual-use security tools, as strict blocks hinder defenders while attackers simply bypass them with jailbreaks.

Why it matters:
- Software engineering and security teams face an immediate transition period where malicious actors could use accessible AI tools to discover and exploit unpatched vulnerabilities at an unprecedented scale.

Evidence:
- An LLM discovered the first critical blind SQL injection in the popular Ghost CMS and autonomously wrote a script to extract admin API keys and password hashes.
- An LLM identified a remotely exploitable heap buffer overflow in the Linux kernel's NFS V4 daemon that had existed undiscovered since 2003.

Caveat:
- It remains uncertain how long the exponential improvement in LLM vulnerability research capabilities will continue before hitting a performance plateau.
