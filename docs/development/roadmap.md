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
- [x] **B4 — Upstream: cyrius should cache the system trust bundle. Done; hook retired at 0.7.1.**
      cyrius caches it: the bundle is read once per process (v6.5.36), and one parsed
      root set is shared by every ctx (6.6.13). On a real kernel at 6.7.18 the probe
      measured `_agnos_ca_hook` at ~272,720 B per connect (it re-parsed the bundle
      into each ctx) against `set_ca_system`'s ~656 B. So `_agnos_tls_native_connect`
      now calls `_agnos_ca_install` → `tls_native_set_ca_system`, the hook is gone, and
      the probe's `ca-cost-bounded` check (≤ 16 KiB per connect) guards against
      either regression returning.

### C. Substrate — `taar` `tls` / `http` modules

A standing v1.0 criterion: whirl vendors no network primitives locally, and is
the consumer that grows taar's remaining modules. `tcp` shipped at taar 0.2.0 and
whirl runs on it; `tls` and `http` are **still unwritten** (verified: zero
`taar_tls_*` / `taar_http_*` symbols at taar 0.6.2).

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

---

## Moving the cyrius pin to 6.6.6

**Done at 0.6.15.** The pin moved from `6.6.2` straight to `6.6.20`, which includes 6.6.6. Both
*Verify after bumping* steps below were run and pass (CHANGELOG 0.6.15). The PE `O_APPEND` note
stays relevant only if whirl ever adds a Windows target.

No source change needed. One item is latent-but-sharp enough to lead with.

### `output_append` is the `-C` resume path, and on PE it would have eaten the download

`src/output.cyr:44` opens `sys_open(outfile, O_WRONLY | O_APPEND | O_CREAT, 420)`
to append a fetched range onto a partial file after a 206 Partial Content.
**Before 6.6.6 a PE build's `O_APPEND` did not append — it wrote from offset 0.**
A `-C` resume on Windows would therefore have written the resumed bytes over the
*start* of the partial download and destroyed it. That is exactly the failure
whirl's own comment at `src/output.cyr:52-56` already documents for the agnos
read-modify-write arm — "a `-C` resume that ate the download it was resuming" —
arriving by a completely different route.

`src/output.cyr:129` has the matching `O_TRUNC` half
(`O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW`, the non-resume overwrite), plus 8
`file_write_all` sites which open `O_WRONLY|O_CREAT|O_TRUNC` via
`lib/io.cyr:546`: on pre-6.6.6 PE a shorter rewrite kept the old tail.

**This is latent, not live.** whirl declares no Windows target — zero
`CYRIUS_TARGET_WIN` guards, no Windows mention in the README or this roadmap, and
27 `CYRIUS_TARGET_AGNOS` guards marking the two targets it does have (Linux and
agnos). But both of the sites above sit under `#ifndef CYRIUS_TARGET_AGNOS`, i.e.
the arm a PE build would compile, so the exposure appears the day someone builds
`whirl --win`. Pin 6.6.6 before that, not after.

### Two things that look like findings and are not

- **`O_NOFOLLOW` at `src/output.cyr:20` and `:23` is not a redeclaration.** The
  two are `#ifdef CYRIUS_ARCH_AARCH64` / `#ifndef` arms (32768 vs 131072), so
  exactly one is live per build. 6.6.6's "a later redeclaration now wins
  everywhere from program start" flip and the new different-type-co-linked-global
  error do not touch it. The per-arch split and the reasoning above it are right
  as they stand.
- **The `r` global at `src/main.cyr:590` and `src/test.cyr:10`** is the same:
  those are `[build].entry` and `[build].test`, two separate entry points that
  are never co-linked.

### Checked and clear

0 structs (so neither the new different-struct-copy error nor the by-value >8 B
deep-copy change has a site), 0 `async fn`, 0 `operator` fns, 0 `ret2` / `rethi`,
no SIMD intrinsics, no `: cstring` params. 59 globals with no real redeclaration
beyond the two above. No `var` inside a top-level block. No own `vec_*`
definitions, so `assert.cyr`'s new transitive `vec.cyr` include cannot collide. No
raw `SYS_STATFS`. `lib/regression.cyr` is not vendored. `lib/` holds no symlinks
and `cyrius.lock` is present and writable, so 6.6.6's fail-hard `cyrius deps` /
`publish` is a no-op.

The 4 `file_exists` / `file_read_all` sites gain the companion fix: both open
read-only, and 6.6.6 stops PE requesting write access for a read, so on a future
Windows build they would succeed against read-only files and volumes.

### Verify after bumping

1. `cyrius test` plus `tests/whirl.tcyr` and `tests/agnos_probe.cyr` — the latter
   has explicit resume-append assertions on both arms
   (`resume-large-append-ok (host: O_APPEND, no cap)`).
2. A real `-C` resume against a live server on Linux, to confirm nothing shifted
   under the new compiler.

---

## Adopting cmdit (CLI parsing)

**Demand-gated, not a forced sweep.** The 2026-06-25 ecosystem CLI review
([agnosticos `planning/cmdit.md`](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/cmdit.md))
lists whirl as a Tier-1 drop-in, and whirl's `-H` accumulator is what motivated `cmdit_repeat`. This note was read
against cmdit 1.2.6 source on 2026-10-14. Nothing was built or run.

