# flickr-update

A rate-limited Flickr upload tool: scans a directory of images and uploads them to Flickr at a controlled pace (e.g. 3 images per 30 minutes), rather than all at once.

## Why

Flickr's own API limits are far looser than any sane upload schedule — the platform won't throttle you. The pacing here is for **visibility, not quota**: uploading a large batch at once tends to bury most of the photos, since contacts/recent-activity feeds mostly surface the latest few uploads. Spacing uploads out gives each photo its own moment in front of viewers.

## Setup

### 1. Credentials

Copy `.env.example` to `.env` and fill in your Flickr API key and secret:

```
FLICKR_API_KEY=...
FLICKR_API_SECRET=...
```

### 2. Authorize with Flickr (one-time)

Run step 1 to get an authorization URL:

```
python auth.py
```

Open the printed URL in your browser, click "OK, I'll authorize it", then paste the verifier code back:

```
python auth.py <verifier-code>
```

The OAuth token is stored in `~/.flickr/oauth-tokens.sqlite` and reused on every subsequent run.

### 3. Schedule uploads with cron

The cron entry is managed by `run_upload.sh`. To install:

```
crontab -e
```

Add:

```
17 */2 * * * /path/to/flickr_update/run_upload.sh
```

This uploads up to 3 photos every 2 hours at 17 minutes past the hour (00:17, 02:17, 04:17, …). Output is appended to `cron.log` in the project directory.

## Re-authorizing after token expiry

If uploads stop and `cron.log` shows:

```
RuntimeError: Flickr OAuth token is missing or expired. Run 'python auth.py' ...
```

Re-run the two-step auth flow above. The token isn't tied to a specific expiry date but can be invalidated if you revoke access in Flickr's settings or if the token cache (`~/.flickr/oauth-tokens.sqlite`) is deleted.

## Design

- **Auth**: OAuth 1.0a (three-legged). `auth.py` handles the one-time setup; `upload.py` reuses the stored token.
- **State**: Upload progress is persisted in `upload_state.json` (gitignored), keyed by filename. Stops and resumes safely without re-uploading.
- **Error handling**: Transient errors (network, HTTP 504) are logged and skipped. Token errors (Flickr error 98) cause a clean exit with a message pointing to `auth.py`.
- **Credentials**: API key/secret in `.env` (gitignored); OAuth token in `~/.flickr/oauth-tokens.sqlite` (outside the repo).

See [CLAUDE.md](CLAUDE.md) for full design notes.
