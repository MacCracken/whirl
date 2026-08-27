# Changelog

All notable changes to whirl are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions are [SemVer](https://semver.org/).

## [Unreleased]

## [0.6.6] — 2026-08-27 (P-1 security + correctness sweep; CI compiles the AGNOS arm)

A hardening cut. A multi-lens audit of `src/` produced findings that were then
adversarially re-checked; the survivors are fixed here. **Three are genuine
remote-attacker security defects** — one of them a remote arbitrary file write.
Every fix below was proven by running the 0.6.5 binary against a local test
server to reproduce the defect, then the 0.6.6 binary against the same server to
show it closed (17 paired checks, plus positive controls that the fixes do not
over-block).

### Security — fixed
- **Remote arbitrary file write in `-r` (path traversal).** `_resolve_link`
  returned absolute same-host links *verbatim*, skipping the `links_path_normalize`
  applied to relative ones, and `_save_tree` sanitized the result only by
  stripping **one** leading `/`. A crawled page containing
  `<a href="http://host/../../../../tmp/x">` — or the `//tmp/x` variant, which
  survived one slash-strip as the absolute path `/tmp/x` — made whirl create or
  truncate files anywhere the user could write. **Reproduced against 0.6.5**,
  which wrote `/tmp/whirl_pwned_marker2` outside the crawl directory.
  Confinement now lives at `_save_tree`, the single point that touches the
  filesystem: any `..` segment is refused outright and *all* leading slashes are
  stripped, so the write is always relative to cwd regardless of caller.
- **Request splitting via an attacker-controlled `Location` / `href`.**
  `_dup_location` stops only at CR, `url_parse` copied the path through to NUL
  without validation, and `http_build_request` writes host and path into the
  request line **unescaped** — so a redirect carrying bare LFs spliced
  attacker-chosen headers, or a whole second request, into the request whirl
  then sent to the *redirect target*. Now rejected in `url_parse`: controls,
  space and DEL are refused in both host and path. One choke point covers the
  command line, `Location:` and crawled hrefs alike. High bytes (≥ 128) still
  pass, so UTF-8 / IDN paths are unaffected.
- **Credential replay across origins on redirect.** `-H 'Authorization: …'`
  (and `Cookie`, `Proxy-Authorization`) was re-sent verbatim to whatever host a
  `Location:` named, so any site whirl was given a credential for could harvest
  it by redirecting to a host it controls. Redirects that change scheme, host
  (case-insensitively) or port now drop credential headers. Same-origin hops and
  non-redirect requests keep them — verified both ways.

### Fixed — silent wrong results
- **A truncated transfer no longer reports success.** Both read loops folded
  `n < 0` into the same branch as `n == 0`, so a timeout, RST or full buffer was
  indistinguishable from a clean close: whirl wrote a short file and exited 0.
  The loops now separate the two, and — more importantly — **every** response is
  checked against its `Content-Length`, since a server that sends a short body
  and then closes *cleanly* is the most common truncation of all and no
  error-flag scheme would catch it. `HEAD`, 204 and 304 are correctly exempt.
- **Response cap 256 KB → 1 MiB, and exceeding it is now an error.** This is the
  root cause of the reported `whirl -L https://github.com` → `malformed chunked
  body` (exit 9): github.com's 575 KB chunked body was cut mid-chunk at 256 KB,
  and the dechunker reported the *symptom*. Now returns the full 574,917-byte
  body, exit 0; a body over the new cap fails loudly instead of silently.
- **`-r` wrote raw chunk framing to disk.** The crawl saved `rbuf` verbatim with
  no dechunking, so every chunked resource was mirrored corrupt (`5\r\nHELLO…`)
  — and link extraction then ran over the corrupt bytes. It now decodes first,
  clamps to `Content-Length`, and extracts links from the decoded body.
- **`-r` mirrored error pages as though they were the resource.** A 404 or 500
  body was written under the requested name. Non-2xx is now skipped and reported.
- **A failed `-o` write exited 0.** `output_write`'s error return was discarded
  at every call site in `_emit_body`. Now checked; a write failure exits 9.
- **`-d @missing-file` silently became a bodyless GET** with exit 0, and
  **`-d @file` over the cap was truncated and sent under a `Content-Length` that
  matched the truncated length** — so the server stored a short body and both
  ends reported success. Both are now hard errors (exit 2) with distinct
  messages; the body cap is 1 MiB with one byte of read headroom to tell "full"
  from "too large".
- **`-L` now follows a relative `Location:`.** RFC 9110 permits one and real
  sites send bare `/docs/`; `url_parse` rejects a schemeless URL, so `-L`
  silently stopped following and exited 0 with the redirect stub as the result.
  Relative, root-relative and protocol-relative forms all resolve now — and the
  resolver **keeps the port**, which the existing `_resolve_link` drops.

### Hardening
- **`taar_tcp_send` partial writes.** The return was discarded and never looped,
  though both backends document a short write (`sock_send`#48 on agnos returns
  "bytes sent (≤ len)"). Now a bounded send-all that tolerates a transient `0`
  with a spin cap, matching taar's own `_taar_dns_tcp_send_all`. The TLS path
  was already correct — `tls_write` / `tls_native_write` send-all internally —
  so only its return code is checked, not re-looped.

### CI
- **CI now compiles and selects the AGNOS arm.** There was no `--agnos` step, so
  a hard break inside an agnos-only block landed green: lint, the Linux build,
  the ELF check and `cyrius test` all pass without ever touching it (`cyrius
  test` builds a host binary, so every assertion runs the Linux arm). The step
  builds with the same `CYRIUS_DCE=1` flags as the Linux build and `cmp`s the
  two images — identical output means the `#ifdef` arm was not taken and fails
  the job. Proves compilation and selection only; nothing executes it.
- **CI runs the new behavioral suite** against the built binary, so a regression
  in any of this release's security fixes fails the job rather than shipping.

### Tests
- **New `tests/behavior.py` — an end-to-end behavioral suite, now checked in and
  gated in CI.** `tests/whirl.tcyr` covers pure logic, so none of the defects
  above were reachable from it: they live in the interaction between the CLI,
  the transport and the filesystem, and need a real binary with a real working
  directory and a server that answers adversarially. Every fix in this release
  is asserted there.
  - Run standalone (`python3 tests/behavior.py build/whirl`) it checks the 12
    assertions that must hold for the build to ship — and it has teeth: run
    against the 0.6.5 binary, 7 of the 12 fail and it exits 1.
  - Run with `--baseline <pre-0.6.6 binary>` each security check becomes a
    **paired** test that first reproduces the defect on the old binary (19
    checks). A failed control then means the check has stopped exercising the
    vulnerable path — a silent false pass — rather than a broken build.
  - Python because Cyrius has no test-harness/scripting spinoff yet; it should
    move over when one exists. Nothing in it needs Python specifically.
- **52 → 69 assertions** in `tests/whirl.tcyr`. New groups:
  `url-reject-injection` (CRLF, LF, tab and space refused in host and path;
  ordinary and percent-encoded URLs still accepted, so the check cannot
  over-reject) and `credential-headers` (case-insensitive matching,
  non-credentials not matched, and short/empty header lines that must not
  overrun).
- `tests/whirl.tcyr` now exits via `syscall(SYS_EXIT, …)` rather than a bare
  `syscall(60, …)`, matching the project idiom.

### Known latent (found and confirmed, deliberately not fixed here)
- The crawl has no **scheme** confinement: an `https` crawl follows same-host
  `http://` links over cleartext. Same-host is enforced; same-scheme is not.
- `robots.txt` is fetched from port 80/443 rather than the port being crawled,
  and relative links lose a non-default `:port` — `-r` is effectively unusable
  against a non-default port. `_resolve_link` needs the `_authority` treatment
  this release gave `_abs_location`.
- `_save_tree` follows symlinks and truncates pre-existing files (`O_CREAT|O_TRUNC`).
- `http_build_request` truncates an oversized request silently; no caller can
  detect it. `_http_puts` clamps at `bufmax` and returns as if it wrote.
- `_agnos_ca_hook` allocates 1 MiB per TLS connect and never reclaims it (bump
  allocator), and probes only `/etc/ssl/cert.pem`. It may also now be redundant
  — cyrius v6.2.23 fixed the `set_ca_system` agnos ABI it works around — but
  removing it needs a run on real agnos.
- `alloc()` failure is unchecked at every call site in `src/`.
- `transport_fetch` and `transport_fetch_tls` remain near-duplicates; this
  release had to fix the same read-loop bug in both.

### Not validated here
- **AGNOS runtime.** The new CI step and the local `--agnos` build are
  **compile-only**. Several fixes touch code paths shared with the agnos arm
  (`transport.cyr`'s read loops and send-all, `output.cyr`'s callers); a QEMU
  smoke against a re-staged 0.6.6 rootfs is still owed, and iron on archaemenid
  remains open.
- The behavioral suite runs against local test servers over plain HTTP; the
  fixes are transport-agnostic, but the TLS arm was exercised only by live
  `https://example.com` / `https://github.com` fetches and a fail-closed check
  against a local self-signed server.

## [0.6.5] — 2026-08-26 (toolchain 6.5.35; taar 0.5.0; vendored stdlib re-cut)

Housekeeping cut: toolchain, substrate and vendored stdlib all move to the
family-current versions. **No transport, HTTP or CLI logic changed** — the only
source edit is the default User-Agent string. Both targets build, the suite is
green, and the Linux binary drops ~86%.

### Changed
- **Toolchain pin `6.4.25` → `6.5.35`** — realigns with the family (`yo` and
  `taar` are both on 6.5.35) and clears the `manifest-pin: 6.4.25 (drift —
  wrapper is 6.5.35)` warning the local toolchain has been emitting. Required
  **zero** source changes: `src/` builds untouched on both targets. Note this is
  a deliberate, substantively-motivated bump, not drift-chasing — the 6.2.6 →
  6.4.25 move at 0.6.3 set the same precedent.
- **`[deps.taar]` `0.3.1` → `0.5.0`.** The load-bearing dep edit: `path =
  "../taar"` wins locally, so local builds were already on 0.5.0 while **CI —
  which has no `../taar` sibling — was still resolving 0.3.1**. What the shipped
  artifact gains:
  - **Fail-closed DNS query-ID entropy.** taar 0.3.1's Linux
    `_taar_plat_random_u16` opened `/dev/urandom` and *discarded the read
    result*, so a short or failed read left the query ID as uninitialised stack
    (RFC 5452). 0.5.0 zero-inits, uses `sys_getrandom`, checks the count, and
    fails the resolve rather than querying with a guessable ID. whirl hits this
    on every hostname fetch (`src/transport.cyr` `transport_fetch` /
    `transport_fetch_tls`).
  - RFC 5452 reply acceptance, TC→TCP-53 fallback (from taar 0.4.0), empty-host
    rejection, and an IPv4-literal fast path that skips DNS entirely.
  - Linux socket primitives moved off hardcoded x86_64 syscall numbers onto
    arch-dispatched `sys_*` wrappers (`sys_openat` in place of x86-only
    `open(2)`) — aarch64 correctness for free.
- **Default User-Agent `whirl/0.5.3` → `whirl/0.6.5`** (`src/http.cyr`). It had
  been stale since 0.5.3 and misreported the version on the wire. `-A` /
  `--user-agent` still overrides it; no test asserts the value.
- **Vendored stdlib snapshot re-cut against 6.5.35.** `lib/` was rebuilt from
  scratch (`rm -rf lib && cyrius lib sync && cyrius deps`) rather than overlaid,
  which prunes 37 undeclared modules that had accumulated from the 6.2.x era —
  including `lib/agnosys.cyr`, which exists in no 6.4.x or 6.5.x snapshot at
  all. `cyrius.lock` 98 → 61 entries; the `./lib/ shadows version-pinned …`
  warning (9 stale modules: `sandhi`, `mabda`, `sankoch`, `patra`, `yukti`,
  `vani`, `sakshi`, `ganita`, `niyama`) is gone. `lib/` is gitignored, so only
  the lock appears in the diff.

### Fixed (inherited from the toolchain, no whirl code change)
- **Silent HTTPS body truncation on the `tls_native` backend.** 6.4.25's
  `tls_native_read` returned `TLS_ERR_BUFFER_FULL` — a *negative* — when a
  decrypted record exceeded the caller's remaining buffer. whirl's read loop
  treats any `n <= 0` as clean EOF (`src/transport.cyr`), so a truncated body
  was reported as a **successful** fetch. Reachable as the 256 KB response cap
  fills and the remaining ask drops below one 16 KB record. 6.5.35 adds a ctx
  read-hold (`TLS_CTX_OFF_READ_HOLD*`) and returns a partial read instead.
  Applies wherever `tls_native` is the active backend — the AGNOS path always
  (it calls `tls_native_*` directly since 0.6.3), and the Linux path whenever
  libssl.so.3 is absent and the facade falls back to native.

### Performance
- **Linux binary 13,935,360 → 2,013,744 bytes (−85.6%)**; static data
  12,980,976 → 726,752 (−94.4%). AGNOS binary 2,002,352 bytes. Attributed to
  the **toolchain pin alone**, verified by experiment: holding `lib/` and
  `cyrius.lock` fixed at the 0.6.4 snapshot and changing only the pin reproduces
  2,013,744 bytes exactly. The `lib/` prune is hygiene, not the cause.

### Validated
- `cyrius build` (Linux) and `cyrius build --agnos` both `OK`; the two images
  differ, so the `#ifdef CYRIUS_TARGET_AGNOS` arm is genuinely taken.
- `cyrius test` → **52 passed, 0 failed** (13 groups: url, http framing, links,
  path-normalize).
- Live over the new stack: `http://example.com` and `https://example.com` both
  return `HTTP/1.1 200 OK`, exit 0.
- **TLS still fails closed**: a *reachable* local `openssl s_server` presenting a
  self-signed cert on `127.0.0.1:18443` is rejected (exit 9), while
  `https://example.com` succeeds. (The usual `*.badssl.com` probes are not
  reachable from this network — a valid-cert control against `badssl.com` also
  fails — so they were not used as evidence.)

### Not validated here
- **AGNOS runtime.** Both `--agnos` results above are **compile-only**; the
  `#ifdef CYRIUS_TARGET_AGNOS` arms are not executed. The QEMU smoke needs a
  re-run against a re-staged 0.6.5 `rootfs/bin/whirl`.
- **CI on a fresh checkout.** Every local build resolves taar through
  `path = "../taar"`; only a real CI run exercises the `git`+`tag` path this
  release fixes.
- **taar's TC→TCP-53 fallback on AGNOS** — no executed coverage anywhere; the
  QEMU smoke will not reach it (example.com's A RRset never sets TC).
- **Iron on archaemenid** — still open, unchanged by this cut.

### Known latent (found while verifying; deliberately not fixed here)
- **CI never compiles the AGNOS arm.** `.github/workflows/` has no `--agnos`
  step, so a hard break inside an agnos-only block lands green. `yo` gates this;
  whirl should adopt it in its own commit.
- `transport_fetch`'s `taar_tcp_send(fd, req, reqlen)` discards the return and
  never loops on a partial write. Reachable with a large `-d @file` body; real
  exposure is the AGNOS backend (`sock_send`#48 may accept `< len`). The TLS
  path is unaffected — `tls_write` / `tls_native_write` already send-all.
- `_agnos_ca_hook` (`src/transport.cyr`) may now be redundant: the upstream
  `tls_native_set_ca_system` agnos-ABI defect it works around was fixed at
  cyrius v6.2.23 and that fix is in the vendored snapshot. Needs its own
  investigation on real agnos before removal.
- `-L https://github.com` fails with `whirl: malformed chunked body` (exit 9) on
  both a taar-0.3.1 baseline and this build — pre-existing, unrelated.

## [0.6.4] — 2026-07-08 (validation re-cut — HTTPS confirmed under mirshi)

### Validated
- **HTTPS under mirshi confirmed working** — no whirl code change vs 0.6.3. The transient
  HTTPS-under-mirshi segfault seen during 0.6.3 bring-up was root-caused to a NULL-deref in
  the **stale pre-6.4.25 sigil** snapshot whirl's old vendored `lib/` carried (heap
  crypto-scratch `mmap` returned 0, zeroed unchecked → SIGSEGV `faultaddr=0`). The 6.4.25
  sigil (static crypto banks) already fixes it. Confirmed: whirl HTTPS fetches over **both**
  mirshi (`--root <ca> --net-allow`) and the real agnos kernel. No mirshi patch / cyrius
  issue required.

## [0.6.3] — 2026-07-08 (AGNOS build under cyrius 6.4.x — fdlopen → tls_native; toolchain 6.4.25)

### Changed
- **Toolchain pin `6.2.6` → `6.4.25`** (latest cyrius). Clears the stale-pin drift; the
  build fix below is mandated by 6.4.x's stricter reachable-undef gate — 6.2.6 tolerated
  the unreachable `fdlopen_*` refs, 6.4.x refuses to emit a binary with them.
- **stdlib list gains `dynlib` + `fdlopen`.** cyrius 6.4.x resolves the `tls` facade's
  libssl.so.3-bridge `fdlopen_*` refs from the explicit include list (no longer
  auto-pulled via tls's transitive requires), so the **Linux** build needs them named or
  it fails reachable-undef. On `--agnos` they compile (Linux path is
  `#ifdef CYRIUS_TARGET_LINUX`-gated) and stay unreachable (native TLS path) → DCE'd.

### Fixed — AGNOS build under cyrius 6.4.x (fdlopen reachable-undef)
- **`cyrius build --agnos` no longer fails on `fdlopen_*` reachable-undef.** On the
  6.4.x toolchain the `lib/tls.cyr` facade's `tls_connect*` verbs pull in
  `tls_connect_alloc → _tls_init → fdlopen_init_full` — the libssl.so.3 dynamic-loader
  bridge (fdlopen bootstraps ld.so to `dlopen` glibc). AGNOS binaries are STATIC (no
  ld.so, no fdlopen), so those symbols were both unbuildable (`refusing to emit binary
  with 4 reachable undefined function(s)`) and structurally unusable. The agnos HTTPS
  path now calls the sovereign `tls_native_*` API directly (`_agnos_tls_native_connect`:
  `tls_native_new_client` → CA roots via the agnos-ABI `_agnos_ca_hook` →
  `tls_native_connect`, chain+hostname fail-closed), returning a native-backed shim so
  the shared `tls_read/write/close` still drive it. fdlopen is now unreachable on
  `--agnos` and DCE-eliminated; the Linux path is byte-identical (all changes are
  `#ifdef CYRIUS_TARGET_AGNOS`-guarded). Rounds out the net-tools (yo + dig) in the
  agnos-dev docker image.

### Validated on AGNOS (QEMU + KVM real kernel, virtio-net + SLIRP)
- **HTTP and HTTPS both PASS** with the rebuilt binary — `whirl https://example.com`
  fetched the real Example Domain page (tls_native over taar, cert-verified) over the
  sovereign stack. Also runs under mirshi (`--net-allow`): HTTP over the emulated net
  band PASS. (HTTPS *under mirshi* segfaults inside cyrius `tls_native_connect` — a
  mirshi net-band emulation gap, NOT a whirl issue; the identical binary does HTTPS
  fine on the real kernel.)

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
