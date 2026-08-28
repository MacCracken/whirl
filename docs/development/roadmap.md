# whirl — Roadmap

> **The path to 1.0.0, and the AGNOS call surface.** Per-release history lives in
> [`../../CHANGELOG.md`](../../CHANGELOG.md) — this file does not repeat it.
> Current version, surface area and open defects live in [`state.md`](state.md).

---

## Remaining for 1.0.0

Four workstreams. **A3 (iron) is the critical path**; the others can proceed in
parallel. Completed items are not listed here — per-release history is in the
[CHANGELOG](../../CHANGELOG.md).

### A. AGNOS validation

- [ ] **A3 — Iron on archaemenid.** Same run over the r8169 NIC. Parity
      benchmark vs `curl` (latency / RSS / binary size). **The critical path to 1.0.**

### B. Open defects

Full detail in [`state.md`](state.md) § *Open defects*.

- [ ] **B2 — `_save_tree` TOCTOU, AGNOS half.** Closed on Linux at 0.6.13
      (`O_NOFOLLOW` makes the refusal part of the open). agnos `open`(7) has no
      no-follow flag and no `O_EXCL`, so the pre-check and its race remain.
      **Blocked on the kernel** — filed as agnos
      `2026-08-27-open-ao-nofollow-flag`; the machinery exists
      (`ext2_path_lookup_ex(..., follow_last=0)`), the ask is to expose it.
- [ ] **B5 — Symlinked intermediate directory.** `O_NOFOLLOW` guards only the
      FINAL component (POSIX semantics, and readlink#70's), so a symlinked
      *directory* planted inside the crawl output is still followed. Needs
      per-component `openat` walking, on both targets. Narrower than B2 and
      unblocked — no kernel change required on Linux.
- [ ] **B4 — Upstream: cyrius should cache the system trust bundle.**
      `tls_native_set_ca_system` allocates 1 MiB on every call and caches
      nothing. Every agnos TLS consumer pays that, not just whirl. Fixing it
      upstream is what makes B3 genuinely doable — at which point
      `_agnos_ca_hook` becomes deletable in a one-line change.

### C. Substrate — `taar` `tls` / `http` modules

A standing v1.0 criterion: whirl vendors no network primitives locally, and is
the consumer that grows taar's remaining modules. `tcp` shipped at taar 0.2.0 and
whirl runs on it; `tls` and `http` are **still unwritten** (verified: zero
`taar_tls_*` / `taar_http_*` symbols at taar 0.5.0).

- [ ] **C1 — Decide the split.** whirl's HTTP framing (`src/http.cyr`) and TLS
      composition (`src/transport.cyr`) are the candidate donors. Worth settling
      whether they genuinely belong in a shared substrate or whether the
      criterion should narrow to `tcp` + `dns` — a module with exactly one
      consumer is not yet shared code.
- [ ] **C2 — Extract whatever C1 selects**, in taar, with whirl as the consumer.

### D. Limits and ergonomics

Not defects, but each is a place where whirl's behaviour is bounded in a way a
1.0 should either lift or state plainly.

- [ ] **D1 — Whole-response buffering.** `WHIRL_RBUF_SZ` is 1 MiB and the entire
      response is held in memory; a body over the cap is an error (0.6.6 made it
      loud rather than silent, which was the bug). For the wget half of the tool
      that is a real limitation: large downloads are the use case. Streaming to
      the output sink instead of buffering is the fix, and it interacts with
      `-C` resume, chunked decode and the truncation check.
- [ ] **D2 — Configurable crawl caps.** The 64-resource and 64-per-page caps are
      reported since 0.6.8 but cannot be raised.
- [ ] **D3 — Document exit codes.** 0 / 2 (usage, bad URL, bad body) / 9
      (transport, TLS, malformed, truncated, write failure) / 22 (`-f` on ≥ 400)
      are established but appear in no user-facing doc.

---

## v1.0.0 criteria

- [x] GET + POST + arbitrary methods + custom headers; redirects; chunked; HTTPS
      with cert verification — shipped 0.3.0–0.5.3, fail-closed verify proven
      against a reachable bad-cert server.
- [x] **No POSIX `socket()`** anywhere in the AGNOS backend — the agnos arm binds
      `sock_*`#47-50 / `udp_*`#51-54 exclusively.
- [~] Security. The 0.6.6 audit's P-1/P-2/P-3 tiers are closed and B1 is fixed
      on both targets. **Two symlink-write races remain open and are not
      hand-waved**: B2's AGNOS half (blocked on a kernel flag) and B5 (mid-path
      symlink, both targets, unblocked). Both are bounded — each needs write
      access to the crawl output directory — but "no known unfixed security
      defect" would be false today, so this is not ticked.
