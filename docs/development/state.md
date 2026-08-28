# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-08-27 (0.6.13). Recent arc: AGNOS revalidated end-to-end
> and at unit level after six releases of compile-only checking, and the 0.6.6
> audit's follow-ups (B1/B3) closed. Per-release detail is in the
> [CHANGELOG](../../CHANGELOG.md) — this file does not repeat it.

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.6.13** (HTTP/1.1 + HTTPS; GET/POST/methods + headers + `-A` UA; `-i`/`-I`/`-f`; **`-r` recursive** w/ tree-mirroring + robots.txt `Allow`/`Disallow` precedence, `-O`, `-C` **resume**, `--retry` — over the taar transport; **HTTP + HTTPS both run on AGNOS**, QEMU-validated at 0.6.2, rebuilt at 0.6.3 onto the sovereign `tls_native_*` path) |
| Status | Working. `whirl [-X M] [-d DATA\|@file\|@-] [--data-binary D] [-H 'H: v'] [-A UA] [-i] [-I] [-f] [-r [-l N]] [-O\|-o FILE] [-C] [-L] [--retry N] http(s)://…` — resolve + connect (+ TLS) + request + emit/save; redirects (`-L`); recursive same-host crawl (`-r`); cert chain + hostname verified fail-closed. |
| Module footprint | `src/{version,util,url,http,cli,crawl,transport,output,links,main}.cyr` (+ `test.cyr`) — 11 modules, ~2,270 lines. `crawl.cyr` (0.6.7) holds link resolution, path confinement and robots parsing as pure logic, so the security-critical half is reachable from the unit suite. url / http / links / path-normalize pure-tested; transport rides taar (TCP+DNS), with TLS for https. |
| Cyrius pin | **6.5.35** (family-aligned with yo + taar; `dig` is the outlier at 6.2.24) |
| AGNOS validation | **End-to-end (0.6.9)**: `whirl http://example.com` and `whirl https://example.com` both return the **complete** Example Domain page over the sovereign stack, cert-verified (virtio-net + SLIRP, KVM). **Unit-level (0.6.10)**: `tests/agnos-probe.sh` runs `tests/agnos_probe.cyr` as `/bin/agnsh` — no keyboard, so no dropped-key retries — covering the trust-store search + cache, the `-C` resume append + >1 MiB guard, and `fs_is_symlink`'s agnos branch (including detection of a planted link): **14 checks, 0 failures**. Each run so far has found a real defect. **Iron on archaemenid remains open.** |
| Backends | **Linux** (raw-syscall TCP via taar; the `tls.cyr` facade for TLS) + **AGNOS** (taar's sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45 backend, landed at taar 0.3.0; whirl I/O portable via `sys_write`/`sys_read`/chrono/io + `#ifdef` for mkdir/stat/append). HTTP + HTTPS both **QEMU-validated on agnos** at 0.6.2; since 0.6.3 the agnos handshake calls `tls_native_*` **directly** (`_agnos_tls_native_connect`) rather than the facade's `tls_connect`, because agnos binaries are static and cannot use the libssl/`fdlopen` bridge. `tls_read`/`tls_write`/`tls_close` are shared by both targets. **`net` is not in the `[deps].stdlib` include list** — the transport is sovereign. |
| Tests | **`tests/agnos_probe.cyr`** + `tests/agnos-probe.sh` — the agnos-only paths, executed on a real kernel (14 checks). Builds for both targets, so its logic is checkable on the host before a QEMU run. `tests/whirl.tcyr` → **139 assertions** across 23 groups (URL parse + injection rejection, HTTP framing, credential headers, links + extractor cap, path normalization, path confinement, authority/port, origin comparison, shared helpers). Plus **`tests/behavior.py`** — an end-to-end suite against local adversarial servers, gated in CI (**26 checks** standalone; up to **41** with `--baseline <older binary>`, where 15 version-tagged controls first reproduce the defect each fix closed). Controls are version-aware: the baseline's version is read off its User-Agent, and a control the baseline already has fixed is skipped rather than failed. Live: `http://example.com` + `https://example.com` fetch, `-L https://github.com` (575 KB chunked), reachable self-signed cert rejected fail-closed (exit 9). |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — drove taar's `socket` + `dns` modules (taar 0.2.0); `tls`/`http` module growth still open. |
| Deps | stdlib base + **`[deps.taar]` 0.5.0** + the **opt-in crypto/TLS libs** (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls` plus `dynlib`/`fdlopen` since 0.6.3, vendored via `cyrius lib sync` — wired into CI). No stdlib `net`/`sandhi`. `lib/` is gitignored; `cyrius.lock` (61 entries) is the committed record. |
| Response cap | **1 MiB** (`WHIRL_RBUF_SZ`) for both the response buffer and a `-d @file` request body. Exceeding it is a reported error, never a silent truncation. |
| Floors | **agnos ≥ 1.45.16** (0.6.2's kernel-leased resolver, `net_config`#61) · **taar ≥ 0.5.0** (fail-closed DNS query-ID entropy) · **cyrius ≥ v5.6.37** for the `dynlib`+`fdlopen` include rule. |

## AGNOS readiness

whirl needs **zero new kernel syscalls** — the full call surface (`sock_*`#47-50, `getrandom`#45, UDP-53 #51-54, `net_config`#61, `uptime_ms`#40/`sleep_ms`#41, `stat`#33/`mkdir`, `readlink`#70) is landed and wired in the cyrius peer.

**Where it stands:** HTTP and HTTPS both run end-to-end on a real agnos kernel, cert-verified, over taar's sovereign backend, with the handshake calling `tls_native_*` directly (agnos binaries are static, so the libssl/`fdlopen` bridge is unusable there). The agnos-only branches — trust-store load + cache, `-C` resume, symlink detection — are exercised by `tests/agnos-probe.sh`. **Iron on archaemenid is the one remaining validation step**, plus the gaps listed under *Needs testing* above.

How each piece got there is in the [CHANGELOG](../../CHANGELOG.md); the call table is in [`roadmap.md`](roadmap.md) § *AGNOS call surface*.

> **Note (0.6.11):** the cyrius-peer defect `_agnos_ca_hook` was written for — `set_ca_system` opening the CA bundle with the Linux `sys_open` ABI — is fixed (cyrius v6.2.23). `tests/agnos_probe.cyr` proves it on a real kernel: `set_ca_system` returns 0, verifies a valid chain, and rejects a self-signed one. **The hook still stays.** It became the bundle cache at 0.6.8, and `set_ca_system` re-reads 1 MiB per call against a bump allocator with no free — measured at 1 MiB leaked per TLS connect, ~64 MiB on an HTTPS crawl. Retiring it is correct only once cyrius caches upstream (**B4**).

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| `taar` `tls` / `http` modules | whirl is the consumer that would add them (`tcp` shipped at taar 0.2.0 and whirl runs on it) | whirl + taar |
| Iron validation on archaemenid | hardware run over the r8169 NIC; parity benchmark vs `curl` | whirl + agnos |

## Needs testing — what has no executed coverage

Distinct from *Open defects* below: nothing here is known to be broken. These are
paths that **ship without ever having been run**, which is the state that produced
a real defect on each of the last three AGNOS runs. Ordered by how much is riding
on them.

| Gap | Status | What would close it |
|---|---|---|
| **Iron** — the whole tool on archaemenid | never run | roadmap **A3**: same fetch over the r8169 NIC, + parity benchmark vs `curl`. The critical path to 1.0 |
| **`-r` recursive crawl on AGNOS** | never run | no QEMU case drives `-r`. The crawl touches `mkdir`, `tree_relpath`, the symlink refusal and `_save_tree` — all agnos-arm code covered only as *units* by the probe |
| **`-C` resume end-to-end on AGNOS** | units only | the probe exercises `output_append` and the >1 MiB guard directly; no run performs an actual interrupted download and resumes it |
| **aarch64** | **compiles, never executed** | `cyrius build --aarch64` passes, so both `O_NOFOLLOW` branches compile — but the aarch64 value (32768 vs x86_64's 131072) has never run. A wrong value would not error; it would silently pass some other flag and drop the no-follow guarantee |
| **taar's DNS TC→TCP-53 fallback** | zero executed coverage anywhere | needs a truncated DNS reply. example.com's A RRset never sets TC, so the QEMU smoke cannot reach it. taar covers it on Linux under `unshare -rn`; the **AGNOS × TC** combination is untested in any repo |
| **TLS failure modes on AGNOS** | one case | the probe rejects one self-signed chain. Expired, wrong-host and truncated-handshake are unexercised there (all are covered on Linux) |
| **The agnos probe in CI** | manual only | needs QEMU + OVMF + sibling `agnos`/`gnoboot` checkouts, which a GitHub runner does not have. Deliberately manual — a step that always skips reads as coverage that does not exist |
| **macOS / Windows** | not a target | `lib/` carries the peers, but whirl declares neither. Not a gap unless the family adopts them |

> **The pattern worth keeping:** 0.6.9, 0.6.10 and 0.6.13 each changed AGNOS-arm
> code that CI compiles but nothing executes, and the first two runs after that
> gap each found a real defect (a complete response reported truncated; an
> `output_append` contract mismatch). Compile-verified is not verified.

## Open defects (confirmed, not yet fixed)

Current truth only. Each row says what is open, and why it is still open.

| Area | Defect |
|---|---|
| `_save_tree` TOCTOU — **AGNOS only** | closed on Linux at 0.6.13 (`O_NOFOLLOW` in `fs_write_no_follow`). agnos `open`(7) has no no-follow flag and no `O_EXCL`, so the pre-check and its race remain — filed as agnos `2026-08-27-open-ao-nofollow-flag` (roadmap **B2**) |
| symlinked intermediate dir | `O_NOFOLLOW` guards only the FINAL component (POSIX semantics), so a symlinked *directory* planted inside the crawl output is still followed. Narrower than the final-component case; not claimed as covered |
| `_agnos_ca_hook` | **resolved at 0.6.11 — keep it.** The ABI defect it was written for is fixed (verified on a real kernel: valid chain → TLS_OK, self-signed → rejected), but the hook is now the bundle **cache**, and `set_ca_system` leaks a measured **1 MiB per connect** without it. Retirable only once cyrius caches upstream (roadmap **B4**) |
| crawl caps | the 64-resource and 64-per-page caps are reported since 0.6.8, but there is no flag to raise them |


## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
