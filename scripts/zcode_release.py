#!/usr/bin/env python3
"""ZCode release tooling.

Everything ZCode-release specific lives here: where versions are listed,
where builds live on the CDN, and how electron-updater metadata is read.
Callers (the workflow, humans) never need to know any of that.

Seam contract: this module owns the ZCode side only. GitHub-side concerns
(release existence, tags, uploading assets) belong to the caller.

Subcommands:
  latest            Print the latest ZCode version from the download page.
  versions          Print every ZCode version from the download page,
                    one per line, oldest first.
  prepare VERSION   Download the available x64/arm64 AppImages for VERSION, verify
                    them against the published sha512 checksums, and write
                    release assets into --out-dir (default: cwd):
                      ZCode-<version>-x86_64.AppImage
                      ZCode-<version>-aarch64.AppImage
                      SHA512SUMS
                      release-notes.md   (English notes from latest.yml,
                                          with fallbacks)

Exit codes: 0 success, 1 operational failure, 2 usage error.

Requires Python 3 with PyYAML (preinstalled on GitHub-hosted runners).
"""

import argparse
import base64
import hashlib
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

DOWNLOAD_PAGE = "https://zcode.z.ai/en"
CHANGELOG_URL = "https://zcode.z.ai/en/changelog"
CDN_URL = "https://cdn-zcode.z.ai/zcode/electron/releases/{version}/{platform}/{filename}"
VERSION_RE = re.compile(r"zcode/electron/releases/(\d+\.\d+\.\d+)/")

# CDN platform directory -> arch suffix used for the published asset
ARCHES = [
    ("linux-x64", "x86_64"),
    ("linux-arm64", "aarch64"),
]


DOWNLOAD_ATTEMPTS = 5
TIMEOUT = 60
PROGRESS_INTERVAL = 15
MIN_WINDOW_BYTES = 1024 * 1024  # abort + retry below ~70KB/s


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return resp.read().decode()


def exists(url: str) -> bool:
    """Availability probe via a 1-byte ranged GET (HEAD is unreliable on this CDN)."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status in (200, 206, 416)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return False


def fetch_file(url: str, dest: Path) -> None:
    print(f"Downloading {url}", flush=True)
    last = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                window_start = time.monotonic()
                window_bytes = 0
                with dest.open("wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        window_bytes += len(chunk)
                        elapsed = time.monotonic() - window_start
                        if elapsed >= PROGRESS_INTERVAL:
                            if window_bytes < MIN_WINDOW_BYTES:
                                raise OSError(
                                    f"stalled: {window_bytes} bytes in {elapsed:.0f}s"
                                )
                            pct = f" ({done * 100 // total}%)" if total else ""
                            print(f"  {done // (1024 * 1024)}MB{pct}", flush=True)
                            window_start = time.monotonic()
                            window_bytes = 0
                if total and done != total:
                    raise OSError(f"truncated: got {done} of {total} bytes")
            return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            dest.unlink(missing_ok=True)
            if attempt < DOWNLOAD_ATTEMPTS:
                print(f"  retry {attempt + 1}/{DOWNLOAD_ATTEMPTS} ({exc})", flush=True)
                time.sleep(5 * attempt)
    raise RuntimeError(f"download failed after {DOWNLOAD_ATTEMPTS} attempts: {url} ({last})")


def version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def all_versions() -> list:
    versions = sorted(set(VERSION_RE.findall(fetch_text(DOWNLOAD_PAGE))), key=version_key)
    if not versions:
        raise RuntimeError(f"No versions found on {DOWNLOAD_PAGE}")
    return versions


def latest_version() -> str:
    return all_versions()[-1]


def appimage_entry(meta: dict) -> dict:
    """Return the latest.yml file entry for the AppImage."""
    return next(f for f in meta["files"] if f["url"].endswith(".AppImage"))


def sha512_hex(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_notes(meta, version: str) -> str:
    """English release notes from latest.yml, with fallbacks."""
    locale = ((meta or {}).get("releaseNotesByLocale") or {}).get("en-US") or {}
    notes = (locale.get("markdown") or "").strip()
    if not notes:
        notes = ((meta or {}).get("releaseNotes") or "").strip()
    if not notes:
        notes = f"Automated release of ZCode {version} for Linux x64 and aarch64."
    header = f"Automated release of [ZCode {version}]({CHANGELOG_URL}) for Linux x64 and aarch64."
    return f"{header}\n\n{notes}\n"


def prepare_arch(version: str, platform: str, arch: str, out_dir: Path, tmp: Path):
    """Download and verify one arch. Returns (arch, meta, asset, hexdigest) or None."""
    if not exists(CDN_URL.format(version=version, platform=platform, filename="latest.yml")):
        print(f"No {platform} build for {version}, skipping {arch}", flush=True)
        return None

    yml_path = tmp / f"latest-{platform}.yml"
    asset = out_dir / f"ZCode-{version}-{arch}.AppImage"
    fetch_file(
        CDN_URL.format(version=version, platform=platform, filename="latest.yml"),
        yml_path,
    )
    fetch_file(
        CDN_URL.format(
            version=version,
            platform=platform,
            filename=f"ZCode-{version}-{platform}.AppImage",
        ),
        asset,
    )

    with yml_path.open() as f:
        meta = yaml.safe_load(f)
    expected = base64.b64decode(appimage_entry(meta)["sha512"]).hex()
    actual = sha512_hex(asset)
    if actual != expected:
        raise RuntimeError(
            f"Checksum mismatch for {asset.name}: expected {expected}, got {actual}"
        )
    print(f"Checksum OK: {asset.name}", flush=True)
    return arch, meta, asset, actual


def prepare(version: str, out_dir: Path) -> None:
    sums = []
    notes_meta = None

    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=2) as pool:
        results = pool.map(
            lambda pa: prepare_arch(version, pa[0], pa[1], out_dir, Path(tmp)), ARCHES
        )
        for result in results:
            if result is None:
                continue
            _, meta, asset, sha = result
            sums.append(f"{sha}  {asset.name}")
            if notes_meta is None:
                notes_meta = meta

    if not sums:
        raise RuntimeError(f"No builds available for {version}")

    (out_dir / "SHA512SUMS").write_text("\n".join(sums) + "\n")
    (out_dir / "release-notes.md").write_text(extract_notes(notes_meta, version))
    print("Release assets ready.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("latest", help="Print the latest ZCode version")
    sub.add_parser("versions", help="Print all known ZCode versions, oldest first")
    prepare_parser = sub.add_parser("prepare", help="Download and verify release assets")
    prepare_parser.add_argument("version", help="ZCode version, e.g. 3.16.3 (v prefix allowed)")
    prepare_parser.add_argument("--out-dir", type=Path, default=Path.cwd(), help="Output directory (default: cwd)")
    args = parser.parse_args()

    try:
        if args.command == "latest":
            print(latest_version())
        elif args.command == "versions":
            print("\n".join(all_versions()))
        else:
            version = args.version.lstrip("v")
            if not re.fullmatch(r"\d+\.\d+\.\d+", version):
                parser.error(f"Invalid version: {version!r}")
            args.out_dir.mkdir(parents=True, exist_ok=True)
            prepare(version, args.out_dir)
    except (urllib.error.URLError, RuntimeError, StopIteration) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
