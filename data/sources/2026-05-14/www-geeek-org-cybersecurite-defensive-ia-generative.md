Title: Generative AI Agents for Defensive Cybersecurity: Claude Code and GitHub Copilot CLI in Practice

TL;DR: The article outlines how coding agents like Claude Code and GitHub Copilot CLI can be applied across six defensive cybersecurity pillars—code audit, DevSecOps, detection, forensics, threat intelligence, and hardening—to integrate continuous security checks into the development lifecycle.

Key points:
- Generative AI is lowering the barrier for attackers (e.g., recent breaches by teenagers), making defensive AI adoption urgent.
- Six defensive pillars are covered with concrete prompts: SAST/code audit, DevSecOps/CI/CD, SIEM/detection, incident response/forensics, threat intelligence, and infrastructure hardening/compliance.
- Claude Code excels at multi-file context analysis, reverse engineering obfuscated code, and generating structured CTI reports with MITRE ATT&CK mapping.
- GitHub Copilot CLI shines via native GitHub integration (issues, PRs, Dependabot, CodeQL) and sandboxed shell execution for DFIR tools like volatility3.
- Both tools must be used with governance: never blindly trust generated code, always pair with human review, and combine with established scanners (Semgrep, Trivy, etc.).

Why it matters:
- Shifts security from a final validation gate to a continuous, AI-assisted companion embedded in the developer workflow, addressing the speed gap between agile development and security controls.

Evidence:
- 68% of breaches involve a human factor; 194 days average detection time; $4.4M average cost per incident (Verizon DBIR 2024, IBM 2024/2025).
- +180% year-over-year increase in vulnerability exploitation as initial attack vector.
- Two French cases: a 17-year-old exfiltrated 19.2M Free subscriber records (Oct 2024); a 15-year-old exploited an IDOR flaw in ANTS, exposing 12–19M citizen profiles (Apr 2026).

Caveat:
- AI can produce false positives, miss context-specific vulnerabilities, and should not replace expert audits or pentests; sensitive data must be anonymized before sending to agents, and all critical fixes require human review.
