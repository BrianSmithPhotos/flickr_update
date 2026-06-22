# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository currently contains only research (`research/RESEARCH.md`) — no source code, build tooling, dependencies, or tests exist yet. There are no commands to build, lint, or test because nothing has been implemented. When code is added, update this file with the actual commands and architecture.

## What this project is

A rate-limited Flickr upload tool: scan a directory of images and upload them to Flickr at a controlled pace (e.g. 3 images per 30 minutes), rather than all at once.

## Key design decisions from research

These constraints came out of `research/RESEARCH.md` and should guide the implementation:

- **Flickr does not enforce the upload pacing** — its API limit is 3,600 queries/hour per key, far looser than any sane upload schedule. The tool itself must implement the throttling (directory scan, state tracking, pacing/scheduling).
- **Auth is OAuth 1.0a, three-legged** — request token → user authorization (write permission) → permanent token/secret. This exchange is a one-time setup step; the resulting token/secret should be stored and reused, not re-derived per run.
- **Use an existing OAuth/upload client** rather than hand-rolling signing — `flickrapi` or `python-flickr-api` are the candidates noted in research.
- **Credentials (API key, API secret, OAuth token/secret) must never be committed** — keep them in environment variables or a local config file excluded via `.gitignore`, since this repo is on GitHub.
- **Persist upload state** (e.g. filename + hash → uploaded/not) so the tool can be stopped and resumed without re-uploading or skipping files.
- **Two viable pacing architectures**: a long-running loop process that sleeps between batches, or a short script invoked on a schedule (cron/launchd) that uploads up to N files per invocation. The research leans toward the scheduled-invocation pattern as more robust (no long-lived process to keep alive).
- **Error handling distinction**: retry transient errors (network, Flickr error 105) with backoff; treat error 6 (bandwidth limit) and error 98 (bad/expired token) as stop conditions needing user attention, not retries.
- Check `flickr.people.getUploadStatus` for bandwidth/storage headroom before large batches — this is the more likely practical limit (monthly bandwidth on free accounts), not Flickr's per-hour query limit.
