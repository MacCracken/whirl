# Changelog

All notable changes to whirl are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions are [SemVer](https://semver.org/).

## [Unreleased]

## [0.6.2] — 2026-06-23 (AGNOS QEMU validation + HTTPS CA fix + kernel-leased resolver)

### Changed
- **AGNOS DNS resolution prefers the kernel-leased on-subnet resolver** (via **taar
  0.3.1**, dep bumped 0.3.0 → 0.3.1). `taar_resolve_ipv4` now consults the new agnos
  `net_config(3)`#61 syscall (the DHCP option-6 resolver) before the off-subnet
  `8.8.8.8` fallback. The off-subnet fallback needs working gateway routing the kernel
  can't guarantee on real iron — it froze `whirl https://google.com` on archaemenid
  (the binary exec'd and resolved into the void). The leased resolver is on-subnet +
  directly reachable. Linux is unchanged. **Requires agnos ≥ 1.45.16.**

### Validated on AGNOS (QEMU + KVM, virtio-net + SLIRP)
- **whirl runs on agnos end-to-end** — booted a production kernel with the staged
  rootfs (`/bin/whirl`) and fetched **real example.com pages over the sovereign
  stack**: exec-from-disk (1.1 MB binary, ring 3) → taar DNS (`udp_*`#51-54) →
  `sock_connect`#47 → HTTP framing → body. **HTTP and HTTPS both PASS.** Harness:
  `agnos/scripts/whirl-smoke.sh`.

### Fixed — HTTPS on AGNOS (the 0.6.1 path didn't actually work)
- 0.6.1 claimed HTTPS-on-agnos "correct-by-construction"; QEMU testing proved it
  failed: cyrius's `tls_native_set_ca_system` opens the CA bundle with the **Linux**
  `sys_open(path, flags, mode)` ABI, but agnos `sys_open` is `(name, namelen, flags)`
  → `namelen=0` → the trust store never loads → fail-closed handshake. (A verify-none
  handshake completes fine on agnos, isolating the fault to trust-root loading — the
  `set_transport`-over-taar path itself is correct.)
- **`_agnos_ca_hook`** (`src/transport.cyr`, `#ifdef CYRIUS_TARGET_AGNOS`): loads the
  staged `/etc/ssl/cert.pem` with the correct agnos ABI and installs it via
  `tls_native_set_ca_bundle` through `tls_connect_with_ctx_hook` — fail-closed cert +
  hostname verification now passes on agnos. Stopgap until the cyrius fix lands (filed
  `cyrius/docs/development/issues/2026-06-18-tls-native-set-ca-system-agnos-sys-open-abi.md`).
- Requires the CA bundle staged on the agnos-fs — wired into `agnos/scripts/stage-tools.sh`.
- Linux unchanged (the `#ifndef` path still uses plain `tls_connect`; HTTPS regression green).

## [0.6.1] — 2026-06-18 — HTTPS on AGNOS (tls_native transport hook)

Closes the `https://` path on agnos. On Linux, tls_native does raw `sys_read`/
`sys_write` on the real socket fd — but taar's agnos TCP "fd" is a sentinel (the
real conn_id lives in a taar module global), so the default path can't route.

### Added
- **`tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)`** in
  `transport_fetch_tls`, under `#ifdef CYRIUS_TARGET_AGNOS` — installs taar's TCP
  recv/send as tls_native's transport vtable (the v6.2.4 "Option C" hook). The
  per-conn handle whirl passes to `tls_connect` is forwarded to the leaf helpers,
  but taar's recv/send read the active conn from their own global, so any handle
  works. `now_fn = 0` keeps the agnos default (`_tn_now_unix` → `sys_time_unix`#46)
  for cert-window validation — **fail-closed cert + hostname verification is
  unchanged on agnos**.

### Notes
- Zero new cyrius/kernel surface: `tls_native_set_transport` (cyrius v6.2.4) and
  `sys_time_unix`#46 (v6.2.3) are both ≤ the pinned 6.2.6. Linux is untouched
  (the `#ifdef` is agnos-only; the default raw-fd path still serves Linux).

### Verified
- **Linux**: HTTPS regression unchanged (example.com fetched; `expired.badssl.com`
  fail-closed). 52 unit assertions green.
- **AGNOS**: compiles clean — `tls_native_set_transport` + `&taar_tcp_recv` /
  `&taar_tcp_send` resolve. End-to-end `https://` is correct-by-construction
  (transport vtable + matching read/write signatures + agnos cert clock); iron
  validation on archaemenid is 0.6.2.

## [0.6.0] — 2026-06-18 — HTTP on AGNOS (sovereign backend)

whirl's plain-HTTP path now runs over the **AGNOS kernel's own network stack** —
no POSIX `socket()`, no Linux syscall numbers anywhere in the agnos build. The
transport rides **taar 0.3.0**'s sovereign backend; the rest of whirl's I/O was
made target-agnostic so the whole tool compiles + behaves correctly on agnos.

### Added
- **`[deps.taar]` → 0.3.0** — taar's AGNOS backend (TCP over `sock_connect`#47 /
  `sock_send`#48 / `sock_recv`#49 / `sock_close`#50; DNS over `udp_*`#51-54;
  entropy via `getrandom`#45). `transport_fetch` needed **zero** changes — the
  `taar_tcp_*` / `taar_resolve_ipv4` API is identical across Linux and agnos.
- **AGNOS build target** — `CYRIUS_TARGET_AGNOS=1 cyrius build src/main.cyr`
  emits an agnos ring-3 binary (1.10 MB). The full stack (HTTP framing, links,
  robots, tls) compiles for agnos.

### Changed (portable I/O — correctness on agnos)
- `_puts` / `_eputs` / `_eput_int` now use the **`sys_write`** wrapper (raw
  `syscall(1,…)` is Linux-only; agnos's syscall ABI differs — `1` isn't `write`).
- `_sleep_ms` → chrono **`sleep_ms`** (was raw `nanosleep`#35).
- `-d @file` → portable **`file_read_all`** (io); `-d @-` stdin + `--retry` read
  via the **`sys_read`** wrapper.
- `_mkdir` and `output_file_size` carry a minimal `#ifdef CYRIUS_TARGET_AGNOS`
  branch (the `sys_mkdir` / `sys_stat` signatures differ; agnos size via
  `sys_stat` STAT_SIZE). `-C` append: Linux true `O_APPEND`; agnos read-modify-
  write (no `O_APPEND`/flock in the frozen FS surface; ≤1 MB resume cap there).

### Verified
- **Linux**: build + **52** unit assertions + live regression (HTTP, HTTPS w/
  cert verify, `-C` resume → reassembled, `-d @file`, `--retry`) — no behavior
  change from the portable-I/O refactor.
- **AGNOS**: compiles clean (no undefined-function warnings; `sys_sock_*` /
  `sys_udp_*` / `sys_getrandom` / `sys_stat` / `sys_mkdir` resolve). Iron
  validation on archaemenid (`whirl http://… ` over the sovereign stack) is the
  0.6.x roadmap step.

### Still ahead
- **0.6.1**: HTTPS on agnos — the taar TCP "fd" is a sentinel there, so
  tls_native's default raw-fd read/write won't route; wire
  `tls_native_set_transport(read, write, now)` → `taar_tcp_recv`/`send`.
- Iron burn + curl parity benchmark (latency / RSS / binary size).

## [0.5.3] — 2026-06-18 — polish (curl/wget flag round-out)

### Added
- **`-A UA` / `--user-agent UA`** — override the `User-Agent` (default `whirl/<ver>`). New `http_set_user_agent`.
- **`-i`** — include the response status line + headers in the output (verbatim response).
- **`-I`** — HEAD request (headers only; method override + implies header output).
- **`-f`** — fail on HTTP ≥ 400: suppress the body, report `whirl: HTTP <code>`, exit **22** (curl-compatible).
- **`-d @file` / `-d @-`** — read the request body from a file or stdin (≤ 256 KB). **`--data-binary`** added (same loader, raw body).
- **robots.txt `Allow:` precedence** — `-r` now parses `Allow:` as well as `Disallow:` and applies RFC 9309 longest-match specificity (a tie resolves to Allow). New `_robots_dup`; `_robots_parse`/`_robots_load`/`_robots_blocked` carry a parallel allow/disallow flag array.

### Validated
- Live (postman-echo / example.com): `-A` echoed; `-i` emitted status+headers; `-I` returned headers only; `-f` on a 404 → exit 22, 0 body bytes; `-d @file` and `-d @-` echoed the body. **Allow precedence proven on `en.wikipedia.org`** — `/w/load.php?…` saved (matches the longer `Allow: /w/load.php?`) while `/w/index.php?…` and `/w/rest.php/…` blocked (only `Disallow: /w/`). 52 unit assertions green.

## [0.5.2] — 2026-06-18 — resume (-C)

### Added
- **`-C`** — resume a partial download. When the `-o`/`-O` output file already exists, whirl sends `Range: bytes=<size>-` and:
  - **206 Partial Content** → appends the remainder (`output_append`),
  - **200 OK** (server ignores Range) → overwrites with the full body,
  - **416 Range Not Satisfiable** → reports "already complete".
  Resume applies to the first hop only (a redirect falls back to a full GET). New `output_file_size` (`lseek` SEEK_END) + `_build_range_header`.
- Live-validated: example.com 559 B → truncated to 300 B → `-C` → "resumed at 300 bytes" → reassembled to 559 B (valid tail); `Range: bytes=N-` confirmed sent via postman-echo; 200-overwrite path confirmed.

## [0.5.1] — 2026-06-18 — -r niceties

### Added / Changed
- **Directory-tree mirroring** — `-r` saves each resource to a path tree under cwd (`/docs/g.html` → `docs/g.html`, creating dirs; `/` or `/d/` → `…/index.html`) instead of flat `a_b.html` names.
- **`../` / `.` path normalization** (RFC 3986 §5.2.4) — new `links_path_normalize`; relative + root-relative links are normalized before fetch/dedup (6 unit tests).
- **robots.txt** — `-r` fetches `/robots.txt` and honors `Disallow` for `User-agent: *`; blocked paths are skipped.
- **Protocol-relative links** (`//host/path`) now resolve to scheme + host (→ cross-host, filtered) instead of being mis-saved as a base-host path.
- **52** unit assertions. Live: info.cern.ch saved a nested tree; the Wikipedia crawl honored robots (`/w/…` blocked) and filtered cross-host (`upload.wikimedia.org`).

## [0.5.0] — 2026-06-18 — wget side (-O / --retry / -r)

### Added
- **`-O`** — save the body to a filename derived from the URL path (last segment; `index.html` for `/` or a trailing slash). New `url_filename(path)`.
- **`--retry N`** — retry transient connection failures N times with linear backoff (`200·attempt` ms).
- **`-r` recursive fetch** (`-l N` depth, default 1) — `src/links.cyr` extracts `href`/`src` values; the crawl resolves them (absolute / root-relative / relative), **bounds to the same host**, dedups visited, caps at 64 fetches, and saves each resource to a flat file (`/a/b.html` → `a_b.html`). Cross-host / `#`-fragment / `mailto:` links are skipped.
- **46** unit assertions (links extraction + `url_filename`). Live-validated: `-O https://example.com` → `index.html`; `--retry 2` on a bad host retries then fails; `-r http://info.cern.ch` saved `index.html` + `hypertext_WWW_TheProject.html` (same-host relative link followed, cross-host filtered).

### Still ahead
- `-r` niceties: directory-tree mirroring (vs flat names), `robots.txt`, `../` path normalization.
- resume (`-C`), `--data-binary` / stdin body.
- AGNOS socket backend (taar `#ifdef` + tls_native `set_transport`).

## [0.4.0] — 2026-06-18 — methods + bodies

### Added
- **`-X METHOD`** — arbitrary request method (default GET, or POST when `-d` is given).
- **`-d DATA`** — request body → POST + `Content-Length` + default `Content-Type: application/x-www-form-urlencoded`.
- **`-H 'Header: value'`** — repeatable custom headers; a caller `Content-Type` overrides the default.
- `http.cyr` generalized to `http_build_request(method, host, path, hdrs, nhdrs, body, bodylen, …)`; `http_build_get` is now a thin wrapper. Redirects (`-L`) follow as **GET with the body dropped** (the 301/302/303 norm); custom headers persist across hops.
- **Validated live over HTTPS** (postman-echo): `-d` POST echoed as form data, `-H` header echoed back, `-X DELETE` reached the delete endpoint. **37** unit assertions (6 new for request build + custom headers).

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