- [x] AGNOS backend resolves + fetches `https://` end-to-end (DNS → TCP → TLS →
      HTTP) on a current build — QEMU-validated at 0.6.9.
- [ ] The same, **iron-validated** on archaemenid — A3.
- [ ] Consumes `taar` with no network primitives vendored locally — C1/C2, or a
      deliberate narrowing of the criterion.
- [ ] Large transfers are not bounded by memory, or the bound is documented as
      intended — D1.

---

## Post-1.0 (not scoped)

Recorded so they are not mistaken for 1.0 gaps: HTTP/2, connection reuse /
keep-alive, cookie jar, proxy support, IPv6 (`taar_resolve_ipv4` is A-record
only), compression (`Accept-Encoding`), parallel crawl fetches, `--limit-rate`.

---

## AGNOS call surface

whirl's AGNOS arm binds **only** the calls below. Unlike dig/yo there is **no
`platform_agnos.cyr`** — the dispatch is inline `#ifdef CYRIUS_TARGET_AGNOS` in
`src/transport.cyr`, `src/main.cyr` and `src/output.cyr`. Every kernel half
landed, and the cyrius-side wiring landed too: composed at 0.6.1, proven
end-to-end on QEMU at 0.6.2, rebuilt onto the direct `tls_native_*` path at 0.6.3.

| Need | AGNOS kernel syscall | Status (kernel) | cyrius peer |
|---|---|---|---|
| TCP connect | `sock_connect`#47 (dst_ip, dst_port, src_port) → conn_id | ✅ landed agnos 1.45.1 | `net.cyr sock_connect` — client band wired v6.2.3 |
| TCP send | `sock_send`#48 (conn_id, buf, len) | ✅ 1.45.1 | `net.cyr sock_send` ✅ |
| TCP recv | `sock_recv`#49 (conn_id, buf, max) non-blocking, WOULD_BLOCK/EOF split | ✅ 1.45.1 | `net.cyr sock_recv` ✅ |
| TCP close | `sock_close`#50 (conn_id) | ✅ 1.45.1 | `net.cyr sock_close` ✅ |
| TLS (HTTPS) | *(none — runs over the TCP calls)* | n/a | `tls_native` is transport-agnostic: `tls_native_set_transport(read_fn, write_fn, now_fn)` over `sock_recv`#49 / `sock_send`#48, then `tls_native_connect` / `_write` / `_read` / `_close` + `tls_native_client_verify_hostname`. Client TLS peer wired v6.2.3 |
| TLS / nonce entropy | `getrandom`#45 (buf, len, flags) — Zen RDRAND | ✅ landed agnos 1.45.0 | `random.cyr` / `SYS_GETRANDOM=45` ✅ |
| DNS resolve | UDP-53 `udp_bind`#51 / `udp_send`#52 / `udp_recv`#53 / `udp_unbind`#54 | ✅ landed agnos 1.45.3 | `taar.dns` over the UDP wrappers; dig drives the same path |
| Monotonic clock / sleep | `uptime_ms`#40 / `sleep_ms`#41 | ✅ landed | `sys_uptime_ms` / `sys_sleep_ms` wrappers (cyrius ≥ 6.2.6) ✅ |
| Kernel-leased resolver | `net_config`#61 field 3 (DHCP option-6 nameserver) | ✅ landed agnos 1.45.16 | `sys_net_dns_server()` ✅ — reached via `taar_resolve_ipv4` → `_taar_resolv_discover`, tried **before** `/etc/resolv.conf`. Hard dependency since 0.6.2: the off-subnet `8.8.8.8` fallback needs gateway routing the kernel cannot guarantee on iron |
| Symlink detection (`-r` safety) | `readlink`#70 (no-follow final component) | ✅ landed agnos 1.5x | `sys_readlink()` ✅ — `fs_is_symlink` treats success as "is a link" (0.6.12). Chosen by the kernel over an `lstat` variant of `stat`#33 |

**Net:** whirl needs **zero new kernel syscalls**, and the transport lock-down is
closed. The one open kernel ask is **B2** — an `AO_NOFOLLOW` flag on `open`(7),
filed as agnos `2026-08-27-open-ao-nofollow-flag`. Like the old B1 ask it is a
filesystem concern, not a network one — and B1 turned out not to need a kernel
change at all, since `readlink`#70 already answered it.

> Cross-refs: [agnos net-syscall arc](https://github.com/MacCracken/agnosticos/blob/main/docs/development/state.md) (#45-#57) · [taar](https://github.com/MacCracken/taar) (substrate) · [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig)
