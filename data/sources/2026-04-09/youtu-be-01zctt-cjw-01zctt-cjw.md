Title: Google's Gemma 4 and Turbo Quant Quantization

TL;DR: Google released Gemma 4, a highly efficient open-weight model, along with a novel quantization method called Turbo Quant that drastically reduces AI memory bandwidth bottlenecks.

Key points:
- Gemma 4 is an Apache 2.0 licensed model designed to run efficiently on local machines by minimizing VRAM read expenses.
- The core bottleneck for local AI is memory bandwidth, not CPU power, which Google addresses by reducing the amount of data required to generate tokens.
- Google's new Turbo Quant technique improves model compression by converting Cartesian coordinates into polar coordinates to skip typical normalization steps.
- Turbo Quant further compresses high-dimensional data into single sign bits using the Johnson-Lindenstrauss transform while preserving relative data point distances.

Why it matters:
- It allows developers to run competitive, high-parameter AI models entirely locally on standard consumer GPUs instead of relying on massive, expensive enterprise hardware arrays.

Evidence:
- The 31 billion parameter version of Gemma 4 requires only a 20 GB download and achieves roughly 10 tokens per second on a single RTX 4090 GPU.
- Comparable models require a 600+ GB download, at least 256 GB of RAM, and multiple enterprise-grade H100 GPUs to achieve similar performance.

Caveat:
- The source notes that despite being released simultaneously, the Turbo Quant technique is actually not the direct mechanism responsible for the small size of the Gemma 4 models.
