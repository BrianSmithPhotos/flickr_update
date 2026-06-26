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
uv run python auth.py
```

Open the printed URL in your browser, click "OK, I'll authorize it", then paste the verifier code back:

```
uv run python auth.py <verifier-code>
```

The OAuth token is stored in `~/.flickr/oauth-tokens.sqlite` and reused on every subsequent run.

### 3. Schedule uploads with launchd

The upload schedule is managed by a launchd agent. To install:

```
cp com.briansmith.flickrupload.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.briansmith.flickrupload.plist
```

This uploads up to 3 photos every hour at 17 minutes past the hour. Unlike cron, launchd fires any missed runs after the Mac wakes from sleep. Upload output is appended to `cron.log`; any script-level errors go to `launchd_error.log`.

To unload (pause uploads):

```
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.briansmith.flickrupload.plist
```

## Re-authorizing after token expiry

If uploads stop and `cron.log` shows:

```
RuntimeError: Flickr OAuth token is missing or expired. Run 'python auth.py' ...
```

Re-run the two-step auth flow above (using `uv run python auth.py`). The token isn't tied to a specific expiry date but can be invalidated if you revoke access in Flickr's settings or if the token cache (`~/.flickr/oauth-tokens.sqlite`) is deleted.

## Design

- **Auth**: OAuth 1.0a (three-legged). `auth.py` handles the one-time setup; `upload.py` reuses the stored token.
- **State**: Upload progress is persisted in `upload_state.json` (gitignored), keyed by filename. Stops and resumes safely without re-uploading.
- **Error handling**: Transient errors (network, HTTP 504) are logged and skipped. Token errors (Flickr error 98) cause a clean exit with a message pointing to `auth.py`.
- **Credentials**: API key/secret in `.env` (gitignored); OAuth token in `~/.flickr/oauth-tokens.sqlite` (outside the repo).

See [CLAUDE.md](CLAUDE.md) for full design notes.
