# whirl — Roadmap

> **The path to 1.0.0, and the AGNOS call surface.** Per-release history lives in
> [`../../CHANGELOG.md`](../../CHANGELOG.md) — this file does not repeat it.
> Current version, surface area and open defects live in [`state.md`](state.md).
>
> Restructured at 0.6.8: the milestone-by-milestone record that used to fill this
> file was a second copy of the changelog, and it had gone stale in three places
> (a superseded toolchain pin, an old assertion count, and follow-ups ticked as
> open after they shipped). What survives is the part a roadmap is for: **what is
> left, in what order, and what "done" means.**

---

## Shipped

One line per release; detail in the [CHANGELOG](../../CHANGELOG.md).

| Version | What landed |
|---|---|
| 0.1.0 | Scaffold: manifest, CI/release workflows, docs skeleton |
| 0.2.0 | HTTP/1.1 GET over the taar substrate — url / http / transport / output modules |
| 0.3.0 | HTTPS with fail-closed cert + hostname verification; redirect UX |
| 0.4.0 | `-d` / `-X` / `-H` — methods, bodies, custom headers |
| 0.5.0–0.5.3 | The wget side: `-r` recursive fetch, tree mirroring, robots.txt, `-O`, `-C` resume, `--retry`, `-A`/`-i`/`-I`/`-f` |
| 0.6.0–0.6.1 | HTTP then HTTPS running on AGNOS over taar's sovereign backend |
| 0.6.2 | First QEMU validation on a real agnos kernel; `_agnos_ca_hook` trust-root fix |
| 0.6.3–0.6.4 | AGNOS off the libssl/`fdlopen` bridge onto direct `tls_native_*`; mirshi re-cut |
| 0.6.5 | Toolchain 6.5.35, taar 0.5.0, vendored stdlib re-cut; binary 13.9 MB → 2.0 MB |
| 0.6.6 | **P-1 security sweep** — remote arbitrary file write via `-r`, request splitting via `Location`, cross-origin credential replay, silent truncation. CI compiles the AGNOS arm; `tests/behavior.py` added |
| 0.6.7 | **P-2 tier** — crawl confined to an origin, port correctness throughout, overflow bounds; `src/crawl.cyr` extracted |
| 0.6.8 | **P-3 tier** — checked allocation, Linux symlink refusal, both crawl caps reported; `src/util.cyr` + `src/version.cyr` |
| 0.6.9 | **QEMU-revalidated on AGNOS** — HTTP + HTTPS end-to-end on a real kernel; fixed the defect that run found (a complete response reported truncated because whirl waited for a socket close it did not need) |

---

## Remaining for 1.0.0

Four workstreams. **A3 (iron) is the critical path** now that A1 has landed;
the others can proceed in parallel.

### A. AGNOS validation

- [x] **A1 — QEMU re-validation** ✅ 0.6.9. HTTP and HTTPS both fetch the
      complete Example Domain page on a real agnos kernel over the sovereign
      stack (virtio-net + SLIRP, KVM), cert-verified. Six releases of
      agnos-affecting change had accumulated behind compile-only checking, and
      the run found a defect on the first attempt — whirl waited for a socket
      close it did not need, so a complete chunked body was reported truncated.
      Fixed in the same release; the response framing is now the authority.
      **The lesson worth keeping: compile-verified is not verified.**
- [ ] **A2 — Exercise the agnos-only paths the smoke does not reach.** The CA
      hook's multi-path probe and cache (0.6.7), the resume guard (0.6.7) and
      `_path_is_symlink`'s agnos branch (0.6.8) are each `#ifdef`-gated and
      untested. Decide per path: cover it, or record it as knowingly unexercised.
- [ ] **A3 — Iron on archaemenid.** Same run over the r8169 NIC. Parity
      benchmark vs `curl` (latency / RSS / binary size). **The critical path to 1.0.**

### B. Open defects

From the 0.6.6 audit; full detail in [`state.md`](state.md) § *Open defects*.

- [ ] **B1 — `-r` writes through a symlink on AGNOS.** Refused on Linux since
      0.6.8 via `lstat`; agnos has no `lstat` peer and its `sys_stat`#33 follows
      the final symlink, so the check cannot be expressed there. Needs a
      kernel-side `lstat` or an `O_NOFOLLOW` open — **a kernel ask, not a whirl
      change.** File it against agnos.
- [ ] **B2 — `_save_tree` TOCTOU on Linux.** The `lstat` runs before the write.
      Closing the race needs `O_NOFOLLOW` on the write itself, i.e. a private
      open/write path instead of `file_write_all`.
- [ ] **B3 — Retire `_agnos_ca_hook` if it is redundant.** cyrius v6.2.23 fixed
      the `set_ca_system` agnos-ABI defect it works around. A1 did not settle it:
      the hook runs on the HTTPS path that now passes, so it is *reachable*, but
      nothing proves `set_ca_system` would work without it. Needs A2 — a run with
      the hook disabled.

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
- [x] No known unfixed security defect. The 0.6.6 audit's P-1/P-2/P-3 tiers are
      closed; B1/B2 are the residue and are recorded, bounded and understood.
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

**Net:** whirl needs **zero new kernel syscalls**, and the transport lock-down is
closed. The one open kernel ask is **B1** — an `lstat` peer (or `O_NOFOLLOW`), and
that is a filesystem concern, not a network one.

> Cross-refs: [agnos net-syscall arc](https://github.com/MacCracken/agnosticos/blob/main/docs/development/state.md) (#45-#57) · [taar](https://github.com/MacCracken/taar) (substrate) · [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig)
