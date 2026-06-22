# Flickr Rate-Limited Upload Tool — Research

Date: 2026-06-21

## Question

Can the Flickr API support a tool that reads a directory of images and uploads them at a controlled rate (e.g. 3 images per 30 minutes)?

**Yes.** Flickr's API supports programmatic photo uploads, and the platform's own rate limits are far looser than 3 images/30 min, so the throttling is something the tool enforces itself, not something Flickr enforces for you.

## Flickr Upload API

- Endpoint: `POST https://api.flickr.com/services/upload/` (also reachable at `up.flickr.com`), sent as `multipart/form-data`. This is separate from the main REST API because it carries a binary file.
- Required auth: the call must be signed and carry a token with **write** permission. An API key alone is not enough — write access requires the OAuth 1.0a flow described below.
- Key form fields: `photo` (the file, excluded from the signature), plus optional `title`, `description`, `tags`, `is_public`/`is_friend`/`is_family`, `safety_level`, `content_type`, `hidden`.
- Success response returns a `photoid`. Failure returns a numeric error code (e.g. `6` = monthly bandwidth limit exceeded, `98` = invalid/expired auth token, `100` = invalid API key).
- A companion REST method, `flickr.people.getUploadStatus`, reports the account's current file-size and bandwidth limits — useful for a tool to check headroom before uploading.

Source: [Flickr — Uploading Photos](https://www.flickr.com/services/api/upload.api.html)

## Authentication

Flickr uses **OAuth 1.0a**, a three-legged flow:

1. Request a temporary token using the API key + secret.
2. Redirect the user to Flickr to authorize the app for the permission level needed (write, in this case).
3. Exchange the authorized temporary token for a permanent OAuth token + token secret.

The permanent token/secret pair is then used to sign every upload call. This is a one-time setup step (the resulting token can be stored and reused), not something the tool repeats per run.

Brian already has an API key, but uploading also requires an **API secret** (issued alongside the key) and a **write-permission OAuth token**, obtained once through the authorization flow above.

Source: [Flickr — User Authentication](https://www.flickr.com/services/api/auth.oauth.html)

## Rate Limits

- Flickr's documented general API limit is **3,600 queries/hour per API key**. A schedule of 3 images per 30 minutes (6/hour) is trivially within this — Flickr's limits are not the constraint.
- Separately, free (non-Pro) accounts have **monthly upload bandwidth/storage limits**, checkable via `flickr.people.getUploadStatus`. This is the more relevant cap for a bulk-upload tool and worth checking before a large batch.

Source: [Flickr Help Forum — API Limit of 3,600 queries/hour](https://www.flickr.com/help/forum/en-us/72157645405253549/)

## What the Tool Itself Needs to Provide

Since Flickr won't enforce "3 per 30 minutes" for you, the tool needs its own scheduling and bookkeeping:

1. **Directory scan** — list image files in a folder (filter by extension/MIME type Flickr accepts: jpg, png, gif, etc.), ideally sorted deterministically (e.g. by filename or modified date) so re-runs are predictable.
2. **Upload state tracking** — persist which files have already been uploaded (e.g. a small SQLite database or a JSON/CSV manifest keyed by filename + hash) so the tool can be stopped and resumed without re-uploading or skipping files.
3. **Pacing logic** — a simple scheduler: upload N files, then sleep until the next interval. Two practical patterns:
   - A long-running loop process that sleeps between batches (simplest, but needs to keep running).
   - A short script invoked on a fixed schedule (e.g. cron/launchd every 30 minutes, uploads up to N files per invocation) — more robust since it doesn't depend on a long-lived process surviving.
4. **Credential handling** — store the API key, API secret, and OAuth token/secret outside source control (e.g. environment variables or a local config file excluded via `.gitignore`), since this project is going into a GitHub repo.
5. **Error handling** — retry transient failures (network errors, Flickr error 105 "service unavailable") with backoff; treat error 6 (bandwidth limit) and 98 (bad token) as stop conditions requiring user attention rather than retries.
6. **Logging** — record what was uploaded, when, and the resulting Flickr photo ID/URL, both for auditing and to support the state-tracking in (2).
7. **Library choice** — rather than hand-rolling OAuth 1.0a signing, an existing Python client simplifies this:
   - [`flickrapi`](https://stuvel.eu/flickrapi-doc/) — mature, handles OAuth and uploads.
   - [`python-flickr-api`](https://github.com/alexis-mignon/python-flickr-api) — object-oriented wrapper over the same API.

## Summary

Building this is straightforward: Flickr's upload endpoint and OAuth flow fully support it, and Flickr's own rate limits are not a real constraint at 3 images/30 minutes. The work is mostly in the tool itself — directory scanning, persistent upload state, a pacing/scheduling mechanism, and safe credential storage — rather than anything Flickr-side.
