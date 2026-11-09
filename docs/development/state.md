# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-11-09 (0.7.1). Recent arc: AGNOS revalidated end-to-end
> and at unit level after six releases of compile-only checking, and the 0.6.6
> audit's follow-ups (B1/B3) closed. 0.6.14–0.7.1 moved the toolchain
> 6.6.2 → 6.6.20 → 6.7.9 → 6.7.18 and taar 0.5.0 → 0.6.2. 0.7.0 first executed the
> aarch64 build, under qemu-user. 0.7.1 is family-aligned again, brings taar
> 0.6.2's connect/send deadline, and is the first release where `cyrius audit`
> passes (lint clean, every public fn documented). Per-release detail is in the
> [CHANGELOG](../../CHANGELOG.md) — this file does not repeat it.

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.7.1** (HTTP/1.1 + HTTPS; GET/POST/methods + headers + `-A` UA; `-i`/`-I`/`-f`; **`-r` recursive** w/ tree-mirroring + robots.txt `Allow`/`Disallow` precedence, `-O`, `-C` **resume**, `--retry` — over the taar transport; **HTTP + HTTPS both run on AGNOS**, QEMU-validated at 0.6.2, rebuilt at 0.6.3 onto the sovereign `tls_native_*` path) |
| Status | Working. `whirl [-X M] [-d DATA\|@file\|@-] [--data-binary D] [-H 'H: v'] [-A UA] [-i] [-I] [-f] [-r [-l N]] [-O\|-o FILE] [-C] [-L] [--retry N] http(s)://…` — resolve + connect (+ TLS) + request + emit/save; redirects (`-L`); recursive same-host crawl (`-r`); cert chain + hostname verified fail-closed. |
| Module footprint | `src/{version,util,url,http,cli,crawl,transport,output,links,main}.cyr` (+ `test.cyr`) — 11 modules, ~2,270 lines. `crawl.cyr` (0.6.7) holds link resolution, path confinement and robots parsing as pure logic, so the security-critical half is reachable from the unit suite. url / http / links / path-normalize pure-tested; transport rides taar (TCP+DNS), with TLS for https. |
| Cyrius pin | **6.7.18**, family-aligned with yo, dig and taar. |
| AGNOS validation | **End-to-end (0.6.9)**: `whirl http://example.com` and `whirl https://example.com` both return the **complete** Example Domain page over the sovereign stack, cert-verified (virtio-net + SLIRP, KVM), re-run at **0.7.1** (cyrius 6.7.18, `_agnos_ca_hook` retired, via agnos's `whirl-smoke.sh` from a throwaway tree): all three checks pass. **Unit-level (0.6.10)**: `tests/agnos-probe.sh` runs `tests/agnos_probe.cyr` as `/bin/agnsh` — no keyboard, so no dropped-key retries — covering the trust store (bundle loads, every ctx shares one root set, whirl's own `_agnos_tls_native_connect` verifies a valid chain and refuses a self-signed one, per-connect cost ≤ 16 KiB), the `-C` resume append + >1 MiB guard, and `fs_is_symlink`'s agnos branch (including detection of a planted link): **14 checks, 0 failures**, last run at **0.7.1 on cyrius 6.7.18 with `_agnos_ca_hook` retired**. That was the first run since 0.6.13, because the harness's build guard had rejected every build since 0.6.14 (fixed at 0.7.1). Each run so far has found something real; 0.7.1's was that the CA hook had become the leak. **Iron on archaemenid remains open.** |
| Backends | **Linux** (raw-syscall TCP via taar; the `tls.cyr` facade for TLS) + **AGNOS** (taar's sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45 backend, landed at taar 0.3.0; whirl I/O portable via `sys_write`/`sys_read`/chrono/io + `#ifdef` for mkdir/stat/append). HTTP + HTTPS both **QEMU-validated on agnos** at 0.6.2; since 0.6.3 the agnos handshake calls `tls_native_*` **directly** (`_agnos_tls_native_connect`) rather than the facade's `tls_connect`, because agnos binaries are static and cannot use the libssl/`fdlopen` bridge. `tls_read`/`tls_write`/`tls_close` are shared by both targets. **`net` is not in the `[deps].stdlib` include list** — the transport is sovereign. |
| Tests | **`tests/agnos_probe.cyr`** + `tests/agnos-probe.sh` — the agnos-only paths, executed on a real kernel (14 checks). Builds for both targets, so its logic is checkable on the host before a QEMU run. It writes scratch files to `/`, so run the host build in a writable root (`unshare -r chroot <dir> /probe`), or `resume-setup` fails for that reason alone. `tests/whirl.tcyr` → **139 assertions** across 23 groups (URL parse + injection rejection, HTTP framing, credential headers, links + extractor cap, path normalization, path confinement, authority/port, origin comparison, shared helpers). Plus **`tests/behavior.py`** — an end-to-end suite against local adversarial servers, gated in CI (**26 checks** standalone; up to **41** with `--baseline <older binary>`, where 15 version-tagged controls first reproduce the defect each fix closed). Controls are version-aware: the baseline's version is read off its User-Agent, and a control the baseline already has fixed is skipped rather than failed. Live: `http://example.com` + `https://example.com` fetch, `-L https://github.com` (chunked, 525 KB at 0.6.15), reachable self-signed cert rejected fail-closed (exit 9), and a real `-C` resume against a local Range server (0.6.15). |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — drove taar's `socket` + `dns` modules (taar 0.2.0); `tls`/`http` module growth still open. |
| Deps | stdlib base + **`[deps.taar]` 0.6.2** (default builds resolve `git`+`tag` locally and in CI; `path = "../taar"` is a local-mode-only override since cyrius 6.7.6, used with `CYRIUS_LOCAL=1`) + the **opt-in crypto/TLS libs** (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls` plus `dynlib`/`fdlopen` since 0.6.3, redundant since cyrius 6.6.9 but still listed; all vendored via `cyrius lib sync`, which is wired into CI). No stdlib `net`/`sandhi`. `lib/` is gitignored. `cyrius.lock` (73 rows, taar 0.6.2 commit-pinned, `cyrius 6.7.18` trailer; `cyrius deps --locked` passes) is the committed record. |
| Response cap | **1 MiB** (`WHIRL_RBUF_SZ`) for both the response buffer and a `-d @file` request body. Exceeding it is a reported error, never a silent truncation. |
| Floors | **agnos ≥ 1.45.16** (0.6.2's kernel-leased resolver, `net_config`#61) · **taar ≥ 0.5.0** (fail-closed DNS query-ID entropy) · **cyrius ≥ v5.6.37** for the `dynlib`+`fdlopen` include rule (moot from 6.6.9 on, where `tls.cyr` includes `fdlopen` itself). |

## AGNOS readiness

whirl needs **zero new kernel syscalls** — the full call surface (`sock_*`#47-50, `getrandom`#45, UDP-53 #51-54, `net_config`#61, `uptime_ms`#40/`sleep_ms`#41, `stat`#33/`mkdir`, `readlink`#70) is landed and wired in the cyrius peer.

**Where it stands:** HTTP and HTTPS both run end-to-end on a real agnos kernel, cert-verified, over taar's sovereign backend, with the handshake calling `tls_native_*` directly (agnos binaries are static, so the libssl/`fdlopen` bridge is unusable there). The agnos-only branches — trust-store load + cache, `-C` resume, symlink detection — are exercised by `tests/agnos-probe.sh`. **Iron on archaemenid is the one remaining validation step**, plus the gaps listed under *Needs testing* above.

How each piece got there is in the [CHANGELOG](../../CHANGELOG.md); the call table is in [`roadmap.md`](roadmap.md) § *AGNOS call surface*.

> **Note (0.7.1): `_agnos_ca_hook` is retired.** It was written at 0.6.2 for a cyrius ABI defect (fixed in v6.2.23). From 0.6.8 it was kept as the CA-bundle cache, because `set_ca_system` leaked 1 MiB per connect on cyrius 6.5.35. cyrius has cached upstream since v6.5.36 (bundle) and 6.6.13 (one shared parsed root set). On a real kernel at 6.7.18 the hook cost ~272,720 B per connect, because it re-parsed the bundle into every ctx, against `set_ca_system`'s ~656 B. `_agnos_tls_native_connect` now calls `_agnos_ca_install` → `tls_native_set_ca_system`, and fails before any network I/O if no bundle is readable. `tests/agnos_probe.cyr`'s `ca-cost-bounded` check pins the cost at ≤ 16 KiB per connect.

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| `taar` `tls` / `http` modules | whirl is the consumer that would add them (`tcp` shipped at taar 0.2.0 and whirl runs on it) | whirl + taar |
| Iron validation on archaemenid | hardware run over the r8169 NIC; parity benchmark vs `curl` | whirl + agnos |
| ~307 KB of dead Unicode tables in every image (0.7.1) | bayan 1.11 includes all three `lib/unicode/_*_data.cyr` tables unconditionally, and DCE drops the 32 dead `unicode_*` fns but keeps the string literals only they reference. whirl reaches none of them | cyrius (DCE) / bayan |

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
| **aarch64** | **emulated only (0.7.0, re-run at 0.7.1)** | Under qemu-user the unit suite (139/139), `behavior.py` (26/26), a live HTTP and HTTPS fetch and a `-C` resume all pass. The `O_NOFOLLOW` value is proven by a negative control: planting x86_64's 131072 in the aarch64 arm fails check [13]. It has never run on aarch64 hardware or an aarch64 kernel. A run on a real board would close it. Until then, the qemu result rests on qemu's flag translation being faithful |
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
| crawl caps | the 64-resource and 64-per-page caps are reported since 0.6.8, but there is no flag to raise them |
| resolve-failure message | `main` reports every transport error as `whirl: connection failed` (exit 9), so a DNS failure reads like a connect failure. Since taar 0.6.2 (whirl 0.7.1) a resolv.conf naming only unusable resolvers fails closed, which makes this path more likely to be hit. `TRANSPORT_ERR_RESOLVE` already exists to tell them apart |


## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