**Hand-rolled today.** The parser is a `streq` if-chain, not stdlib `flags`. `"flags"` is in `[deps] stdlib`, but
there are zero `flags_*` calls outside `lib/`.

- `src/main.cyr:55-60` is `_materialize_argv`. `:423-429` parses and dispatches: `CLI_HELP` → `_print_help`, exit 0;
  `CLI_ERR` → `whirl: usage: whirl [-o FILE] [-L] <url>`, exit 2.
- `src/cli.cyr:104-199` is `cli_parse`. It takes short-only bools `-L -O -r -C -f -i -I`; `-o` and `-X`; `-d` and
  `--data-binary` (one loader, last wins); `-A`/`--user-agent`; and `-H`, repeatable and capped at 16 (`:7`, `:157`).
  `--retry` (long-only) and `-l` (short-only, default 1) go through `_cli_atoi` (`:36-47`), which stops at the first
  non-digit and clamps at 1,000,000.
- `src/cli.cyr:127-128` returns on `-h`/`--help` mid-loop. At `:192-195`, any other token is the URL, including an
  unknown `-x`. A second such token is `CLI_ERR`.
- `src/main.cyr:81-102` is `_print_help`, hand-written and on **stdout**. It has already drifted: `:83`, `:429` and
  `src/cli.cyr:3` each list a different subset of flags. There is no `--version`, although `WHIRL_VERSION` exists
  (`src/version.cyr:9`).

**Site → cmdit:**

- [ ] `cmdit_new("whirl")`. Bools → `cmdit_bool(h, ch, 0, …)`. `-o`, `-X` → `cmdit_str`. Register `-d`/`--data-binary`
  as **one** `cmdit_str(h, 100, "data-binary", …)`: one flag keeps last-wins across both spellings, while two flags
  could not tell which came last. Register `-A`/`--user-agent` the same way.
- [ ] `-H` → `cmdit_repeat(h, 72, 0, …)`. Keep the fail-closed cap in whirl: `cmdit_repeat_count > 16` → error.
  This holds only while 16 stays below cmdit's silent 64-entry list cap. Build the `hdrs` array for
  `src/main.cyr:480-481` from `cmdit_repeat_get`. Run `_cli_load_data` once, after the parse, on `cmdit_get_str`.
- [ ] **Decide** `--retry`/`-l`. `cmdit_int` with `cmdit_range(h, f, 0, 1000000)` rejects (exit 2) the values that
  `_cli_atoi` truncates or clamps (`5x` → 5, `-1` → 0). For identity, register them as `cmdit_str` and keep
  `_cli_atoi`. Making them strict is a separate change.
- [ ] URL → `cmdit_require_positionals_exact(h, 1)`. Map both the missing and the too-many case to today's usage
  line, exit 2.
- [ ] `CMDIT_VERSION` → `cmdit_version(h, WHIRL_VERSION)`, which prints `whirl 0.7.1` on stdout. This is new
  surface with no clash (curl's `-V` is also `--version`). Add its row to `_print_help`.
- [ ] Keep `_print_help` hand-written. `cmdit_help_flags` writes `-X <str>\t…` rows to **stderr** and cannot carry
  whirl's metavars or wrapped lines. Generated help would be a separate, deliberate output change.

**Behaviour that still changes.** These are all still exit 2: an unknown `-x` is `CMDIT_ERR_UNKNOWN` instead of a
URL; `-LO` is `CMDIT_ERR_BUNDLED`; and `-h` no longer short-circuits, so `whirl -h -o` is a missing-value error.
`--` and `--name=value` become accepted. Exit codes 9 and 22 stay whirl's own, because `CMDIT_EXIT_*` covers only
0/1/2 (see D3).

**`cyrius.cyml`:** drop the unused `"flags"`. Keep `"args"` (`src/main.cyr:423-426`) and `"io"`. Add the block
below. At whirl's 6.7.18 pin (since 0.7.1) the matching tag is `1.5.1`, cmdit's latest, which is pinned to 6.7.18 (dig
runs on it). This note was read against 1.2.6, so re-check the calls it names against 1.5.1 first. dig's
0.5.0 records two user-visible changes that came in with 1.3.x: `--help=x` is now a usage error, and unknown-flag errors
now name the token.

```
[deps.cmdit]
git = "https://github.com/MacCracken/cmdit.git"
tag = "1.5.1"
modules = ["dist/cmdit.cyr"]
```

**Tests:** `tests/whirl.tcyr` has no CLI test. Add synthetic-argv cases on `cmdit_parse_argv`, which is pure. Note
that `CLI_HELP` is 1 but `CMDIT_HELP` is 2. `tests/agnos_probe.cyr:34` includes `src/cli.cyr` but calls nothing in
it, so it must still compile after the swap, or the include should go.

**Output-identity bar:** `python3 tests/behavior.py build/whirl` (CI, `.github/workflows/ci.yml:112`) must stay
green. It drives `-r -l 0/1`, `-L -H`, `--retry 2`, `-o`, `-I`, `-i` and `-d @missing` (rc 2). Also byte-compare
`-h` and the usage-error paths against the pre-swap binary.

References: cmdit's [`README.md`](https://github.com/MacCracken/cmdit/blob/main/README.md) (API reference) and
[`docs/development/roadmap.md`](https://github.com/MacCracken/cmdit/blob/main/docs/development/roadmap.md)
(v2 backlog). Worked migrations: kii `src/cli.cyr` and anuenue `src/main.cyr`.
