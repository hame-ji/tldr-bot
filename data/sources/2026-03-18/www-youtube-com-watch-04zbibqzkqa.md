**Core Thesis**
* Claude Code includes a built-in, highly underrated "Claude Code Guide" sub-agent that acts as an expert on the software itself [1]. 
* By tagging this sub-agent, users can bypass external tutorials and have the AI directly answer questions, diagnose local file issues, and write fixes for their configurations [1, 2].

**Key Supporting Points and Evidence**
* **Operates independently:** The sub-agent fetches information from Claude Code guides in the background without eating into your main context window tokens [3].
* **Context-aware diagnostics:** You can tag the guide alongside your actual local project files (like configuration files or markdown documents) so it can read them and identify what is missing or broken [2, 4].
* **Scalable utility:** The feature can be used across five "levels" of complexity, starting from answering basic conceptual questions to acting as a "medic" that autonomously rewrites broken code settings [5-7].

**Notable Examples, Numbers, and Concrete Details**
* **Token usage:** In one query, the sub-agent processed 28,000 tokens of documentation in the background to deliver an accurate response [3].
* **Auditing `Claude.md`:** When asked why Claude wasn't following formatting preferences, the guide read a user's `Claude.md` file and accurately diagnosed that it lacked core instructions for file organization, code formatting, and positive/negative prompting [4, 8].
* **Explaining Hooks:** The guide successfully outlined 17 different types of available "hook" events (e.g., pre-tool use, post-tool use, session start) and explained how to write the necessary JSON to trigger them [8, 9].
* **Live troubleshooting:** In a "Level 5" demonstration, the guide fixed a broken archive hook that was saving files with random animal names (like "dizzy purple flamingo"). It read the documentation, fixed the user's `settings.json` file, and automatically renamed the files to include proper descriptions and dates [6, 7, 10].

**Actionable Takeaways**
* **Stop Googling for syntax:** Instead of searching online for how to use Claude Code, tag the built-in guide to explain concepts directly from the source material [1, 5].
* **Audit your custom instructions:** Tag the guide and your local `Claude.md` file simultaneously, and ask the agent what is missing or how to improve your formatting rules [4].
* **Automate your workflow:** Ask the guide to teach you how to set up "hooks" so you can trigger specific actions (like archiving plans or organizing files) automatically during your sessions [8, 9].
* **Switch models easily:** Use the `/model` command to easily switch between models (e.g., from Sonnet to Opus) mid-conversation [3, 5].
