# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-06-18 (0.2.0 — HTTP/1.1 GET MVP working over taar).

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.2.0** (HTTP/1.1 GET MVP — fetches real http:// end-to-end over the taar transport) |
| Status | Working. `whirl http://…` resolves + connects + GETs + emits body to stdout / `-o FILE`; redirects (`-L`). HTTPS (TLS) is the next bite. |
| Module footprint | `src/{url,http,cli,transport,output,main}.cyr` (+ `test.cyr`). url/http are pure-tested; transport rides taar. |
| Cyrius pin | 6.2.6 (family-aligned with yo / dig / taar) |
| Backends | Linux (raw-syscall TCP via taar). AGNOS socket backend (taar `#ifdef`) is a follow-up. **No `lib/net.cyr`** — sovereign per-backend posture. |
| Tests | `tests/whirl.tcyr` → **31 assertions** (URL parse + HTTP framing); live fetch validated against neverssl.com. |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — drove taar's `socket` + `dns` modules (0.2.0); `tcp`/`tls`/`http` growth continues. |
| Deps | stdlib base + **`[deps.taar]` 0.2.0** (socket + dns). HTTPS adds `tls_native` + `sigil` next. No stdlib `net`/`sandhi` (the lean per-backend choice). |

## AGNOS readiness

whirl needs **zero new kernel syscalls** — the full call surface (`sock_*`#47-50, `getrandom`#45, UDP-53 #51-54, `uptime_ms`#40/`sleep_ms`#41) is already landed, and the client band + `tls_native` are wired in the cyrius peer (6.2.3+). The HTTPS-on-agnos path is composing `tls_native` over the socket transport — confirmed when the transport src lands. Full table in [`roadmap.md`](roadmap.md) § *AGNOS call surface*.

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| `taar` `tcp`/`tls`/`http` modules | whirl is the third consumer that adds them | whirl + taar |
| HTTPS client on agnos | `tls_native` over the socket transport (cyrius peer) | cyrius (language agent) |
| taar dep resolves in CI | taar `0.1.x` tag pushed to GitHub | taar (release) |

## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
