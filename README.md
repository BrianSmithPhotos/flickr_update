# flickr-update

A rate-limited Flickr upload tool: scans a directory of images and uploads them to Flickr at a controlled pace (2 images per hour), rather than all at once.

## Why

Flickr's own API limits are far looser than any sane upload schedule — the platform won't throttle you. The pacing here is for **visibility, not quota**: uploading a large batch at once tends to bury most of the photos, since contacts/recent-activity feeds mostly surface the latest few uploads. Spacing uploads out gives each photo its own moment in front of viewers.

## Setup

### 1. Credentials

Copy `.env.example` to `.env` and fill it in:

```
FLICKR_API_KEY=...
FLICKR_API_SECRET=...
PHOTOS_DIR="/Users/you/Library/CloudStorage/GoogleDrive-you@example.com/My Drive/Photos2026"
```

`PHOTOS_DIR` lives here rather than in `run_upload.sh` because the path embeds
your local username and cloud account name, and this repo is public. `.env` is
gitignored. If it's missing or points at a nonexistent directory, `run_upload.sh`
logs the reason and fires a desktop notification rather than silently uploading
nothing.

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
cp photos.briansmith.flickrupload.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/photos.briansmith.flickrupload.plist
```

This uploads up to 2 photos every hour at 17 minutes past the hour. Unlike cron, launchd fires any missed runs after the Mac wakes from sleep. Upload output is appended to `cron.log`; any script-level errors go to `launchd_error.log`.

To unload (pause uploads):

```
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/photos.briansmith.flickrupload.plist
```

## Adding an existing archive to the watched folder

The uploader never asks Flickr what's already there — `upload_state.json` is its
only memory. Photos copied in from an older archive are indistinguishable from
new ones and **will be uploaded again as duplicates**. Before adding any, use
`baseline.py` to record them as already handled:

```
# 1. Pause the scheduled agent so a run can't fire mid-pass
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/photos.briansmith.flickrupload.plist

# 2. Copy the archive into its own subfolder, then preview
uv run python baseline.py "$PHOTOS_DIR" --under Archive --dry-run

# 3. Commit, and re-bootstrap the agent
uv run python baseline.py "$PHOTOS_DIR" --under Archive
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/photos.briansmith.flickrupload.plist
```

The dry run reports how many files elsewhere in the tree are still queued for
upload, so you can confirm the archive folder is the only thing being touched.

`--under` is the important safety: it confines the pass to the folder the
archive landed in, so photos still queued elsewhere in the tree can't be swept
up. Anything baselined is excluded from upload permanently, so the script backs
up the manifest first and prompts for confirmation. Files already in the
manifest keep their `photo_id`; the only change to them is filling in a missing
content hash.

Two things to watch:

- **Files must be available offline.** Placeholders can't be hashed and are
  reported, not baselined — they'd still be seen as new. `Photos2026` is already
  marked available offline in Google Drive, so copied-in files inherit that;
  just confirm the copy has finished syncing before running the script.
- **Images placed directly in `$PHOTOS_DIR`** (not in a subfolder) are ignored by
  the scanner entirely, so they never upload and aren't baselined either.

## Re-authorizing after token expiry

If uploads stop and `cron.log` shows:

```
RuntimeError: Flickr OAuth token is missing or expired. Run 'python auth.py' ...
```

Re-run the two-step auth flow above (using `uv run python auth.py`). The token isn't tied to a specific expiry date but can be invalidated if you revoke access in Flickr's settings or if the token cache (`~/.flickr/oauth-tokens.sqlite`) is deleted.

## Design

- **Auth**: OAuth 1.0a (three-legged). `auth.py` handles the one-time setup; `upload.py` reuses the stored token.
- **State**: Upload progress is persisted in `upload_state.json` (gitignored), keyed by filename. Stops and resumes safely without re-uploading.
- **Error handling**: Transient errors (network, HTTP 504) are logged and skipped; each HTTP request times out after 60s so a stalled connection cannot hang the run. Token errors (Flickr error 98) cause a clean exit with a message pointing to `auth.py`.
- **Credentials**: API key/secret in `.env` (gitignored); OAuth token in `~/.flickr/oauth-tokens.sqlite` (outside the repo).

See [CLAUDE.md](CLAUDE.md) for full design notes.
