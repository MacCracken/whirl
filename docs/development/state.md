# whirl — Current State

> **⚠ NOT A LOG.** Live state with pointers — current truth only. Per-release history → [`../../CHANGELOG.md`](../../CHANGELOG.md). Milestone path → [`roadmap.md`](roadmap.md). Audits → [`../audit/`](../audit/).
>
> **Last refresh**: 2026-11-09 (0.7.2). Recent arc: 0.6.14–0.7.1 moved the
> toolchain 6.6.2 → 6.7.18 and taar → 0.6.2, retired `_agnos_ca_hook`, and made
> `cyrius audit` pass. 0.7.2 is whirl's first filed P(-1) audit
> ([`2026-11-09-audit.md`](../audit/2026-11-09-audit.md)): 23 findings, all
> repaired. The largest change: `-r` mirrors into `./HOST[:PORT]/` and refuses
> hidden paths.

---

## Snapshot

| Field | Value |
|---|---|
| Current version | **0.7.2** |
| Status | Working. `whirl [-X M] [-d DATA\|@file\|@-] [--data-binary D] [-H 'H: v'] [-A UA] [-i] [-I] [-f] [-r [-l N]] [-O\|-o FILE] [-C] [-L] [--retry N] http(s)://…`. HTTP/1.1 and HTTPS (certificate chain and hostname verified, fail-closed); redirects under `-L` with RFC 9110 method rules; `-C` resume with `Content-Range` checked; `-r` same-origin crawl mirrored under `./HOST[:PORT]/`, robots.txt per RFC 9309. Exit status 0 / 2 / 9 / 22, listed by `whirl -h`. |
| Module footprint | `src/{version,util,url,http,links,crawl,cli,transport,output,mirror,main}.cyr` (+ `test.cyr`): 12 files, ~2,780 lines. `crawl.cyr` is the pure half of `-r` (link resolution, path confinement, robots.txt parsing), reachable from the unit suite; `mirror.cyr` (0.7.2) is its I/O half. |
| Cyrius pin | **6.7.18**, family-aligned with yo, dig and taar. |
| Deps | stdlib + **`[deps.taar]` 0.6.2** (default builds resolve `git`+`tag`; `path = "../taar"` is used only with `CYRIUS_LOCAL=1`) + the crypto/TLS libs (`chrono`/`ct`/`keccak`/`random`/`bayan`/`sigil`/`tls_native`/`tls`), all vendored by `cyrius lib sync`. `assert` and `bench` are `[test]` leaves (0.7.2). No stdlib `net`/`sandhi`. `cyrius.lock` (72 rows, taar commit-pinned, `cyrius 6.7.18` trailer; `--locked` passes) is the committed record; `lib/` is gitignored. |
| Limits | 1 MiB response buffer and request body (`WHIRL_RBUF_SZ`, `CLI_BODY_MAX`; exceeding either is a reported error). 10 redirect hops. `-r`: 64 fetches, 64 links per page, 256 robots.txt rules, 512 KiB robots.txt. 10 s connect / send / recv deadline. |
| Backends | **Linux**: raw-syscall TCP via taar; TLS through the `tls.cyr` facade. **AGNOS**: taar's sovereign `sock_*`#47-50 / `udp_*`#51-54 / `getrandom`#45; HTTPS through `tls_native_*` directly (`_agnos_tls_native_connect`), with trust roots from `tls_native_set_ca_system`. The AGNOS dispatch is inline `#ifdef` in `transport.cyr`, `output.cyr` and `mirror.cyr`. |
| AGNOS validation | **End to end** (QEMU + KVM, agnos's `whirl-smoke.sh` from a throwaway tree): `--help`, HTTP and HTTPS (cert-verified), and since 0.7.2 `-r`, all passing at 0.7.2. **Unit level**: `tests/agnos-probe.sh` runs `tests/agnos_probe.cyr` as `/bin/agnsh` (no keyboard) — trust store, verify good/bad, CA cost ≤ 16 KiB per connect (656 B measured), `-C` append and its >1 MiB guard, readlink#70 symlink detection: **14/14 at 0.7.2**. **Iron is still open.** |
| Tests | `tests/whirl.tcyr`: **139 assertions** (pure logic). `tests/behavior.py`: end to end against local test servers, gated in CI: **49 checks** standalone, **57** with `--baseline <older binary>`, whose version-tagged controls reproduce each defect first (skipped when the baseline already has the fix). `tests/agnos_probe.cyr`: 14 checks on a real kernel (manual). `benches/parse.bcyr`: 13 rows over the per-response CPU paths (`cyrius bench benches/`). |
| Family position | Third in the network-tools family (after yo and dig); third taar consumer, running on taar's `tcp` + `dns`; the candidate donor for taar's unwritten `tls` / `http` (roadmap C1). |
| Floors | **agnos ≥ 1.45.16** (kernel-leased resolver, `net_config`#61) · **taar ≥ 0.6.2** (connect/send deadline; fail-closed resolv.conf) · **cyrius ≥ 6.7.6** (`path` as local-only override, `[test]` section). |

## Carry-forward (dependent on other repos)

| Item | Blocked on | Owning repo |
|---|---|---|
| taar `tls` / `http` modules | the C1 decision: whether whirl's HTTP framing and TLS composition belong in a shared substrate | whirl + taar |
| Iron validation on archaemenid | a hardware run over the r8169 NIC, and a parity benchmark against `curl` | whirl + agnos |
| ~307 KB of dead Unicode tables in every image | bayan 1.11 includes all three `lib/unicode/_*_data.cyr` tables unconditionally; DCE drops the 32 unreached `unicode_*` fns but keeps the string literals only they reference. whirl reaches none of them | cyrius (DCE) / bayan |
| B2: AGNOS symlink refusal is a pre-check | agnos `open`(7) has no no-follow flag (`2026-08-27-open-ao-nofollow-flag`) | agnos |

## Needs testing — what has no executed coverage

Distinct from *Open defects*: nothing here is known to be broken. These paths
ship without having been run, or without a test that fails when they break.

| Gap | Status | What would close it |
|---|---|---|
| **Iron**: the whole tool on archaemenid | never run | roadmap A3 |
| **0.7.2 repairs without a dedicated test** | reviewed; every existing check passes | the chunk-size digit bound, stderr escaping, the 1xx skip, half header blocks under `-i`/`-I`, `Location` trimming, the crawl's case-insensitive host match and `?query` resolution, the deadline check, `Content-Length: 0` for an empty body. Roadmap 0.8.x |
| **`-C` resume end to end on AGNOS** | units only | the probe exercises `output_append` and its guard; no run resumes a real interrupted download there |
| **aarch64** | emulated only | under qemu-user the unit and behavioral suites pass and the `O_NOFOLLOW` negative control fails as it should; CI builds it (0.7.2) and fails on any warning in `src/`. Never run on aarch64 hardware |
| **taar's DNS TC→TCP-53 fallback** on AGNOS | zero executed coverage | a truncated DNS reply; example.com never sets TC |
| **TLS failure modes on AGNOS** | one case | the probe refuses one self-signed chain; expired, wrong-host and truncated handshakes are covered on Linux only |
| **The agnos probe and smoke in CI** | manual | they need QEMU, OVMF and sibling `agnos` / `gnoboot` checkouts. Deliberately manual: a step that always skips reads as coverage that does not exist |

> **The pattern worth keeping:** every AGNOS run after a stretch of compile-only
> checking has found something real — a complete response reported truncated,
> an `output_append` contract mismatch, a probe that could not build, a CA hook
> that had become the leak. Compile-verified is not verified.

## Open defects (confirmed, not yet fixed)

Current truth only. Each row says what is open, and why.

| Area | Defect |
|---|---|
| `-r` symlink race — **AGNOS only** | closed on Linux (`O_NOFOLLOW` in `fs_write_no_follow`). AGNOS `open`(7) has no no-follow flag, so the pre-check and its race remain (B2; blocked on the kernel) |
| symlinked directory inside the mirror | `O_NOFOLLOW` guards only the final component, so a symlinked *directory* planted in the mirror (the per-host directory included) is still followed. Needs local write access to the cwd; fix is a per-component `openat` walk (B5, roadmap 0.8.x) |

Behaviour that is bounded but not a defect (crawl caps without a flag, the 1 MiB
buffer, `-r` not following redirects, `--retry` not retrying HTTP 5xx) is
tracked in [`roadmap.md`](roadmap.md) § 0.8.x.

## Pointers

- [agnosticos shared-crates.md § whirl + network-tools family](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/shared-crates.md)
- Siblings: [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig) · [taar](https://github.com/MacCracken/taar)
