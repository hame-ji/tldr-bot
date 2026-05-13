Title: Background GUI Automation in Codex

TL;DR: Codex now performs background GUI automation on macOS by utilizing OS-level accessibility frameworks, enabling it to operate multiple local applications simultaneously without interrupting the user.

Key points:
- The agent uses an independent graphical cursor, allowing users to continue their standard workflows while it completes tasks in the background.
- Instead of relying exclusively on screenshot-based multimodal vision models, the system leverages native accessibility frameworks to extract textual interface data, including off-screen elements.
- Bypassing heavy vision requirements enables the use of faster, non-multimodal models like Codex Spark to execute UI actions more rapidly than manual human input.
- Security is isolated through an app-by-app permission model, preventing the tool from viewing or accessing unauthorized software or streaming the broader desktop.

Why it matters:
- Engineers can offload tedious GUI-based tasks across diverse local applications to a concurrent agent, directly integrating native or non-API software into automated workflows without losing focus on their active screens.

Evidence:
- Real-world demonstrations included provisioning a macOS virtual machine using the UTM app, dispatching messages, and updating Apple Numbers spreadsheets.
- The feature is currently live for macOS, with the engineering goal of eventually performing computing tasks 2 to 10 times faster than a human.

Caveat:
- All capability claims and successful demonstrations originate directly from the product's developers at OpenAI, lacking independent verification or discussion of failure rates and application incompatibilities.
