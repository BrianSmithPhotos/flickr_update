# flickr-update

A rate-limited Flickr upload tool: scans a directory of images and uploads them to Flickr at a controlled pace (e.g. 3 images per 30 minutes), rather than all at once.

## Why

Flickr's own API limits are far looser than any sane upload schedule — the platform won't throttle you. The pacing here is for **visibility, not quota**: uploading a large batch at once tends to bury most of the photos, since contacts/recent-activity feeds mostly surface the latest few uploads. Spacing uploads out gives each photo its own moment in front of viewers.

## Status

Research only — see [research/RESEARCH.md](research/RESEARCH.md). No upload logic, scheduling, or auth flow has been implemented yet.

## Planned design

- OAuth 1.0a (three-legged) for Flickr write access; token/secret obtained once and reused.
- Directory scan with persisted upload state (filename/hash → uploaded or not), so the tool can stop and resume safely.
- Pacing via either a long-running sleep loop or a script invoked on a schedule (cron/launchd), uploading up to N files per run.
- Credentials kept out of version control (env vars / local config, gitignored).

See [CLAUDE.md](CLAUDE.md) for full design notes and constraints.
