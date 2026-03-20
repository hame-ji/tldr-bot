**Core Thesis**
*   Coding agents have advanced to the point where they can write the vast majority of software, fundamentally shifting the developer's role from writing code to directing agents, defining tests, and orchestrating architecture. [1, 2] 
*   This shift enables massive productivity gains but requires developers to manage code quality actively and adopt strict test-driven workflows to keep AI models on track. [3, 4]

**Key Supporting Points and Evidence**
*   **TDD is essential, not optional:** Test-Driven Development (TDD) prevents agents from endlessly spinning or writing bloated code by defining exact stopping points. [3] 
*   **Poor AI code is a choice:** If an agent outputs 2,000 lines of spaghetti code, developers can and should prompt the agent to refactor it using specific design patterns rather than just accepting it. [4, 5]
*   **Agents mimic existing environments:** AI models are highly consistent and will copy the patterns and style of the codebase they are working in, making well-structured templates critical. [6, 7]
*   **Security risks remain high:** Language models are incredibly gullible, making them vulnerable to "prompt injection" (or the "lethal trifecta") where malicious instructions hidden in ingested data can trick the agent into executing harmful commands. [8-10]

**Notable Examples, Numbers, and Concrete Details**
*   Using Claude Opus 4.6 on his phone, Simon achieved a **45-49% performance speedup** on a Python WebAssembly Fibonacci benchmark in just 30 minutes. [1, 11]
*   He built a multi-part file upload feature by first asking Claude to reverse-engineer a test suite that passes across **six different web frameworks** (including Go, Node.js, and Django), and then had the agent build a new implementation to pass those tests. [12]
*   He created a tool called "Showboat" in 48 hours, which instructs agents to test APIs manually using `curl` commands and outputs a Markdown document of the results. [13]
*   He successfully "vibe coded" a custom Christmas dinner timer that synced the steps for two distinct recipes simultaneously, just by uploading photos of the recipes. [14]

**Actionable Takeaways and Decisions to Make**
*   **Command "Red-Green TDD":** Start every coding agent session by providing the test framework command (e.g., `uv run pytest`) and instructing the agent to use "red-green TDD" so it writes the test first. [3]
*   **Force manual testing:** Don't rely solely on automated tests; explicitly tell your agents to start the server in the background and use `curl` to exercise the API they just created to catch runtime bugs. [13, 15]
*   **Use rigid project templates:** Rely on templating tools like cookiecutter to set up boilerplate, continuous integration, and baseline tests before letting an agent loose, ensuring the AI adopts your preferred coding style. [6, 7]
*   **Sandbox your agents:** Run your agents inside Docker or Apple containers to prevent malicious code from destroying your local machine via prompt injection attacks. [16]
*   **Generate mock data:** Never pass real production user data to agents; instead, instruct the AI to build simulated users and specific edge cases for testing purposes. [17]
