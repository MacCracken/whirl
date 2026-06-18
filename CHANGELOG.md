# Changelog

All notable changes to whirl are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions are [SemVer](https://semver.org/).

## [Unreleased]

## [0.3.0] — 2026-06-18 — HTTPS + redirect UX

### Added
- **HTTPS** (`src/transport.cyr` `transport_fetch_tls`): TLS session over taar's TCP
  socket via the stdlib `tls_connect`/`tls_read`/`tls_write`/`tls_close`. The
  `tls_native` engine verifies the cert chain + hostname **fail-closed** (CVE-18) —
  `https://expired.badssl.com` is rejected. Sovereign: tls_native's default raw
  read/write on the fd is used; the libssl/`fdlopen` fallback is DCE'd out.
- `main.cyr` routes `https://` (and https redirect targets, with `-L`) to the TLS path.
- **Opt-in deps** (vendored via `cyrius lib sync`, wired into CI): `chrono` / `ct` /
  `keccak` / `random` / `bayan` / `sigil` / `tls_native` / `tls`.
- **Redirect UX**: a bare 3xx without `-L` now prints `whirl: <code> redirect -> <loc>
  (use -L to follow)` to stderr (stdout stays clean) instead of a silent empty body.

### Validated
- `whirl https://example.com` fetches end-to-end (handshake + cert verify + GET);
  `-o FILE` works. Bad-cert host fails closed.

### Still ahead
- POST (`-d`), arbitrary methods (`-X`), custom headers (`-H`).
- AGNOS socket backend (taar's socket is Linux-only; tls_native's `set_transport`
  wires over taar's agnos socket there).

## [0.2.0] — 2026-06-18 — HTTP/1.1 GET MVP (over taar)

whirl fetches real HTTP end-to-end. The transport is sovereign raw-syscall over
the **taar** substrate (no stdlib net): taar's DNS + TCP under whirl's own HTTP
framing — the option chosen for the family's lean per-backend posture.

### Added
- **`src/url.cyr`** — http/https URL parse (scheme / host / port / path; default 80/443; rejects bad scheme / empty host / port > 65535).
- **`src/http.cyr`** — HTTP/1.1 request build + response parse: status code, body offset, case-insensitive header lookup, Content-Length, chunked detect + decode.
- **`src/transport.cyr`** — resolve (`taar_resolve_ipv4`) + TCP connect/send/recv (`taar_tcp_*`) with a recv timeout. Sovereign, no `lib/net.cyr`.
- **`src/cli.cyr`** (`<url>` / `-o FILE` / `-L` / `-h`) + **`src/output.cyr`** (stdout or file via `file_write_all`).
- `main.cyr` wiring with redirect following (`-L`, up to 10 hops).
- **`[deps.taar]`** — whirl is taar's third consumer; pins `taar` **0.2.0** (socket + dns).
- `tests/whirl.tcyr` → **31 assertions** (URL + HTTP framing).

### Validated
- Live: `whirl http://neverssl.com` fetches the page to stdout and via `-o FILE`.

## [0.1.0] — 2026-06-18 — scaffold

### Added
- Repo skeleton mirroring the network-tools family (`yo` / `dig` / `taar`): `cyrius.cyml` (pin 6.2.6), `VERSION`, `LICENSE` (GPL-3.0-only), `README.md`, `CLAUDE.md`, `.gitignore`.
- CI + release workflows using the upstream `install.sh` toolchain pattern from the start (lays out `~/.cyrius/versions/<v>/` — avoids the hand-rolled curl+cp `cyrius deps` pin-check failure).
- `docs/development/roadmap.md` (MVP scope, backlog, v1.0 criteria, and the **AGNOS call surface** — the syscalls/peer functions whirl's agnos backend binds) + `docs/development/state.md`.
- Compilable `src/main.cyr` stub (prints usage; transport WIP) + `src/test.cyr` entry.
