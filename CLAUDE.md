# whirl — Claude Code Instructions

> **Core rule**: this file is **preferences, process, and procedures** — durable
> rules that change rarely. Volatile state (current version, module line counts,
> supported backends, test counts, dep-gap status, consumers) lives in
> [`docs/development/state.md`](docs/development/state.md). Do not inline state here.

## Project Identity

**whirl** — `curl` + `wget` unified into one verb. HTTP / HTTPS / file transfer. English-wordplay naming lane (curl + wget = whirl; *the packet whirls out, the response whirls back*).

- **Type**: Binary (CLI tool)
- **License**: GPL-3.0-only
- **Language**: Cyrius (toolchain pinned in `cyrius.cyml [package].cyrius`)
- **Version**: `VERSION` at the project root is the source of truth — do not inline the number here
- **Genesis repo**: [agnosticos](https://github.com/MacCracken/agnosticos)
- **Standards**: [First-Party Standards](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-standards.md) · [First-Party Documentation](https://github.com/MacCracken/agnosticos/blob/main/docs/development/first-party/first-party-documentation.md)
- **Shared crates**: [shared-crates.md](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)

## Goal

Own the **HTTP/HTTPS transfer surface** in the AGNOS network-tools family: fetch a URL (GET → stdout or file), follow redirects, POST (`-d`), arbitrary methods (`-X`), recursive fetch (`-r`, the wget side) — one tool, combined curl+wget feature set, smart defaults. Cyrius-native, **no POSIX `socket()` on the AGNOS backend** — consumes the kernel's sovereign `sock_*` (#47-50) + `getrandom` (#45) + UDP-53 (#51-54) primitives and `tls_native` for HTTPS, per the kernel-grows-for-native-workloads rule.

**Strategic position — third `taar` consumer.** After `yo` (ICMP) and `dig` (DNS), whirl is the consumer that adds `taar`'s `tcp` / `tls` / `http` modules. taar is already extracted (0.1.0, ipv4 module); whirl drives its socket/tcp/tls/http growth.

## Conventions

- **Per-backend sovereignty**: `src/platform.cyr` `#ifdef CYRIUS_TARGET_AGNOS`-dispatches to `platform_agnos.cyr` (sovereign syscalls) or `platform_linux.cyr` (POSIX). Same shape as yo / dig.
- **No POSIX `socket()` on the AGNOS backend** — the v1.0 gate enforces this.
- **`tls_native` is transport-agnostic**: wire `tls_native_set_transport(read, write, now)` over `sock_send`#48 / `sock_recv`#49 / `uptime_ms`#40 on agnos; over POSIX read/write on Linux.
- **CI/Release toolchain install MUST use the upstream `install.sh`** (reads the `cyrius.cyml [package].cyrius` pin) — never a hand-rolled curl+cp, which fails the `cyrius deps` pin-check (it lays files in a flat `~/.cyrius/lib` instead of `~/.cyrius/versions/<v>/`). patra is the reference.
- **Entry/exit idiom**: `var r = main(); syscall(SYS_EXIT, r);` at top level (same as dig).

## Current State

> Volatile state lives in [`docs/development/state.md`](docs/development/state.md) —
> current version, surface area, in-flight work, consumers, dep gaps.

## DO NOT

- Do not commit or push — the user handles all git operations.
- Do not add POSIX `socket()` to the AGNOS backend.
- Do not bump the `cyrius.cyml` pin to chase drift — it is held on a known-working version.
