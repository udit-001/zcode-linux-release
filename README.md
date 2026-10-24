<h1 align="center">
  <img align="top" width="44" src="assets/logo.png">
  <span>ZCode AppImage Updater</span>
</h1>

<p align="center">
  <a href="https://github.com/udit-001/zcode-linux-release/releases/latest" target="_blank"><img alt="release" src="https://img.shields.io/github/v/release/udit-001/zcode-linux-release?label=release&labelColor=%231e1e2e&color=%234fa048"></a>
  <span> </span>
  <a href="https://github.com/udit-001/zcode-linux-release/actions/workflows/release.yml" target="_blank"><img alt="build" src="https://img.shields.io/github/actions/workflow/status/udit-001/zcode-linux-release/release.yml?branch=main&labelColor=%231e1e2e&color=%234fa048"></a>
  <span> </span>
</p>

**The latest ZCode for Linux, mirrored to GitHub releases daily — checksum-verified, with English release notes and download URLs that never change.**

## Get ZCode

Download the AppImage for your architecture from the [latest release](https://github.com/udit-001/zcode-linux-release/releases/latest):

- **x86_64** — `ZCode-*-x86_64.AppImage`
- **ARM64** — `ZCode-*-aarch64.AppImage`

Every release ships a `SHA512SUMS` file. Verify your download:

```
sha512sum -c SHA512SUMS
```

## Auto-update with Gear Lever

Point [Gear Lever](https://github.com/mijorus/gearlever) at a stable URL and it picks up each new release automatically. Configure the update URL for your architecture ([guide](https://mijorus.it/posts/gearlever/update-url-info/)):

- **x86_64**
  ```
  https://github.com/udit-001/zcode-linux-release/releases/download/*/ZCode-*-x86_64.AppImage
  ```

- **ARM64**
  ```
  https://github.com/udit-001/zcode-linux-release/releases/download/*/ZCode-*-aarch64.AppImage
  ```

## Why this repo exists

ZCode publishes its Linux builds on a per-version CDN path — there is no fixed download URL and no API that answers "what's the latest?". [Cursor](https://github.com/udit-001/cursor-linux-release) had the same problem minus an API, so this repo borrows its approach:

- **Detects** the newest version listed on the [download page](https://zcode.z.ai/en#all-downloads), daily
- **Downloads** every available AppImage (x64/arm64) and verifies it against the sha512 checksums ZCode publishes in its electron-updater metadata (`latest.yml`) — a mismatch fails the build. Versions the CDN no longer hosts are skipped.
- **Publishes** a GitHub release with the English changelog (from `latest.yml`'s `releaseNotesByLocale`) and a `SHA512SUMS` file

## Hacking

`scripts/zcode_release.py` holds all the ZCode-specific logic; the workflow is a thin wrapper around it. To test locally (Python 3 with PyYAML, plus curl):

```
python3 scripts/zcode_release.py latest
python3 scripts/zcode_release.py prepare 3.16.3 --out-dir /tmp/zcode
```

## 📅 Release Status
- **⏳ Last Released On**: 2026-10-24 02:03:11 UTC
- **🔄 Last Run**: 2026-10-24 02:03:11 UTC
