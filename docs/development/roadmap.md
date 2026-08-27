# whirl — Roadmap

> Milestone path from scaffold (0.1.0) through v1.0 (curl+wget feature parity for the common cases + HTTPS + AGNOS-native backend). Shape: **Completed** / **Backlog** / **Future** / **v1.0 criteria** + the **AGNOS call surface** (the syscalls/peer functions whirl's agnos backend binds — the "calls to lock down" so the language agent can wire the cyrius side).

## Completed

### 0.1.0 — scaffold (2026-06-18)

- [x] Repo skeleton mirroring the network-tools family (`yo` / `dig` / `taar`): `cyrius.cyml` (pin 6.2.6), `VERSION`, `LICENSE`, `README.md`, `CLAUDE.md`, `.gitignore`.
- [x] CI + release workflows on the upstream `install.sh` toolchain pattern from day one (no hand-rolled curl+cp — avoids the `cyrius deps` pin-check failure dig/yo hit).
- [x] Compilable `src/main.cyr` stub (usage; transport WIP) + `src/test.cyr`.
- [x] This roadmap + `state.md`.

## Backlog — path to v1.0

Ordered by dependency.

### 0.2.0 — HTTP/1.1 GET MVP ✅ (2026-06-18, over taar)

Transport went **raw-syscall over the taar substrate** — *not* stdlib `net`, which
needs the heavy `agnosys`/`async`/`tls`/`ws` tree the lean family avoids. No whirl
platform split: taar's `socket` + `dns` modules (driven by this work) abstract it.

- [x] `src/url.cyr` — http/https URL parse (scheme / host / port / path; rejects bad scheme / empty host / port > 65535).
- [x] `src/cli.cyr` — `<url>`, `-o FILE`, `-L` (follow redirects), `-h`/`--help`.
- [x] `src/http.cyr` — request build + status / header (case-insensitive) / body-offset / Content-Length / chunked decode.
- [x] `src/transport.cyr` — resolve (`taar_resolve_ipv4`) + TCP (`taar_tcp_*`) with a recv timeout. *(TLS wrap → the HTTPS tail below.)*
- [x] `src/output.cyr` — body → stdout or `-o FILE` (`file_write_all`).
- [x] `[deps.taar]` 0.2.0 (socket + dns). *(No whirl platform split; stdlib `net` dropped; `tls_native`/`sigil` arrive with HTTPS.)*
- [x] `tests/whirl.tcyr` — URL + HTTP framing (**31 asserts**). Live fetch validated against neverssl.com.

### 0.3.0 — HTTPS + redirect UX ✅ (2026-06-18)
- [x] HTTPS via stdlib `tls_connect`/`tls_read`/`tls_write`/`tls_close` over taar's TCP socket (`transport_fetch_tls`). tls_native's default raw read/write on the fd — no callback wiring on Linux. Cert chain + hostname verified **fail-closed** (CVE-18; `expired.badssl.com` rejected).
- [x] `main.cyr` routes `https://` + https redirect targets (`-L`).
- [x] **Opt-in** crypto/TLS libs (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls`) via `cyrius lib sync` — wired into CI. *(The libssl/`fdlopen` fallback DCE's out → sovereign tls_native path.)*
- [x] Redirect UX: bare 3xx without `-L` prints `whirl: <code> redirect -> <loc> (use -L to follow)` to stderr; stdout stays clean.
- [ ] *Follow-up:* AGNOS socket backend (taar `#ifdef`) + tls_native `set_transport(read, write, now)` over taar's agnos socket — tracked in CHANGELOG "Still ahead".

### 0.4.0 — methods + bodies ✅ (2026-06-18)
- [x] `-d DATA` (POST, `Content-Type` default `application/x-www-form-urlencoded` + `Content-Length`), `-X METHOD` (arbitrary), `-H 'Header: val'` (repeatable; caller `Content-Type` overrides). Live-validated over HTTPS (postman-echo). Redirects follow as GET (body dropped).
- [x] **0.5.3:** `--data-binary` (raw body), stdin/file body (`-d @-` / `-d @file`).

### 0.5.0 — the wget side ✅ (2026-06-18)
- [x] `-O` (filename derived from the URL path; `url_filename`), `--retry N` (linear backoff).
- [x] `-r` recursive fetch (`-l N` depth) — `src/links.cyr` href/src extraction + same-host crawl (resolve absolute/root-relative/relative, dedup, 64-fetch cap, flat-file save). Live-validated on info.cern.ch (multi-resource, cross-host filtered).
- [x] **0.5.1:** directory-tree mirroring + `../` normalization + robots.txt (+ protocol-relative `//host` resolution). Live-validated.
- [x] **0.5.2:** resume (`-C`) — `Range: bytes=N-` request, 206-append / 200-overwrite / 416-complete. Live-validated.

### 0.5.3 — polish ✅ (2026-06-18)
- [x] `-A`/`--user-agent` (UA override), `-i` (include response headers), `-I` (HEAD), `-f` (fail on HTTP ≥ 400 → exit 22), `-d @file`/`-d @-` + `--data-binary` (file/stdin body).
- [x] robots.txt `Allow:` precedence — RFC 9309 longest-match (tie → Allow). Proven live on en.wikipedia.org (`/w/load.php?` allowed vs `/w/` disallowed).

### 0.6.0 — HTTP on AGNOS ✅ (2026-06-18)
- [x] `[deps.taar]` → **0.3.0** (sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45 backend). `transport_fetch` rides it unchanged.
- [x] Portable I/O: `sys_write`/`sys_read`/chrono `sleep_ms`/`file_read_all`; `#ifdef` only for `sys_mkdir`/`sys_stat`/agnos `-C` append. The whole tool compiles + behaves on **both** Linux and `CYRIUS_TARGET_AGNOS=1`.

### 0.6.1 — HTTPS on AGNOS ✅ (2026-06-18)
- [x] `tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)` in `transport_fetch_tls` under `#ifdef CYRIUS_TARGET_AGNOS` — taar's recv/send become tls_native's transport vtable (v6.2.4 hook); `now_fn=0` keeps the agnos `sys_time_unix`#46 cert clock. Fail-closed cert+hostname verify unchanged. Compiles clean both targets; Linux HTTPS untouched.

### 0.6.2 — AGNOS validation (QEMU) ✅ + iron next
- [x] **QEMU + KVM (virtio-net + SLIRP)**: whirl execs from disk + fetches real example.com over the sovereign stack — **HTTP and HTTPS both PASS** (`agnos/scripts/whirl-smoke.sh`). HTTPS cert-verified.
- [x] Fixed HTTPS-on-agnos: `_agnos_ca_hook` loads the staged CA bundle with the correct agnos `sys_open` ABI (cyrius `tls_native_set_ca_system` uses the Linux ABI — issue filed). CA staging wired into `stage-tools.sh`.
- [ ] **Iron** on archaemenid: same run over the r8169 NIC. Parity benchmark vs `curl` (latency / RSS / binary size).

### 0.6.3 — AGNOS off the libssl bridge ✅ (2026-07-08)
- [x] Toolchain pin 6.2.6 → 6.4.25; stdlib list gains `dynlib` + `fdlopen` (the `tls` facade's `fdlopen_*` refs must be named explicitly or the Linux build fails reachable-undef).
- [x] agnos HTTPS calls `tls_native_*` **directly** (`_agnos_tls_native_connect`) instead of the `tls.cyr` facade — agnos binaries are static, so `ld.so`/`fdlopen` is both unbuildable and structurally unusable. Linux path byte-identical. HTTP + HTTPS re-validated on QEMU.

### 0.6.4 — validation re-cut ✅ (2026-07-08)
- [x] HTTPS under mirshi confirmed working; the transient 0.6.3 segfault root-caused to a stale pre-6.4.25 `sigil` snapshot, not a whirl or mirshi defect. No code change.

### 0.6.5 — toolchain + substrate re-cut ✅ (2026-08-26)
- [x] Pin 6.4.25 → **6.5.35**; `[deps.taar]` 0.3.1 → **0.5.0** (CI had been resolving the old tag — `path = "../taar"` only wins locally). Fail-closed DNS query-ID entropy; TC→TCP-53 fallback; arch-dispatched `sys_*` wrappers.
- [x] Vendored stdlib re-cut from scratch — 37 undeclared 6.2.x-era modules pruned (incl. the orphan `agnosys.cyr`); lock 98 → 61.
- [x] Inherited fix: `tls_native_read` no longer returns `TLS_ERR_BUFFER_FULL` for an over-length record (whirl read it as clean EOF → silent body truncation reported as success).
- [x] Linux binary 13.9 MB → 2.0 MB (−85.6%), attributable to the pin alone. Default UA `whirl/0.5.3` → `whirl/0.6.5`.
- [ ] *Follow-up:* add a `cyrius build --agnos` step to CI — the AGNOS arm is currently never compiled there.

## v1.0 criteria
- [x] GET + POST + arbitrary methods + custom headers; redirects; chunked; HTTPS with cert verification — shipped 0.3.0–0.5.3, fail-closed verify proven against a reachable bad-cert server.
- [x] **No POSIX `socket()`** anywhere in the AGNOS backend — sovereign syscalls only. The agnos arm binds `sock_*`#47-50 / `udp_*`#51-54 exclusively.
- [ ] AGNOS backend resolves + fetches `https://` end-to-end (DNS → TCP → TLS → HTTP) — **QEMU-validated at 0.6.2**; the remaining half is **iron** on archaemenid.
- [ ] Consumes `taar` — `tcp` shipped at taar 0.2.0 and whirl runs on it; `tls` / `http` modules are still unwritten. No network primitives vendored locally either way.

---

## AGNOS call surface (the calls to lock down)

whirl's AGNOS arm binds **only** the calls below. Unlike dig/yo there is **no `platform_agnos.cyr`** — the dispatch is inline `#ifdef CYRIUS_TARGET_AGNOS` in `src/transport.cyr`, `src/main.cyr` and `src/output.cyr`. **The kernel half of every call landed**, and the cyrius-side wiring landed too: composed at 0.6.1, proven end-to-end on QEMU at **0.6.2**, and rebuilt onto the direct `tls_native_*` path at 0.6.3.

| Need | AGNOS kernel syscall | Status (kernel) | cyrius peer |
|---|---|---|---|
| TCP connect | `sock_connect`#47 (dst_ip, dst_port, src_port) → conn_id | ✅ landed agnos 1.45.1 | `net.cyr sock_connect` — client band wired v6.2.3 |
| TCP send | `sock_send`#48 (conn_id, buf, len) | ✅ 1.45.1 | `net.cyr sock_send` ✅ |
| TCP recv | `sock_recv`#49 (conn_id, buf, max) non-blocking, WOULD_BLOCK/EOF split | ✅ 1.45.1 | `net.cyr sock_recv` ✅ |
| TCP close | `sock_close`#50 (conn_id) | ✅ 1.45.1 | `net.cyr sock_close` ✅ |
| TLS (HTTPS) | *(none — runs over the TCP calls)* | n/a | **`tls_native` is transport-agnostic**: `tls_native_set_transport(read_fn, write_fn, now_fn)` → wire read/write to `sock_recv`#49 / `sock_send`#48, `now` to `uptime_ms`#40; then `tls_native_connect` / `tls_native_write` / `tls_native_read` / `tls_native_close` + `tls_native_client_verify_hostname`. Client TLS peer wired v6.2.3. |
| TLS / nonce entropy | `getrandom`#45 (buf, len, flags) — Zen RDRAND | ✅ landed agnos 1.45.0 | `random.cyr` / `SYS_GETRANDOM=45` ✅ |
| DNS resolve | UDP-53 `udp_bind`#51 / `udp_send`#52 / `udp_recv`#53 / `udp_unbind`#54 | ✅ landed agnos 1.45.3 | `taar.dns` (to grow) over the UDP wrappers; dig already drives this path |
| Monotonic clock / sleep | `uptime_ms`#40 / `sleep_ms`#41 | ✅ landed | `sys_uptime_ms` / `sys_sleep_ms` wrappers (cyrius ≥ 6.2.6) ✅ |
| Kernel-leased resolver | `net_config`#61 field 3 (DHCP option-6 nameserver) | ✅ landed agnos 1.45.16 | `sys_net_dns_server()` wrapper ✅ — reached via `taar_resolve_ipv4` → `_taar_resolv_discover`, tried **before** `/etc/resolv.conf`. Hard dependency since 0.6.2: the off-subnet `8.8.8.8` fallback needs gateway routing the kernel can't guarantee on iron. |

**Net:** whirl needed **zero new kernel syscalls**, and the lock-down is closed. Composing `tls_native` over the agnos socket transport for the server-cert-verifying HTTPS client — the one genuinely new cyrius-side item — landed at 0.6.1 and was proven end-to-end on QEMU at 0.6.2 (0.6.2 also corrected 0.6.1's premature "correct-by-construction" claim). What remains is **not** transport composition:

- **Iron validation** on archaemenid (above) — the only open item on the critical path.
- **taar's `tls` / `http` modules**, still unwritten.
- Whether `_agnos_ca_hook` is now redundant, given cyrius v6.2.23 fixed the `tls_native_set_ca_system` agnos-ABI defect it works around. Needs a run on real agnos, not a code read.

> Cross-refs: [agnos net-syscall arc](https://github.com/MacCracken/agnosticos/blob/main/docs/development/state.md) (#45-#57) · [taar](https://github.com/MacCracken/taar) (substrate) · [dig `platform_agnos.cyr`](https://github.com/MacCracken/dig) (the UDP backend pattern to mirror for TCP).
