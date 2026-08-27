# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-08-27 (0.6.6 — P-1 security + correctness sweep: remote arbitrary file write via `-r`, request splitting via `Location`, cross-origin credential replay, and silent truncation all fixed. CI now compiles the AGNOS arm. Iron on archaemenid still the open validation step.)

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.6.6** (HTTP/1.1 + HTTPS; GET/POST/methods + headers + `-A` UA; `-i`/`-I`/`-f`; **`-r` recursive** w/ tree-mirroring + robots.txt `Allow`/`Disallow` precedence, `-O`, `-C` **resume**, `--retry` — over the taar transport; **HTTP + HTTPS both run on AGNOS**, QEMU-validated at 0.6.2, rebuilt at 0.6.3 onto the sovereign `tls_native_*` path) |
| Status | Working. `whirl [-X M] [-d DATA\|@file\|@-] [--data-binary D] [-H 'H: v'] [-A UA] [-i] [-I] [-f] [-r [-l N]] [-O\|-o FILE] [-C] [-L] [--retry N] http(s)://…` — resolve + connect (+ TLS) + request + emit/save; redirects (`-L`); recursive same-host crawl (`-r`); cert chain + hostname verified fail-closed. |
| Module footprint | `src/{url,http,cli,transport,output,links,main}.cyr` (+ `test.cyr`) — 8 modules, 1,529 lines. url / http / links / path-normalize pure-tested; transport rides taar (TCP+DNS), with TLS for https. |
| Cyrius pin | **6.5.35** (family-aligned with yo + taar; `dig` is the outlier at 6.2.24) |
| Backends | **Linux** (raw-syscall TCP via taar; the `tls.cyr` facade for TLS) + **AGNOS** (taar's sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45 backend, landed at taar 0.3.0; whirl I/O portable via `sys_write`/`sys_read`/chrono/io + `#ifdef` for mkdir/stat/append). HTTP + HTTPS both **QEMU-validated on agnos** at 0.6.2; since 0.6.3 the agnos handshake calls `tls_native_*` **directly** (`_agnos_tls_native_connect`) rather than the facade's `tls_connect`, because agnos binaries are static and cannot use the libssl/`fdlopen` bridge. `tls_read`/`tls_write`/`tls_close` are shared by both targets. **`net` is not in the `[deps].stdlib` include list** — the transport is sovereign. |
| Tests | `tests/whirl.tcyr` → **69 assertions** across 15 groups (URL parse + injection rejection, HTTP framing, credential-header matching, links extraction, path normalization). Plus a **17-check paired behavioral suite** run out-of-tree against local servers: each 0.6.6 fix is proven by reproducing the defect on the prior binary first. Live: `http://example.com` + `https://example.com` fetch, `-L https://github.com` (575 KB chunked), reachable self-signed cert rejected fail-closed (exit 9). |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — drove taar's `socket` + `dns` modules (taar 0.2.0); `tls`/`http` module growth still open. |
| Deps | stdlib base + **`[deps.taar]` 0.5.0** + the **opt-in crypto/TLS libs** (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls` plus `dynlib`/`fdlopen` since 0.6.3, vendored via `cyrius lib sync` — wired into CI). No stdlib `net`/`sandhi`. `lib/` is gitignored; `cyrius.lock` (61 entries) is the committed record. |
| Response cap | **1 MiB** (`WHIRL_RBUF_SZ`) for both the response buffer and a `-d @file` request body. Exceeding it is a reported error, never a silent truncation. |
| Floors | **agnos ≥ 1.45.16** (0.6.2's kernel-leased resolver, `net_config`#61) · **taar ≥ 0.5.0** (fail-closed DNS query-ID entropy) · **cyrius ≥ v5.6.37** for the `dynlib`+`fdlopen` include rule. |

## AGNOS readiness

whirl needs **zero new kernel syscalls** — the full call surface (`sock_*`#47-50, `getrandom`#45, UDP-53 #51-54, `net_config`#61, `uptime_ms`#40/`sleep_ms`#41, `stat`#33/`mkdir`) is landed, and the client band + `tls_native` are wired in the cyrius peer. **0.6.0**: the plain-HTTP path runs on agnos (taar 0.3.0's sovereign backend; `CYRIUS_TARGET_AGNOS=1` compiles the whole tool). **0.6.1**: composed `tls_native` over the taar socket via `tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)` (the agnos TCP "fd" is a sentinel, so the default raw-fd path won't route; `now_fn=0` keeps the `sys_time_unix`#46 cert clock). **0.6.2**: **QEMU-validated** (virtio-net + SLIRP) — real example.com fetched over HTTP *and* HTTPS, which also proved 0.6.1's "correct-by-construction" claim had been wrong; needed `_agnos_ca_hook` for trust roots. **0.6.3**: dropped the `tls.cyr` facade on agnos for direct `tls_native_*` calls (static binaries have no `ld.so`, so `fdlopen` is both unbuildable and unusable). **0.6.4**: confirmed under mirshi. **Iron on archaemenid is the remaining step.** Full table in [`roadmap.md`](roadmap.md) § *AGNOS call surface*.

> **Note (0.6.5):** the cyrius-peer defect `_agnos_ca_hook` works around — `tls_native_set_ca_system` opening the CA bundle with the Linux `sys_open` ABI — was fixed upstream at cyrius v6.2.23, and that fix is in the vendored snapshot. The hook is therefore *likely* redundant now, but removing it needs its own validation run on real agnos. Not part of the 0.6.5 cut.

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| `taar` `tls` / `http` modules | whirl is the consumer that would add them (`tcp` shipped at taar 0.2.0 and whirl runs on it) | whirl + taar |
| Iron validation on archaemenid | hardware run over the r8169 NIC; parity benchmark vs `curl` | whirl + agnos |
| QEMU smoke for 0.6.6 | 0.6.6 changed the shared read/send paths; the AGNOS arm is compile-verified only. Needs a re-staged rootfs. | whirl + agnos |

## Open defects (confirmed, not yet fixed)

Carried from the 0.6.6 audit — see [`../../CHANGELOG.md`](../../CHANGELOG.md) § 0.6.6 *Known latent* for detail.

| Area | Defect |
|---|---|
| `-r` scheme confinement | an `https` crawl follows same-host `http://` links over cleartext |
| `-r` on a non-default port | `robots.txt` fetched from :80/:443, and relative links lose `:port` |
| `_save_tree` | follows symlinks; truncates pre-existing files |
| `http_build_request` | truncates an oversized request silently; callers cannot detect it |
| `_agnos_ca_hook` | 1 MiB leaked per TLS connect; probes only `/etc/ssl/cert.pem`; likely redundant since cyrius v6.2.23 |
| `alloc()` | failure unchecked at every `src/` call site |
| `transport.cyr` | `transport_fetch` / `transport_fetch_tls` remain near-duplicates |

## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
