Title: Sapling SCM: A Scalable, Git-Compatible Source Control System

TL;DR: Sapling is an open-source, Git-compatible version control system designed for extreme scalability in massive repositories by scaling operations to active files rather than total repository size.

Key points:
- The `sl` CLI and Interactive Smartlog (ISL) UI provide a Git-compatible, Mercurial-inspired interface for managing repositories.
- Operations scale based on the number of files a developer actively uses, not the total repository size, enabling fast performance in repos with millions of files and commits.
- The architecture includes three components: the client CLI/UI, the Mononoke server, and the EdenFS virtual filesystem.
- EdenFS accelerates large checkouts by lazily populating files on demand, trading a minor initial access delay for significantly faster overall checkout times.

Why it matters:
- It provides a production-tested, high-performance alternative to Git for engineering teams managing monorepos or massive codebases where traditional VCS performance degrades.

Evidence:
- Designed to handle repositories containing millions of files and millions of commits while maintaining fast developer experiences.
- The CLI builds and runs natively on Linux, macOS, and Windows, requiring Python 3.8, Rust, CMake, and OpenSSL.

Caveat:
- The server-side Mononoke and EdenFS components are not yet officially supported for external production use, despite being available as open-source builds for experimentation.
