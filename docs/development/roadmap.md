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

### 0.2.x tail — HTTPS (next)
- [ ] `tls_native` wrap over the taar socket for `https://` (transport-agnostic `tls_native_set_transport(read, write, now)` over `taar_tcp_send`/`taar_tcp_recv`). Adds stdlib `tls_native` + `sigil`.

### 0.3.x — methods + bodies
- [ ] `-d DATA` (POST, `Content-Type` default `application/x-www-form-urlencoded`), `-X METHOD` (arbitrary), `-H 'Header: val'` (custom headers), `--data-binary`, stdin body (`-d @-`).

### 0.4.x — the wget side
- [ ] `-r` recursive fetch (link extraction, same-host bound, depth limit), `-O`/auto filename-from-URL, resume (`-C`), retry/backoff.

### 0.5.x — iron validation + parity
- [ ] First AGNOS run on archaemenid: `whirl https://example.com` over the sovereign backend. Parity benchmark vs `curl` (latency / RSS / binary size).

## v1.0 criteria
- [ ] GET + POST + arbitrary methods + custom headers; redirects; chunked; HTTPS with cert verification (`tls_native_client_verify_hostname`).
- [ ] **No POSIX `socket()`** anywhere in the AGNOS backend — sovereign syscalls only.
- [ ] AGNOS backend resolves + fetches `https://` end-to-end (DNS → TCP → TLS → HTTP), iron-validated.
- [ ] Consumes `taar` (`tcp` / `tls` / `http` modules added by whirl) — no network primitives vendored locally.

---

## AGNOS call surface (the calls to lock down)

whirl's `platform_agnos.cyr` binds **only** the calls below. **The kernel half of every one already landed** — the remaining work is the cyrius-side `CYRIUS_TARGET_AGNOS` wiring (the language agent's job; mirrors the dig/yo client-band peer at cyrius 6.2.3+).

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

**Net:** whirl needs **zero new kernel syscalls** — every call is already exposed and (for the client band) already wired in the cyrius peer. The only genuinely new cyrius-side work is composing `tls_native` over the agnos socket transport for the **server-cert-verifying HTTPS client** path, which the dig/yo client-band peer already proved transport-side. This is the lock-down: when the transport src lands, the language agent confirms `tls_native` builds + verifies for `CYRIUS_TARGET_AGNOS` and whirl's `https://` fetch runs end-to-end.

> Cross-refs: [agnos net-syscall arc](https://github.com/MacCracken/agnosticos/blob/main/docs/development/state.md) (#45-#57) · [taar](https://github.com/MacCracken/taar) (substrate) · [dig `platform_agnos.cyr`](https://github.com/MacCracken/dig) (the UDP backend pattern to mirror for TCP).
