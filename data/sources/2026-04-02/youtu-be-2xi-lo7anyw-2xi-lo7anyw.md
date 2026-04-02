Title: Spec-Driven Development for AI Coding Agents

TL;DR: Aligning AI coding agents requires replacing traditional product requirements documents with concise, continuously updated specifications that define exact scope, non-goals, and verification criteria.

Key points:
- Vague prompts cause eager AI agents to make incorrect assumptions and head down the wrong path, creating a heavy downstream review burden for developers.
- Complex projects should be broken into smaller tasks guided by individual specs, enabling parallel agent execution and adversarial verification.
- AI specs must be treated as living contracts that are actively reviewed before acceptance and continuously updated during generation, rather than just over-specifying implementation details upfront.
- Detailed specs are unnecessary for quick, exploratory, or experimental tasks where a single prompt to a single agent allows for faster iteration.
- Extensive spec frameworks often generate unmanageable amounts of documentation and create unnecessary paperwork.

Why it matters:
- Making engineering intent explicit before generation prevents cheap AI output from turning ambiguity into expensive, difficult-to-review mistakes.

Evidence:
- The video demonstrates a workflow in a tool called "intent" where an agent clarifies a vague prompt about adding authentication by generating a spec complete with non-goals, acceptance criteria, verification steps, and a rollback plan.
- OpenSpec and Spec Kit are specifically named as examples of spec frameworks that tend to be overkill for these workflows.

Caveat:
- The video is produced by a coding assistant company (Augment Code) demonstrating specific tooling, which likely influences the recommended workflows and the dismissive stance on third-party spec frameworks.
