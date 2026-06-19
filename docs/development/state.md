# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-06-18 (0.6.1 — HTTPS on AGNOS via tls_native set_transport; HTTP+HTTPS both wired for agnos, iron-pending).

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.6.1** (HTTP/1.1 + HTTPS; GET/POST/methods + headers + `-A` UA; `-i`/`-I`/`-f`; **`-r` recursive** w/ tree-mirroring + robots.txt `Allow`/`Disallow` precedence, `-O`, `-C` **resume**, `--retry` — over the taar transport; **HTTP + HTTPS both wired for AGNOS** via taar 0.3.0's sovereign backend + tls_native set_transport) |
| Status | Working. `whirl [-X M] [-d DATA\|@file\|@-] [--data-binary D] [-H 'H: v'] [-A UA] [-i] [-I] [-f] [-r [-l N]] [-O\|-o FILE] [-C] [-L] [--retry N] http(s)://…` — resolve + connect (+ TLS) + request + emit/save; redirects (`-L`); recursive same-host crawl (`-r`); cert chain + hostname verified fail-closed. |
| Module footprint | `src/{url,http,cli,transport,output,main}.cyr` (+ `test.cyr`). url/http pure-tested; transport rides taar (TCP+DNS) + stdlib tls for https. |
| Cyrius pin | 6.2.6 (family-aligned with yo / dig / taar; ≥6.2.3 wires the agnos sock client band) |
| Backends | **Linux** (raw-syscall TCP via taar; tls_native default raw read/write for TLS) + **AGNOS** (taar 0.3.0 sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45; whirl I/O portable via `sys_write`/`sys_read`/chrono/io + `#ifdef` for mkdir/stat/append). HTTP + HTTPS both wired on agnos (HTTPS via `tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)`, 0.6.1). **No `lib/net.cyr`** — sovereign. |
| Tests | `tests/whirl.tcyr` → **31 assertions** (URL parse + HTTP framing); live: `http://neverssl.com` + `https://example.com` fetch, `expired.badssl.com` rejected. |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — drove taar's `socket` + `dns` modules (taar 0.2.0); `tcp`/`tls`/`http` growth continues. |
| Deps | stdlib base + **`[deps.taar]` 0.2.0** (socket + dns) + the **opt-in crypto/TLS libs** (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls`, vendored via `cyrius lib sync` — wired into CI). No stdlib `net`/`sandhi`. |

## AGNOS readiness

whirl needs **zero new kernel syscalls** — the full call surface (`sock_*`#47-50, `getrandom`#45, UDP-53 #51-54, `uptime_ms`#40/`sleep_ms`#41, `stat`#33/`mkdir`) is already landed, and the client band + `tls_native` are wired in the cyrius peer (6.2.3+). **0.6.0**: the plain-HTTP path runs on agnos (taar 0.3.0's sovereign backend; `CYRIUS_TARGET_AGNOS=1` compiles the whole tool). **0.6.1**: the HTTPS-on-agnos path composes `tls_native` over the taar socket via `tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)` (the agnos TCP "fd" is a sentinel, so the default raw-fd path won't route; `now_fn=0` keeps the `sys_time_unix`#46 cert clock). Both compile clean for agnos — **iron validation on archaemenid (0.6.2) is the only remaining step**. Full table in [`roadmap.md`](roadmap.md) § *AGNOS call surface*.

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| `taar` `tcp`/`tls`/`http` modules | whirl is the third consumer that adds them | whirl + taar |
| HTTPS client on agnos | `tls_native` over the socket transport (cyrius peer) | cyrius (language agent) |
| taar dep resolves in CI | taar `0.1.x` tag pushed to GitHub | taar (release) |

## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
