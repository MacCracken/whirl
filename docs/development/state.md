# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md).
>
> **Last refresh**: 2026-08-27 (0.6.13 — **B2 Linux half closed**: the symlink refusal moved inside the open via `O_NOFOLLOW`, eliminating the check-then-write window; the agnos half is filed upstream as it needs a kernel flag. Previously 0.6.12 — **B1 closed**: `-r` now detects symlinks on AGNOS via `readlink`#70; the "needs a kernel lstat" framing was wrong, the primitive had already shipped. Previously 0.6.11 — **B3 closed as "won't do"**: the ca-hook's ABI rationale is obsolete, but its *cache* is load-bearing — `set_ca_system` leaks a measured 1 MiB per TLS connect. Raised upstream as B4. Previously 0.6.10 — **A2 complete**: the agnos-only trust-store, `-C` resume and symlink paths now execute on a real kernel (11 checks, 0 failures) via `tests/agnos_probe.cyr`, which found a latent `output_append` contract defect and answered B3. Previously 0.6.9 — **QEMU-revalidated on AGNOS**, the first execution of the agnos arm since 0.6.2. It found a real defect on the first run: whirl waited for a socket close it did not need, so a complete chunked body was reported truncated. Fixed — the response framing is now the authority. Iron on archaemenid still the open validation step.)

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.6.13** (HTTP/1.1 + HTTPS; GET/POST/methods + headers + `-A` UA; `-i`/`-I`/`-f`; **`-r` recursive** w/ tree-mirroring + robots.txt `Allow`/`Disallow` precedence, `-O`, `-C` **resume**, `--retry` — over the taar transport; **HTTP + HTTPS both run on AGNOS**, QEMU-validated at 0.6.2, rebuilt at 0.6.3 onto the sovereign `tls_native_*` path) |
| Status | Working. `whirl [-X M] [-d DATA\|@file\|@-] [--data-binary D] [-H 'H: v'] [-A UA] [-i] [-I] [-f] [-r [-l N]] [-O\|-o FILE] [-C] [-L] [--retry N] http(s)://…` — resolve + connect (+ TLS) + request + emit/save; redirects (`-L`); recursive same-host crawl (`-r`); cert chain + hostname verified fail-closed. |
| Module footprint | `src/{version,util,url,http,cli,crawl,transport,output,links,main}.cyr` (+ `test.cyr`) — 11 modules, ~2,100 lines. `crawl.cyr` (0.6.7) holds link resolution, path confinement and robots parsing as pure logic, so the security-critical half is reachable from the unit suite. url / http / links / path-normalize pure-tested; transport rides taar (TCP+DNS), with TLS for https. |
| Cyrius pin | **6.5.35** (family-aligned with yo + taar; `dig` is the outlier at 6.2.24) |
| AGNOS validation | **End-to-end (0.6.9)**: `whirl http://example.com` and `whirl https://example.com` both return the **complete** Example Domain page over the sovereign stack, cert-verified (virtio-net + SLIRP, KVM). **Unit-level (0.6.10)**: `tests/agnos-probe.sh` runs `tests/agnos_probe.cyr` as `/bin/agnsh` — no keyboard, so no dropped-key retries — covering the trust-store search + cache, the `-C` resume append + >1 MiB guard, and `fs_is_symlink`'s agnos branch: **11 checks, 0 failures**. Each run so far has found a real defect. **Iron on archaemenid remains open.** |
| Backends | **Linux** (raw-syscall TCP via taar; the `tls.cyr` facade for TLS) + **AGNOS** (taar's sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45 backend, landed at taar 0.3.0; whirl I/O portable via `sys_write`/`sys_read`/chrono/io + `#ifdef` for mkdir/stat/append). HTTP + HTTPS both **QEMU-validated on agnos** at 0.6.2; since 0.6.3 the agnos handshake calls `tls_native_*` **directly** (`_agnos_tls_native_connect`) rather than the facade's `tls_connect`, because agnos binaries are static and cannot use the libssl/`fdlopen` bridge. `tls_read`/`tls_write`/`tls_close` are shared by both targets. **`net` is not in the `[deps].stdlib` include list** — the transport is sovereign. |
| Tests | **`tests/agnos_probe.cyr`** + `tests/agnos-probe.sh` — the agnos-only paths, executed on a real kernel (11 checks). Builds for both targets, so its logic is checkable on the host before a QEMU run. `tests/whirl.tcyr` → **139 assertions** across 23 groups (URL parse + injection rejection, HTTP framing, credential headers, links + extractor cap, path normalization, path confinement, authority/port, origin comparison, shared helpers). Plus **`tests/behavior.py`** — an end-to-end suite against local adversarial servers, gated in CI (**25 checks** standalone; up to **31** with `--baseline <older binary>`, where each fix first reproduces its defect). Controls are version-aware: the baseline's version is read off its User-Agent, and a control the baseline already has fixed is skipped rather than failed. Live: `http://example.com` + `https://example.com` fetch, `-L https://github.com` (575 KB chunked), reachable self-signed cert rejected fail-closed (exit 9). |
| Family position | Third entry in the network-tools family (after yo + dig). Third `taar` consumer — drove taar's `socket` + `dns` modules (taar 0.2.0); `tls`/`http` module growth still open. |
| Deps | stdlib base + **`[deps.taar]` 0.5.0** + the **opt-in crypto/TLS libs** (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls` plus `dynlib`/`fdlopen` since 0.6.3, vendored via `cyrius lib sync` — wired into CI). No stdlib `net`/`sandhi`. `lib/` is gitignored; `cyrius.lock` (61 entries) is the committed record. |
| Response cap | **1 MiB** (`WHIRL_RBUF_SZ`) for both the response buffer and a `-d @file` request body. Exceeding it is a reported error, never a silent truncation. |
| Floors | **agnos ≥ 1.45.16** (0.6.2's kernel-leased resolver, `net_config`#61) · **taar ≥ 0.5.0** (fail-closed DNS query-ID entropy) · **cyrius ≥ v5.6.37** for the `dynlib`+`fdlopen` include rule. |

## AGNOS readiness

whirl needs **zero new kernel syscalls** — the full call surface (`sock_*`#47-50, `getrandom`#45, UDP-53 #51-54, `net_config`#61, `uptime_ms`#40/`sleep_ms`#41, `stat`#33/`mkdir`) is landed, and the client band + `tls_native` are wired in the cyrius peer. **0.6.0**: the plain-HTTP path runs on agnos (taar 0.3.0's sovereign backend; `CYRIUS_TARGET_AGNOS=1` compiles the whole tool). **0.6.1**: composed `tls_native` over the taar socket via `tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)` (the agnos TCP "fd" is a sentinel, so the default raw-fd path won't route; `now_fn=0` keeps the `sys_time_unix`#46 cert clock). **0.6.2**: **QEMU-validated** (virtio-net + SLIRP) — real example.com fetched over HTTP *and* HTTPS, which also proved 0.6.1's "correct-by-construction" claim had been wrong; needed `_agnos_ca_hook` for trust roots. **0.6.3**: dropped the `tls.cyr` facade on agnos for direct `tls_native_*` calls (static binaries have no `ld.so`, so `fdlopen` is both unbuildable and unusable). **0.6.4**: confirmed under mirshi. **Iron on archaemenid is the remaining step.** Full table in [`roadmap.md`](roadmap.md) § *AGNOS call surface*.

> **Note (0.6.11):** the cyrius-peer defect `_agnos_ca_hook` was written for — `set_ca_system` opening the CA bundle with the Linux `sys_open` ABI — is fixed (cyrius v6.2.23). `tests/agnos_probe.cyr` proves it on a real kernel: `set_ca_system` returns 0, verifies a valid chain, and rejects a self-signed one. **The hook still stays.** It became the bundle cache at 0.6.8, and `set_ca_system` re-reads 1 MiB per call against a bump allocator with no free — measured at 1 MiB leaked per TLS connect, ~64 MiB on an HTTPS crawl. Retiring it is correct only once cyrius caches upstream (**B4**).

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| `taar` `tls` / `http` modules | whirl is the consumer that would add them (`tcp` shipped at taar 0.2.0 and whirl runs on it) | whirl + taar |
| Iron validation on archaemenid | hardware run over the r8169 NIC; parity benchmark vs `curl` | whirl + agnos |

## Open defects (confirmed, not yet fixed)

Carried from the 0.6.6 audit — see [`../../CHANGELOG.md`](../../CHANGELOG.md) § 0.6.6 *Known latent* for detail.

| Area | Defect |
|---|---|
| `_save_tree` TOCTOU — **AGNOS only** | closed on Linux at 0.6.13 (`O_NOFOLLOW` in `fs_write_no_follow`). agnos `open`(7) has no no-follow flag and no `O_EXCL`, so the pre-check and its race remain — filed as agnos `2026-08-27-open-ao-nofollow-flag` (roadmap **B2**) |
| symlinked intermediate dir | `O_NOFOLLOW` guards only the FINAL component (POSIX semantics), so a symlinked *directory* planted inside the crawl output is still followed. Narrower than the final-component case; not claimed as covered |
| `_agnos_ca_hook` | **resolved at 0.6.11 — keep it.** The ABI defect it was written for is fixed (verified on a real kernel: valid chain → TLS_OK, self-signed → rejected), but the hook is now the bundle **cache**, and `set_ca_system` leaks a measured **1 MiB per connect** without it. Retirable only once cyrius caches upstream (roadmap **B4**) |
| crawl caps | the 64-resource and 64-per-page caps are reported since 0.6.8, but there is no flag to raise them |

> The 0.6.6 audit is now closed out. Cleared at 0.6.7: origin confinement,
> robots/relative-link port handling, silent request truncation, the CA-hook leak
> and NULL write, the agnos resume data loss, the duplicated read loop. Cleared at
> 0.6.8: unchecked `alloc()`, Linux symlink writes, both silent crawl caps, the
> duplicated helpers, and the inlined version literal.

## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
