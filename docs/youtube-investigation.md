# YouTube Transcript Investigation

This document records every approach we investigated for fetching YouTube video transcripts programmatically, and why each was rejected. It exists so future contributors understand why we landed on NotebookLM and do not repeat the same investigation.

## Test video

`https://youtu.be/l8pQeVVaqpY` — used throughout. Public video with auto-generated captions.

## Approaches tried

### 1. `youtube-transcript-api` (Python library)

**Result: Rejected.**

The library fetches captions directly from YouTube's servers. When run from a datacenter IP (GitHub Actions runner, any VPS), YouTube returns HTTP 429 or a bot-detection block. Works fine on a home IP. This is a [well-known issue](https://github.com/jdepoix/youtube-transcript-api/issues) documented extensively in the library's GitHub issues.

### 2. Invidious public instances (caption proxy)

**Result: Rejected.**

Invidious exposes `/api/v1/captions/{video_id}` which returns a list of available caption tracks. We tested instances from the official list at `https://api.invidious.io/instances.json`.

Failures observed:
- Most instances: connection timeout, 502 Bad Gateway, or DNS failure
- `inv.nadeko.net`: returned the captions list JSON successfully, but the VTT content endpoint returned 200 with `content-length: 0` (empty body)

The public instance ecosystem is too unreliable for production use. Self-hosting Invidious would require significant infrastructure and maintenance.

### 3. Piped instances (caption proxy)

**Result: Rejected.**

Piped exposes `/streams/{video_id}` which includes a `subtitles` array. All instances tested from the public list returned 502, 503, or DNS failures. The Piped project is less actively maintained than Invidious.

### 4. `yt-dlp` with `--write-auto-subs`

**Result: Rejected for production use.**

`yt-dlp` works on a residential IP and local development machines. However, it hits the same YouTube bot-detection as `youtube-transcript-api` on datacenter IPs (GitHub Actions runners, VPS). This is explicitly documented in yt-dlp's GitHub issues as a known limitation for non-residential IPs.

### 5. YouTube `timedtext` API (undocumented)

**Result: Rejected.**

`https://www.youtube.com/api/timedtext?...` returns empty content for auto-generated captions in our tests. Only works reliably for manually uploaded SRT files, which are rare.

### 6. Gemini with YouTube URL

**Result: Rejected.**

Pasting a YouTube URL into Gemini (tested via the web UI) resulted in the model hallucinating content not present in the video. The model was not actually processing the video; it appeared to be generating from the title or other metadata only.

---

## Chosen approach: `notebooklm-py`

`notebooklm-py` is an unofficial Python client for [Google NotebookLM](https://notebooklm.google.com/). It automates the browser session using saved auth cookies.

**Why it works:** NotebookLM is a Google product. When it processes a YouTube URL, it uses Google's internal infrastructure to fetch and transcribe the video — the same infrastructure that powers YouTube's own auto-captions. No IP blocking applies because the request never leaves Google's network.

**Validated end-to-end:** We tested `https://youtu.be/l8pQeVVaqpY` via the `notebooklm` CLI:

```bash
uv run notebooklm create "test-yt"
# → Created notebook: ad16e0d3-6686-49ce-abc5-37ca8051809c
uv run notebooklm source add "https://youtu.be/l8pQeVVaqpY"
uv run notebooklm ask "Summarize this video in key points"
```

The summary was accurate and specific, confirming that NotebookLM correctly accessed and understood the video content.

**Trade-offs:**
- Requires a Google account and a saved auth session (`storage_state.json`)
- Auth sessions expire periodically — renewal is manual (`uv run notebooklm login`)
- Uses undocumented Google APIs that may change without notice
- Each video summarization creates and deletes a temporary notebook (overhead: a few extra API calls)
- Not suitable if the Google account is rate-limited or suspended

**Session management in CI:** The `storage_state.json` content is stored as a GitHub Actions secret (`NOTEBOOKLM_STORAGE_STATE`) and written to a temp file at runtime.
