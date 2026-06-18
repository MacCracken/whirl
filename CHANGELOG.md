# Changelog

All notable changes to whirl are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions are [SemVer](https://semver.org/).

## [Unreleased]

### Planned (next bite)
- HTTP/1.1 GET transport: `src/url.cyr` (scheme/host/port/path parse), `src/http.cyr` (request build + response/status/header/chunked parse), `src/transport.cyr` (TCP connect + optional TLS wrap), `src/cli.cyr` (arg parsing).
- Per-backend split: `src/platform_linux.cyr` (POSIX) + `src/platform_agnos.cyr` (sovereign `sock_*`#47-50 + `getrandom`#45 + `tls_native` transport callbacks).
- `[deps.taar]` + stdlib `net`/`tls_native`/`sigil` wired; `tests/whirl.tcyr` unit suite.

## [0.1.0] — 2026-06-18 — scaffold

### Added
- Repo skeleton mirroring the network-tools family (`yo` / `dig` / `taar`): `cyrius.cyml` (pin 6.2.6), `VERSION`, `LICENSE` (GPL-3.0-only), `README.md`, `CLAUDE.md`, `.gitignore`.
- CI + release workflows using the upstream `install.sh` toolchain pattern from the start (lays out `~/.cyrius/versions/<v>/` — avoids the hand-rolled curl+cp `cyrius deps` pin-check failure).
- `docs/development/roadmap.md` (MVP scope, backlog, v1.0 criteria, and the **AGNOS call surface** — the syscalls/peer functions whirl's agnos backend binds) + `docs/development/state.md`.
- Compilable `src/main.cyr` stub (prints usage; transport WIP) + `src/test.cyr` entry.
