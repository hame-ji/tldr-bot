Title: Mitigating LLM Hallucinations in Engineering

TL;DR: Large Language Models frequently hallucinate because they are optimized to guess rather than admit uncertainty, but engineers can reduce these errors by forcing models to rely on explicitly provided data.

Key points:
- LLMs suffer from multiple types of hallucinations, including factual errors, fabricated entities like non-existent code packages, and contextual inconsistency where they ignore provided prompts.
- Models hallucinate primarily because they rely on highly compressed training data and their evaluation benchmarks reward confident guessing over admitting a lack of knowledge.
- Errors based on extrinsic (training) data are highly common, whereas grounding the model with intrinsic (user-provided) data significantly improves accuracy.
- Appending the phrase "Use your search tool" to queries forces the LLM to fetch and rely on external documents rather than guessing from its internal weights.

Why it matters:
- Unverified trust in LLM outputs exposes software developers to significant security risks, including integrating malicious code via supply chain attacks disguised as fabricated packages.

Evidence:
- Google's Bard launch advert featured a factual hallucination about the James Webb Space Telescope, causing Alphabet's stock to drop by 8%.
- Air Canada was found legally liable in 2024 after its chatbot suffered contextual inconsistency and gave bad advice regarding an explicitly provided bereavement policy.

Caveat:
- Even when explicitly provided with intrinsic data or search tools, LLMs can still suffer from contextual inconsistency and misinterpret data, requiring manual verification for critical or high-stakes tasks.
