Title: Archestra Blocks AI Slop by Gating Contributions via Onboarding

TL;DR: The Archestra team describes how AI bots flooded their open source repo with useless comments and PRs, leading them to build a custom onboard-and-whitelist system that uses a GitHub prior-contributor hack to restore quality.

Key points:
- A $900 bounty issue exploded to 253 comments as AI bots posted pointless "implementation plans" and aggression, burying real contributors like @ethanwater and @developerfred.
- One maintainer spent half a day each week removing untested PRs and hallucinated issues; the repo became unfriendly to legitimate contributors.
- Initial countermeasures (a reputation bot "London-Cat" and an "AI sheriff" that closed a few real PRs) failed to stop the spam.
- The team eventually implemented a "nuclear option": only users who complete a CAPTCHA and agree to ethical AI rules on their website get whitelisted as prior contributors via an automated commit to `main`.
- The workaround exploits GitHub's "Limit to prior contributors" setting: a GitHub Action commits to `main` with the user as the author, granting them comment/PR access without real prior commits.

Why it matters:
- As AI-generated noise degrades open source repositories and even enables security attacks (as in the LiteLLM repo), this case demonstrates a pragmatic, if hacky, method for maintainers to preserve contributor trust and repo quality.

Evidence:
- One issue (MCP Apps support) received 253 comments, mostly from AI bots.
- For the x.ai provider support issue, 27 PRs were submitted, most untested.
- The LiteLLM repo experienced a security attack where attackers used AI bots to steer conversations.
- The team built two earlier bots: a reputation calculator (London-Cat) and an AI sheriff (which falsely closed some legitimate PRs).

Caveat:
- The solution is a manual, esoteric workaround that depends on GitHub's commit-author mechanics and may not scale; the team acknowledges it is a "nuclear option" that could affect GitHub activity metrics for the VC-backed startup.
