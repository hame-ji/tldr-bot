Title: Using Claude Code's Autonomous /goal Command

TL;DR: Anthropic's new `/goal` command allows Claude Code to autonomously execute and independently verify coding tasks to prevent incomplete work and hallucinations.

Key points:
- The command utilizes a secondary, independent Claude session to perform adversarial code review and verify if task criteria have been met before marking it complete.
- Proper execution requires updating the CLI, enabling terminal auto-mode or bypassing permissions, and providing clear task descriptions with explicit verification criteria.
- Users should establish a detailed project plan in a long-term memory system and have Claude generate the exact task inputs and verification steps from this plan.
- Tasks should be assigned in small batches of two or three to allow Claude to logically adjust the overall project plan when encountering unexpected bugs or blockers.
- Frequent reviews of the project plan against high-level goals and session logs are necessary to prevent project drift as the code develops.

Why it matters:
- The addition of an independent verification loop solves a major issue where AI coding agents hallucinate task completion or fail to fully finish the assigned work.

Evidence:
- The `/goal` command has a strict input limit of 4,000 characters.

Caveat:
- Claude often miscounts characters, requiring users to enforce a 3,500-character limit prompt to ensure inputs do not fail, and the source has a promotional bias regarding the author's personal Obsidian memory system.
