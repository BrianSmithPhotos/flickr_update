# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A rate-limited Flickr upload tool: it scans a directory of images and uploads them to Flickr at a controlled pace (2 per hour), rather than all at once.

Brian has a **Flickr Pro account**, so bandwidth/storage limits are not a constraint. The reason for pacing is **visibility, not quota**: when a batch of images is uploaded at once, only the last few get views, because Flickr's contacts/recent-activity feeds surface only the most recent uploads. Spacing uploads out gives each photo its own moment in front of viewers. Flickr does not enforce this pacing — its API limit is 3,600 queries/hour, far looser than any sane upload schedule. The throttling exists purely for visibility.

## Commands

```bash
uv run python main.py "$PHOTOS_DIR" --limit 2   # one paced batch
uv run python auth.py                           # one-time OAuth setup (see README)
uv run python baseline.py "$DIR" --under SUB --dry-run  # exclude files from upload
./run_upload.sh                                 # what launchd invokes
```

There are no tests or lint config. `baseline.py` verifies with `--dry-run` against a scratch copy of the manifest (`--manifest /tmp/.../m.json`), never the real one. `main.py` has no dry-run or `--manifest` flag; check its queue read-only by importing `scan`/`state` and comparing, without uploading.

The schedule is a launchd agent (`photos.briansmith.flickrupload.plist`), hourly at :17. Install/pause instructions are in README.md.

## Architecture

- `run_upload.sh` — launchd entry point. `cd`s to the repo, sources `.env`, validates `PHOTOS_DIR`, appends output to `cron.log`, and fires a desktop notification on any non-zero exit. The `cd` matters: `state.MANIFEST_PATH` is a **relative** path, so running `main.py` from elsewhere silently uses a different manifest.
- `main.py` — orchestration: scan, filter, dedupe, upload up to `--limit`, save after each photo.
- `scan.py` — finds candidate images.
- `state.py` — JSON manifest (`upload_state.json`, gitignored), keyed by filename.
- `upload.py` — Flickr client + single-photo upload, plus the dataless-file guard.
- `baseline.py` — one-off pass to mark existing files as already handled.

## How photos are selected

Subtle and easy to break — the pipeline in `main.py:run`:

1. `scan.find_images` recursively globs for `.jpg`/`.jpeg`/`.png`, **excluding files directly in the tree root** (`scan.py:12`) — a photo must be in a subfolder or it is silently ignored.
2. Results sort **alphabetically by filename**, not by date. New files with early-sorting names jump the queue.
3. Candidates are filenames absent from the manifest.
4. Each candidate is SHA-256'd; a digest already in the manifest means the file is a rename of a known photo, so it's marked `baseline` and skipped. Skips do **not** count against `--limit`.
5. The first `--limit` survivors upload.

## Invariants

- **The manifest is the only memory. The tool never asks Flickr what's already there.** Any photo it hasn't recorded is uploaded, even if an identical one is already on Flickr. This is why `baseline.py` must run before an existing archive is copied into the watched tree.
- **Never read a file without checking `upload.is_dataless` first.** Opening an online-only placeholder blocks on hydration and has hung for hours. `stat()` is safe; `open()` is not. The current source (Google Drive, `~/Library/CloudStorage/...`) is marked available offline and its files stat cleanly as materialized (`st_flags=0x40`, `UF_TRACKED`, not `UF_DATALESS`), so the guard behaves correctly there. Google Drive uses the same macOS File Provider mechanism as iCloud, so `UF_DATALESS` is expected to apply to streaming-only files — but that path is untested and should not arise while the folder stays offline-available. If the folder is ever switched back to streaming, re-verify before trusting the guard.
- **A run is watchdogged at 300s** (`main.py:21`). Without it, one hung read wedges the process and launchd's no-overlap rule silently suppresses every later run.
- **Error 6 (bandwidth) and 98 (bad token) are stop conditions**, not retries; everything else is transient and skipped for the run. Network timeouts and dropped connections are also skipped: every HTTP request is capped at 60s (`upload.REQUEST_TIMEOUT`), because flickrapi otherwise waits forever. Sync anomalies exit with code 2 so `run_upload.sh` can alert.
- **Credentials and local paths are never committed** — API key/secret and `PHOTOS_DIR` in `.env`, OAuth token in `~/.flickr/oauth-tokens.sqlite`, all outside version control. This repo is **public on GitHub**, and the photo path embeds both the local username and the Google account name, so it must not be hardcoded in a tracked file.
- **Baselining is irreversible in effect**: a baselined photo never uploads. Confirm the queue state before running `baseline.py`, scope it with `--under`, and keep the automatic manifest backup.

## Working agreements

- **Never manually drain a backlog of missed uploads.** If a schedule gap leaves photos unsent, ask Brian rather than running catch-up batches — the whole point is the pacing, and a burst defeats it. Let the hourly schedule absorb it.
