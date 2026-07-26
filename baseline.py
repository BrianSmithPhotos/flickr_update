"""One-off pass: record every image currently in a directory as already handled.

Run this after copying an existing archive into the watched tree but BEFORE the
next scheduled run fires. The uploader has no idea what is already on Flickr —
its only memory is upload_state.json — so any photo it has never seen looks new
and would be uploaded again as a duplicate. This script walks the tree exactly
the way the uploader does and writes a `baseline` entry (filename + content
hash, no photo_id) for everything it finds, so those files are permanently
skipped.

Files already in the manifest are left alone: an `uploaded` entry keeps its
photo_id. The only change made to existing entries is backfilling a missing
content hash, which strengthens the rename/duplicate guard for future runs.

    uv run python baseline.py "$PHOTOS_DIR" --dry-run   # preview
    uv run python baseline.py "$PHOTOS_DIR"             # commit
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import scan
import state
import upload

LAUNCHD_LABEL = "com.briansmith.flickrupload"

# Write the manifest every this many files so a long pass over network storage
# is resumable: re-running picks up where it left off.
SAVE_EVERY = 50


def agent_is_loaded() -> bool:
    """True if the launchd upload agent is currently bootstrapped."""
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"],
        capture_output=True,
    )
    return result.returncode == 0


def backup_manifest(manifest_path: Path) -> Path | None:
    if not manifest_path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = manifest_path.with_name(f"{manifest_path.name}.bak-baseline-{stamp}")
    shutil.copy2(manifest_path, backup)
    return backup


def warn_about_root_files(directory: Path) -> None:
    """The scanner ignores images sitting directly in the tree root, so files
    dropped there would never upload — and would never be reported either."""
    loose = [
        p
        for p in directory.glob("*")
        if p.is_file() and p.suffix.lower() in scan.IMAGE_EXTENSIONS
    ]
    if loose:
        print(
            f"NOTE: {len(loose)} image(s) sit directly in {directory} rather than "
            f"in a subfolder. The uploader ignores those, so they are not "
            f"baselined either. Move them into a subfolder if they should be "
            f"considered at all."
        )


def run(args) -> int:
    directory: Path = args.directory
    if not directory.is_dir():
        print(f"Not a directory: {directory}")
        return 1

    manifest_path = args.manifest
    manifest = state.load(manifest_path)
    known = state.known_hashes(manifest)

    try:
        images = scan.find_images(directory)
    except OSError as e:
        print(f"ANOMALY: cannot scan {directory}: {e}")
        return 2

    warn_about_root_files(directory)
    print(f"Found {len(images)} image(s) under {directory}; manifest has {len(manifest)} entry(s).")

    if args.under:
        # Scope the pass to the folder the archive was copied into, so photos
        # still queued for upload elsewhere in the tree can't be swept up.
        subtree = (directory / args.under).resolve()
        if not subtree.is_dir():
            print(f"Not a directory: {subtree}")
            return 1
        in_scope = [p for p in images if subtree in p.resolve().parents]
        # Report what's left outside the scope so it's obvious whether the
        # normal upload queue has drained — those files stay eligible.
        pending = [
            p for p in images if p not in in_scope and not state.is_uploaded(manifest, p)
        ]
        images = in_scope
        print(f"Restricted to {subtree}: {len(images)} image(s).")
        if pending:
            print(
                f"  ({len(pending)} file(s) elsewhere in the tree are still queued "
                f"for upload — left untouched.)"
            )

    new_files = [p for p in images if not state.is_uploaded(manifest, p)]
    backfill = (
        []
        if args.no_backfill
        else [
            p
            for p in images
            if state.is_uploaded(manifest, p) and not manifest[p.name].get("hash")
        ]
    )

    print(f"  {len(images) - len(new_files)} already in manifest")
    print(f"  {len(new_files)} to baseline")
    if backfill:
        print(f"  {len(backfill)} existing entry(s) missing a hash, will backfill")

    if args.dry_run:
        for p in new_files[:20]:
            print(f"  would baseline: {p.name}")
        if len(new_files) > 20:
            print(f"  ... and {len(new_files) - 20} more")
        print("Dry run — nothing written.")
        return 0

    if not new_files and not backfill:
        print("Nothing to do.")
        return 0

    if new_files and not args.yes:
        # This is destructive in the quiet way: any photo baselined here is one
        # that will never be uploaded. If the normal queue hasn't drained yet,
        # these are photos still waiting their turn, not old archive.
        print(
            f"\nAbout to permanently exclude {len(new_files)} file(s) from ever "
            f"being uploaded. Confirm the upload queue is drained "
            f"(main.py reports 'Nothing to upload.') before continuing."
        )
        if input("Type 'baseline' to proceed: ").strip() != "baseline":
            print("Aborted — nothing written.")
            return 1

    backup = backup_manifest(manifest_path)
    if backup:
        print(f"Backed up manifest to {backup.name}")

    baselined = 0
    dupes = 0
    backfilled = 0
    dataless: list[Path] = []
    unreadable: list[tuple[Path, OSError]] = []
    processed = 0

    try:
        for file_path in backfill + new_files:
            is_new = file_path.name not in manifest or not state.is_uploaded(manifest, file_path)

            if upload.is_dataless(file_path):
                # Reading an online-only placeholder can block on hydration for
                # hours. Leave it unrecorded and report it: better to rerun this
                # script once the file is local than to hang the whole pass.
                dataless.append(file_path)
                continue

            try:
                digest = state.file_hash(file_path)
            except OSError as e:
                unreadable.append((file_path, e))
                continue

            if is_new:
                if digest in known:
                    dupes += 1
                else:
                    known[digest] = file_path.name
                state.mark_baseline(manifest, file_path, digest)
                baselined += 1
            elif not manifest[file_path.name].get("hash"):
                # Existing uploaded/baseline entry with no hash — fill it in
                # without disturbing photo_id or status. Guarded because the
                # manifest is keyed by filename, so a same-named file elsewhere
                # in the tree lands here too and must not clobber a real hash.
                manifest[file_path.name]["hash"] = digest
                known.setdefault(digest, file_path.name)
                backfilled += 1

            processed += 1
            if processed % SAVE_EVERY == 0:
                state.save(manifest, manifest_path)
                print(f"  ... {processed}/{len(backfill) + len(new_files)}")
    except KeyboardInterrupt:
        state.save(manifest, manifest_path)
        print(f"\nInterrupted. Progress saved ({processed} file(s) recorded); rerun to continue.")
        return 130

    state.save(manifest, manifest_path)

    print(f"Baselined {baselined} file(s) ({dupes} of them duplicate content of a known photo).")
    if backfilled:
        print(f"Backfilled hashes for {backfilled} existing entry(s).")
    if dataless:
        print(
            f"WARNING: {len(dataless)} file(s) are online-only and were NOT baselined. "
            f"They will be treated as new by the uploader. Make them available "
            f"offline in Google Drive and rerun this script:"
        )
        for p in dataless[:10]:
            print(f"  {p}")
        if len(dataless) > 10:
            print(f"  ... and {len(dataless) - 10} more")
    if unreadable:
        print(f"WARNING: {len(unreadable)} file(s) could not be read and were NOT baselined:")
        for p, e in unreadable[:10]:
            print(f"  {p}: {e}")

    return 2 if (dataless or unreadable) else 0


def main():
    parser = argparse.ArgumentParser(
        description="Mark every image in a directory as already handled, so the "
        "uploader never uploads it."
    )
    parser.add_argument("directory", type=Path, help="Directory of images to baseline")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=state.MANIFEST_PATH,
        help="Path to the upload state manifest",
    )
    parser.add_argument(
        "--under",
        help="Only baseline images under this subfolder of DIRECTORY, leaving "
        "the rest of the tree (e.g. photos still queued for upload) untouched",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be baselined without writing the manifest",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        help="Don't fill in missing content hashes on existing manifest entries",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed even if the launchd upload agent is still loaded",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.force and agent_is_loaded():
        print(
            f"The launchd agent {LAUNCHD_LABEL} is still loaded — a scheduled run "
            f"could upload files mid-pass. Pause it first:\n"
            f"  launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/{LAUNCHD_LABEL}.plist\n"
            f"and re-bootstrap it when this finishes. Use --force to override."
        )
        sys.exit(1)

    sys.exit(run(args))


if __name__ == "__main__":
    main()
