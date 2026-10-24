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
  prepare VERSION   Download the x64 + arm64 AppImages for VERSION, verify
                    them against the published sha512 checksums, and write
                    release assets into --out-dir (default: cwd):
                      ZCode-<version>-x86_64.AppImage
                      ZCode-<version>-aarch64.AppImage
                      SHA512SUMS
                      release-notes.md   (English notes from latest.yml,
                                          with fallbacks)

Exit codes: 0 success, 1 operational failure, 2 usage error.

Requires Python 3 with PyYAML (preinstalled on GitHub-hosted runners) and curl.
"""

import argparse
import base64
import hashlib
import re
import subprocess
import sys
import tempfile
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


def fetch_text(url: str) -> str:
    return subprocess.run(
        ["curl", "-fsSL", url], check=True, capture_output=True, text=True
    ).stdout


def fetch_file(url: str, dest: Path) -> None:
    print(f"Downloading {url}", flush=True)
    subprocess.run(
        ["curl", "-fsSL", "--retry", "3", "--retry-delay", "5", "-o", str(dest), url],
        check=True,
    )


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


def extract_notes(meta: dict, version: str) -> str:
    """English release notes from latest.yml, with fallbacks."""
    locale = (meta.get("releaseNotesByLocale") or {}).get("en-US") or {}
    notes = (locale.get("markdown") or "").strip()
    if not notes:
        notes = (meta.get("releaseNotes") or "").strip()
    if not notes:
        notes = f"Automated release of ZCode {version} for Linux x64 and aarch64."
    header = f"Automated release of [ZCode {version}]({CHANGELOG_URL}) for Linux x64 and aarch64."
    return f"{header}\n\n{notes}\n"


def prepare(version: str, out_dir: Path) -> None:
    metas = {}
    sums = []

    with tempfile.TemporaryDirectory() as tmp:
        for platform, arch in ARCHES:
            yml_path = Path(tmp) / f"latest-{platform}.yml"
            fetch_file(
                CDN_URL.format(version=version, platform=platform, filename="latest.yml"),
                yml_path,
            )
            with yml_path.open() as f:
                metas[arch] = yaml.safe_load(f)

            asset = out_dir / f"ZCode-{version}-{arch}.AppImage"
            fetch_file(
                CDN_URL.format(
                    version=version,
                    platform=platform,
                    filename=f"ZCode-{version}-{platform}.AppImage",
                ),
                asset,
            )

            expected = base64.b64decode(appimage_entry(metas[arch])["sha512"]).hex()
            actual = sha512_hex(asset)
            if actual != expected:
                raise RuntimeError(
                    f"Checksum mismatch for {asset.name}: expected {expected}, got {actual}"
                )
            print(f"Checksum OK: {asset.name}", flush=True)
            sums.append(f"{actual}  {asset.name}")

    (out_dir / "SHA512SUMS").write_text("\n".join(sums) + "\n")
    (out_dir / "release-notes.md").write_text(extract_notes(metas["x86_64"], version))
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
    except (subprocess.CalledProcessError, RuntimeError, StopIteration) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
