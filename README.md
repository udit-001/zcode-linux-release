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

**The latest ZCode for Linux, mirrored to GitHub releases daily — checksum-verified, stable download URLs.**

## Get ZCode

Download the AppImage for your architecture from the [latest release](https://github.com/udit-001/zcode-linux-release/releases/latest) — `ZCode-*-x86_64.AppImage` or `ZCode-*-aarch64.AppImage` — and verify with the attached `SHA512SUMS`:

```
sha512sum -c SHA512SUMS
```

## Auto-update with Gear Lever

[Gear Lever](https://github.com/mijorus/gearlever) picks up each new release automatically. In its **Update management** screen, set the source to **Github** and fill in:

- **Username/Repo** — `udit-001/zcode-linux-release`
- **Release file name** — `ZCode-*-x86_64.AppImage` (or `ZCode-*-aarch64.AppImage` on ARM)

Leave **Allow pre-releases** off unless you want in-progress builds.

## How it works

Z.ai serves Linux builds on per-version CDN paths — no fixed URL, no "latest" API. A daily action grabs the newest version from the [download page](https://zcode.z.ai/en#all-downloads), verifies each AppImage against the sha512 checksums in Z.ai's own electron-updater metadata, and publishes a release with the English changelog.

Logic lives in `scripts/zcode_release.py`; test locally with Python 3 + PyYAML:

```
python3 scripts/zcode_release.py latest
python3 scripts/zcode_release.py prepare 3.16.3 --out-dir /tmp/zcode
```

## 📅 Release Status
- **⏳ Last Released On**: 2026-10-24 02:19:00 UTC
- **🔄 Last Run**: 2026-10-28 06:00:22 UTC
