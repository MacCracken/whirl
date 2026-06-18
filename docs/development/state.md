# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-06-18 (0.1.0 scaffold cut).

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.1.0** (scaffold — skeleton + manifest + CI/release + docs; transport WIP) |
| Status | Scaffold. `src/main.cyr` is a usage stub that compiles + runs; HTTP/1.1 + TLS transport is the next bite. |
| Module footprint | `src/main.cyr` (stub) + `src/test.cyr`. Transport modules (url / cli / http / transport / output / platform_linux / platform_agnos) land in 0.2.x. |
| Cyrius pin | 6.2.6 (family-aligned with yo / dig / taar) |
| Backends | none functional yet. Per-backend split (Linux POSIX / AGNOS sovereign) lands with the transport bite. |
| Tests | `src/test.cyr` entry only; `tests/whirl.tcyr` unit suite lands with the transport bite. |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — adds taar's `tcp` / `tls` / `http` modules. |
| Deps | stdlib base only at 0.1.0; `[deps.taar]` + `net` / `tls_native` / `sigil` added with the transport bite (see roadmap § AGNOS call surface). |

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
