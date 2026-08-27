# Changelog

All notable changes to whirl are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); versions are [SemVer](https://semver.org/).

## [Unreleased]

## [0.6.9] — 2026-08-27 (QEMU validation on AGNOS — and the defect it found)

**The first execution of the AGNOS arm since 0.6.2.** Six releases of
agnos-affecting change had accumulated behind compile-only verification, and the
run found a real defect on the first attempt: a complete response was being
reported as truncated. Fixed here, with the failure reproduced on Linux so it
stays fixed.

`taar` needed no repair — see *Where the fault was not* below.

### Fixed
- **A complete response is no longer reported as truncated.** whirl read every
  response until the peer closed the socket, even when the response's own
  framing already said it was whole. On Linux that is invisible: `read(2)`
  returns 0 the instant the peer closes. On AGNOS the close is not surfaced
  promptly, so a **complete** chunked body burned taar's full 10 s receive
  deadline, came back as `_TAAR_ERR_TIMEOUT`, and 0.6.6's truncation check
  correctly reported the result as an incomplete response — `exit 9`, no body.
  The response was never incomplete; whirl was asking the socket a question only
  the framing can answer.

  `http_response_complete()` now decides: a chunked body ends at its terminating
  chunk, a `Content-Length` body at its length, and a HEAD response at its
  headers. Only a genuinely close-delimited body (no length, no chunking) still
  ends at EOF. The read loop stops as soon as the framing says the response is
  whole, and the truncation check consults the same predicate.

  **This was reachable on Linux too**, not only AGNOS — masked because whirl
  sends `Connection: close` and most servers honour it. Against a server that
  holds the connection open after a complete body, 0.6.8 stalls **10.4 s** and
  then exits 9 with no output; 0.6.9 returns the body in **0.0 s**, exit 0.
- **Every fetch is faster.** Not waiting for a close it does not need removes a
  wasted round trip per request on Linux and a whole receive deadline per
  request on AGNOS.

### Validated on AGNOS (QEMU + KVM, virtio-net + SLIRP)
Re-staged `rootfs/bin/whirl` — the previously staged binary was **`whirl/0.5.3`
at 13.9 MB**, predating the 0.6.5 shrink and the UA fix; it is now this release
at 2.0 MB.

- **HTTP PASS and HTTPS PASS** on the shipped artifact (version string `0.6.9`,
  2,011,416 bytes): `whirl http://example.com` and `whirl https://example.com`
  each returned the **complete** Example Domain page — full document through
  `</html>`, not merely a recognisable prefix — over the sovereign stack (taar
  DNS via `udp_*`#51-54 → `sock_connect`#47 → `tls_native` over taar → HTTP
  framing), cert-verified. Zero `incomplete response` errors in the run.
- **The pre-fix run is the evidence the fix was needed**: identical harness,
  same kernel, HTTP failed with `incomplete response` / exit 9 while HTTPS
  passed. HTTPS was unaffected because TLS `close_notify` gives `tls_read` a
  clean 0 without needing socket EOF — which is why the plain-HTTP path failed
  alone, and why testing only HTTPS would have declared a broken build good.
- **Harness note:** the smoke's `whirl --help` step reports FAIL in every run.
  It is an input-layer artifact — the xHCI keyboard drops characters, and agnsh
  received `-help` with the `whirl ` prefix lost. The binary demonstrably execs:
  the same run fetched over both schemes.

### Where the fault was **not**
Worth recording, because two plausible suspects were investigated and cleared:
- **taar is correct.** Its AGNOS `taar_tcp_recv` polls `sock_recv`#49 and maps
  the kernel's `-1` (EOF) to a clean `0`, returning `_TAAR_ERR_TIMEOUT` only on
  deadline expiry. That timeout/EOF split, added in taar 0.5.0, is what made the
  defect *visible* rather than silent — before it, a deadline expiry also
  returned 0 and whirl could not tell a stalled read from a finished one. **No
  taar change was made or needed.**
- **The agnos kernel ABI is correct as specified**: `sock_recv`#49 documents
  `bytes / 0 = WOULD_BLOCK / -1 = EOF`. Whether the close is surfaced *promptly*
  is a separate question this run did not settle — and now does not need to,
  since whirl no longer depends on the answer for a framed response.

### Tests
- **130 → 139 assertions.** New group `response-complete`: `Content-Length`
  satisfied vs short, chunked terminated vs unterminated vs mid-chunk,
  close-delimited (never complete without EOF), and HEAD complete at its headers
  while the identical bytes are incomplete for a GET.
- **`tests/behavior.py` 21 → 25 standalone checks.** `[15]` reproduces the AGNOS
  failure on Linux without QEMU: a server that sends a complete body and then
  holds the connection open. Covers chunked, `Content-Length` and `-I` — plus
  the complement, that an **unterminated** chunk stream followed by a close must
  still fail, so the fix cannot be mistaken for weakening the truncation check.
  Paired against 0.6.8 the control reproduces the stall-then-error.

### Still not validated
- **Iron on archaemenid** — unchanged, still open, and now the critical path to 1.0.
- The agnos-only CA-hook cache, resume guard and `_path_is_symlink` branch are
  still **not executed** by the smoke; the harness only drives `--help`, an HTTP
  fetch and an HTTPS fetch. Recorded as roadmap item **A2**. In particular this
  run does *not* settle whether `_agnos_ca_hook` is redundant: the hook runs on
  the HTTPS path that passed, so it is reachable, but nothing here shows
  `set_ca_system` would succeed without it.

## [0.6.8] — 2026-08-27 (P-3 tier: dedup, checked allocation, no silent caps)

The last tier from the 0.6.6 audit. Mostly cleanup — but two items turned out to
have teeth: `alloc()` failure was unchecked at 39 call sites, and two caps were
dropping work silently. Three of the original P-3s (the integer-overflow bounds
on `_url_parse_uint`, `_cli_atoi` and `http_content_length`) already landed in
0.6.7 and are not repeated here.

### Security
- **`-r` refuses to write through a symlink.** A symlink planted in the crawl
  directory redirected a mirrored file anywhere the user could write — the same
  outcome as the 0.6.6 traversal bug by a different route. `_save_tree` now
  `lstat`s the target and refuses if it is a link.
  **Linux only, and deliberately not faked on agnos:** agnos has no `lstat`
  peer, and its path-based `sys_stat`#33 *follows* the final symlink, so the
  check cannot be expressed there. Using `sys_stat` anyway would have answered
  about the target rather than the link — a check that looks like coverage and
  is not. The gap is recorded in `state.md` instead.
  A pre-write `lstat` is also TOCTOU-racy; closing that needs `O_NOFOLLOW` on
  the write itself, which means bypassing `file_write_all`. This removes the
  whole pre-planted-link class, which is the realistic one.

### Fixed — silent caps
- **The crawl no longer drops work silently.** Two separate caps discarded links
  with no signal, so a partial mirror was indistinguishable from a complete one:
  the 64-resource fetch cap, and `links_extract`'s 64-per-page array. Both are
  now counted and reported on stderr. Against a 200-link page whirl now says
  `crawl cap reached (64 resources) — 1 link(s) not followed` **and**
  `136 link(s) past the 64-per-page extractor limit were not seen`; previously
  it said nothing at all. `links_extract` gained `links_found()`, which reports
  the true total while the return value stays clamped to the caller's array —
  changing the return to the unclamped count would have let a caller index past
  the end of its own buffer.

### Hardening
- **`alloc()` failure is checked.** It returns 0 on a request past `ALLOC_MAX`
  or an mmap that cannot extend the heap, and all 39 call sites in `src/` stored
  straight into address 0. They now go through `xalloc`, which fails loudly with
  `whirl: out of memory` and exit 9. There is no useful recovery in a one-shot
  transfer tool, and faulting at address 0 says nothing about the cause.

### Refactor
- **`src/util.cyr`** — a cstr prefix test, a case-insensitive prefix test, a
  case-insensitive string compare, a bounded cstr dup and a two-part concat each
  existed in three or four near-identical copies across `url` / `http` / `crawl`
  / `main`. Now one copy each. Not cosmetic: the case-insensitive compare is
  exactly the kind of routine where one copy gets a bounds fix and the others do
  not — the short-input safety that mattered for credential-header matching in
  0.6.6 had to be reasoned about per copy.
- **`src/version.cyr`** — the version lived inline in the User-Agent, where it
  went stale for six releases before 0.6.5 caught it. It is now a single
  constant, and CI asserts it equals the root `VERSION` file. (Cyrius has no
  build-time define to inject the value, so a mirror plus a gate is the honest
  arrangement — a mirror alone is what created the original problem.)
- **`src/output.cyr` uses named syscalls and constants.** Its Linux arms used
  bare syscall numbers (`syscall(2, …)`, `syscall(1, …)`, `syscall(3, …)`,
  `syscall(8, …)`) and a bare flag word (`1089`) where the rest of whirl uses
  the `sys_*` wrappers and io.cyr's `O_*`. Same instructions; the numbers now
  say what they do and the agnos stat offsets come from the `Stat` enum rather
  than being hardcoded.

### Tests
- **107 → 130 assertions.** New groups: `util` (every shared helper, including
  the short-input cases that must not overrun) and `links-found` (the clamped
  return vs the true total, and that the counter resets per call).
- **`tests/behavior.py` 19 → 21 standalone checks**: the symlink refusal, and
  both crawl caps being reported. Against a 0.6.6 baseline: 27/27 with all six
  0.6.7/0.6.8 controls reproducing and the seven 0.6.6 controls skipped.
- CI gained the `src/version.cyr` vs `VERSION` check.

### Known latent (still open)
- **`-r` writes through a symlink on the AGNOS target** — no `lstat` peer
  exists. Would need a kernel-side `lstat` or an `O_NOFOLLOW` open.
- The pre-write `lstat` on Linux is TOCTOU-racy (above).
- `_agnos_ca_hook` may be redundant since cyrius v6.2.23 fixed the
  `set_ca_system` agnos ABI it works around — retiring it needs a run on real
  agnos, not a code read.
- The 64-resource crawl cap and 64-per-page link cap are now *reported* but not
  configurable; there is no flag to raise them.

### Not validated here
- **AGNOS runtime**, as with 0.6.6 and 0.6.7. This release changes `output.cyr`
  on both arms and adds an agnos-only branch to `_path_is_symlink`; both are
  compile-verified only. The `output.cyr` syscall rewrite is behaviour-preserving
  by construction but is exactly the kind of change a QEMU run should confirm.
- The behavioural suite runs over plain HTTP against local servers; the TLS arm
  is covered only by live fetches and a fail-closed check.

## [0.6.7] — 2026-08-27 (P-2 tier: origin confinement, port correctness, overflow hardening)

The second tier from the 0.6.6 audit — the "Known latent" list that release
recorded, plus its remaining P-2 findings. One is security-relevant (a cleartext
downgrade a hostile page could force); the rest are correctness, data-loss and
hardening. Two refactors close out the tier, both motivated by defects rather
than taste. Verified the same way as 0.6.6: paired against an older binary that
reproduces each defect first.

### Security
- **The crawl is confined to an ORIGIN, not a host.** `-r` compared hostnames
  only, so a page fetched over `https` could point at same-host `http://` links
  and whirl would follow them **in cleartext** — a downgrade the page controls,
  on every resource it names. It could also wander from `:8443` onto `:80`.
  Scheme, host and port must now all match the starting URL; a link that fails
  is skipped and named on stderr.
- **`robots.txt` is fetched from the port being crawled**, not from 80/443. On a
  non-default port whirl consulted a *different origin's* policy — or, where
  nothing was listening, none at all — and then crawled as though unrestricted.

### Fixed
- **`-r` works on non-default ports at all.** `_resolve_link` built resolved
  URLs from the bare hostname, dropping the port, so on `:8080` every relative
  and root-relative link resolved to `:80`. Combined with the same-host check
  this made recursive fetch silently useless off the default ports. It now
  builds the authority with `_authority`, the same helper 0.6.6 added for
  `Location:` resolution.
- **`Host:` carries a non-default port** (RFC 9110 §7.2). A bare host made
  virtual-host routing on a non-default port resolve to the wrong site.
- **`-i` emits a decoded body.** With `-i` the whole receive buffer was written
  verbatim, so every chunked response carried raw hex chunk framing into stdout
  — and into the `-o` file. Headers and decoded body are now joined and written
  **once**: `output_write` truncates a file sink on each call, so the obvious
  two-call fix would have left `-i -o` containing only the body. There is a
  regression check for exactly that.
- **`--retry` fires on a zero-byte response.** The retry loop treated `total >= 0`
  as success, and a zero-byte read is `total == 0` — so `--retry` never fired on
  a peer that accepted the connection and sent nothing, which is precisely the
  transient failure it exists for. No valid HTTP response is empty.
- **An oversized request is no longer sent malformed.** `_http_puts` clamps at
  `bufmax` and returns as though it wrote, so a request that did not fit (many
  `-H` headers, a long crawl path) went out with a half-written header line and
  no terminating CRLFCRLF, and no caller could tell. `http_build_request` now
  returns `HTTP_REQ_TOOBIG`; all three call sites check it.
- **AGNOS `-C` resume no longer destroys the file it is resuming.** The agnos
  append path read-modify-writes (no `O_APPEND` in the frozen FS surface) with a
  1 MiB read cap, so a *larger* file was read to 1 MiB and written back at
  1 MiB + len — silently discarding everything past the cap. It now refuses, and
  the caller reports it. (Linux uses real `O_APPEND` and was never affected.)

### Hardening
- **`_agnos_ca_hook` no longer leaks 1 MiB per TLS connect.** It allocated a
  fresh 1 MiB bundle buffer on every connection against a bump allocator with no
  `free` — ~1 MiB per redirect hop and per crawled resource. The bundle is now
  loaded once and cached. It also checks the allocation instead of storing into
  address 0 on failure, and probes the four common trust-store layouts rather
  than only `/etc/ssl/cert.pem` (an image with a Debian/RHEL layout had no roots
  at all, so every handshake failed closed — correct, but for the wrong reason).
- **Integer-overflow bounds on the three numeric parsers.** `_url_parse_uint`
  rejects more than 10 digits — a long run wrapped i64 and could land back
  inside 1..65535, defeating the port range check. `http_content_length` rejects
  more than 18 digits, since a wrapped-negative length would sail through the
  0.6.6 "body shorter than promised" comparison. `_cli_atoi` clamps, so a
  wrapped-negative `--retry` cannot silently disable retries or `-l` recursion.

### Refactor
- **`src/crawl.cyr`** — link resolution, path confinement and robots.txt parsing
  carved out of `main.cyr` (which drops ~230 lines). Not tidying: this is where
  the 0.6.6 security fixes live, and while it sat inside `main.cyr` the only way
  to exercise any of it was end-to-end through a real binary and a real server.
  It is now reachable from `tests/whirl.tcyr`, which is what took the unit suite
  from 69 to 107 assertions. `_save_tree`'s pure half became `tree_relpath`, so
  the confinement boundary itself is directly testable.
- **One response read loop, not two.** `transport_fetch` and
  `transport_fetch_tls` each carried a copy, and 0.6.6 had to fix the same
  error-vs-EOF bug in both. `_transport_read_all` now holds the policy once. It
  selects the reader with a **direct call on a mode flag rather than a function
  pointer** — the AGNOS arm has no executed test coverage, so its hot path stays
  on the mechanism it already ships.

### Tests
- **69 → 107 assertions** in `tests/whirl.tcyr`. New groups: `tree-relpath` (the
  confinement boundary, including the `//tmp/x` form that defeated the original
  one-slash strip, and `..hidden` which must *not* be treated as traversal),
  `authority`, `abs-location`, `same-origin` and `resolve-link-port`.
- **`tests/behavior.py` 12 → 19 standalone checks**, covering origin
  confinement, crawling on a non-default port, the `Host` port, `-i` decoding
  (including `-i -o`), and `--retry` on an empty response.
- **Controls are now version-aware.** Each is tagged with the release that fixed
  its defect, and the baseline's version is read off the `User-Agent` it puts on
  the wire. A control whose fix the baseline already has is *skipped* rather
  than failed — without this, every future release would report phantom failures
  for every fix older than its baseline. Against 0.6.6: 23/23 with 7 skipped.
  Against a pre-0.6.6 binary: 30/30 with all 11 controls reproducing.

### Known latent (still open, deliberately)
- `_save_tree` follows symlinks and truncates pre-existing files. Fixing it
  properly needs `O_NOFOLLOW` (or an `lstat` pre-check) on Linux and has no
  clean equivalent in the frozen agnos FS surface, so it would mean a behavioural
  split between targets — more than a hardening cut should take on unannounced.
- `alloc()` failure is still unchecked at most `src/` call sites. The CA hook is
  now guarded because it had a concrete NULL-write; a general sweep is its own
  change with its own failure-mode design.
- The crawl's 64-resource cap, dedup and depth bound are unchanged.

### Not validated here
- **AGNOS runtime**, again. This release touches the shared read loop, the
  agnos-only CA hook and the agnos-only resume path — the last two are
  `#ifdef CYRIUS_TARGET_AGNOS` and are therefore **compile-verified only**; no
  test in this repo executes them. The resume guard and the CA cache in
  particular want a QEMU run against a re-staged rootfs before being trusted.
- Everything in the behavioral suite runs over plain HTTP against local servers.
  The TLS arm is covered only by live fetches and a fail-closed check.

## [0.6.6] — 2026-08-27 (P-1 security + correctness sweep; CI compiles the AGNOS arm)

A hardening cut. A multi-lens audit of `src/` produced findings that were then
adversarially re-checked; the survivors are fixed here. **Three are genuine
remote-attacker security defects** — one of them a remote arbitrary file write.
Every fix below was proven by running the 0.6.5 binary against a local test
server to reproduce the defect, then the 0.6.6 binary against the same server to
show it closed (17 paired checks, plus positive controls that the fixes do not
over-block).

### Security — fixed
- **Remote arbitrary file write in `-r` (path traversal).** `_resolve_link`
  returned absolute same-host links *verbatim*, skipping the `links_path_normalize`
  applied to relative ones, and `_save_tree` sanitized the result only by
  stripping **one** leading `/`. A crawled page containing
  `<a href="http://host/../../../../tmp/x">` — or the `//tmp/x` variant, which
  survived one slash-strip as the absolute path `/tmp/x` — made whirl create or
  truncate files anywhere the user could write. **Reproduced against 0.6.5**,
  which wrote `/tmp/whirl_pwned_marker2` outside the crawl directory.
  Confinement now lives at `_save_tree`, the single point that touches the
  filesystem: any `..` segment is refused outright and *all* leading slashes are
  stripped, so the write is always relative to cwd regardless of caller.
- **Request splitting via an attacker-controlled `Location` / `href`.**
  `_dup_location` stops only at CR, `url_parse` copied the path through to NUL
  without validation, and `http_build_request` writes host and path into the
  request line **unescaped** — so a redirect carrying bare LFs spliced
  attacker-chosen headers, or a whole second request, into the request whirl
  then sent to the *redirect target*. Now rejected in `url_parse`: controls,
  space and DEL are refused in both host and path. One choke point covers the
  command line, `Location:` and crawled hrefs alike. High bytes (≥ 128) still
  pass, so UTF-8 / IDN paths are unaffected.
- **Credential replay across origins on redirect.** `-H 'Authorization: …'`
  (and `Cookie`, `Proxy-Authorization`) was re-sent verbatim to whatever host a
  `Location:` named, so any site whirl was given a credential for could harvest
  it by redirecting to a host it controls. Redirects that change scheme, host
  (case-insensitively) or port now drop credential headers. Same-origin hops and
  non-redirect requests keep them — verified both ways.

### Fixed — silent wrong results
- **A truncated transfer no longer reports success.** Both read loops folded
  `n < 0` into the same branch as `n == 0`, so a timeout, RST or full buffer was
  indistinguishable from a clean close: whirl wrote a short file and exited 0.
  The loops now separate the two, and — more importantly — **every** response is
  checked against its `Content-Length`, since a server that sends a short body
  and then closes *cleanly* is the most common truncation of all and no
  error-flag scheme would catch it. `HEAD`, 204 and 304 are correctly exempt.
- **Response cap 256 KB → 1 MiB, and exceeding it is now an error.** This is the
  root cause of the reported `whirl -L https://github.com` → `malformed chunked
  body` (exit 9): github.com's 575 KB chunked body was cut mid-chunk at 256 KB,
  and the dechunker reported the *symptom*. Now returns the full 574,917-byte
  body, exit 0; a body over the new cap fails loudly instead of silently.
- **`-r` wrote raw chunk framing to disk.** The crawl saved `rbuf` verbatim with
  no dechunking, so every chunked resource was mirrored corrupt (`5\r\nHELLO…`)
  — and link extraction then ran over the corrupt bytes. It now decodes first,
  clamps to `Content-Length`, and extracts links from the decoded body.
- **`-r` mirrored error pages as though they were the resource.** A 404 or 500
  body was written under the requested name. Non-2xx is now skipped and reported.
- **A failed `-o` write exited 0.** `output_write`'s error return was discarded
  at every call site in `_emit_body`. Now checked; a write failure exits 9.
- **`-d @missing-file` silently became a bodyless GET** with exit 0, and
  **`-d @file` over the cap was truncated and sent under a `Content-Length` that
  matched the truncated length** — so the server stored a short body and both
  ends reported success. Both are now hard errors (exit 2) with distinct
  messages; the body cap is 1 MiB with one byte of read headroom to tell "full"
  from "too large".
- **`-L` now follows a relative `Location:`.** RFC 9110 permits one and real
  sites send bare `/docs/`; `url_parse` rejects a schemeless URL, so `-L`
  silently stopped following and exited 0 with the redirect stub as the result.
  Relative, root-relative and protocol-relative forms all resolve now — and the
  resolver **keeps the port**, which the existing `_resolve_link` drops.

### Hardening
- **`taar_tcp_send` partial writes.** The return was discarded and never looped,
  though both backends document a short write (`sock_send`#48 on agnos returns
  "bytes sent (≤ len)"). Now a bounded send-all that tolerates a transient `0`
  with a spin cap, matching taar's own `_taar_dns_tcp_send_all`. The TLS path
  was already correct — `tls_write` / `tls_native_write` send-all internally —
  so only its return code is checked, not re-looped.

### CI
- **CI now compiles and selects the AGNOS arm.** There was no `--agnos` step, so
  a hard break inside an agnos-only block landed green: lint, the Linux build,
  the ELF check and `cyrius test` all pass without ever touching it (`cyrius
  test` builds a host binary, so every assertion runs the Linux arm). The step
  builds with the same `CYRIUS_DCE=1` flags as the Linux build and `cmp`s the
  two images — identical output means the `#ifdef` arm was not taken and fails
  the job. Proves compilation and selection only; nothing executes it.
- **CI runs the new behavioral suite** against the built binary, so a regression
  in any of this release's security fixes fails the job rather than shipping.

### Tests
- **New `tests/behavior.py` — an end-to-end behavioral suite, now checked in and
  gated in CI.** `tests/whirl.tcyr` covers pure logic, so none of the defects
  above were reachable from it: they live in the interaction between the CLI,
  the transport and the filesystem, and need a real binary with a real working
  directory and a server that answers adversarially. Every fix in this release
  is asserted there.
  - Run standalone (`python3 tests/behavior.py build/whirl`) it checks the 12
    assertions that must hold for the build to ship — and it has teeth: run
    against the 0.6.5 binary, 7 of the 12 fail and it exits 1.
  - Run with `--baseline <pre-0.6.6 binary>` each security check becomes a
    **paired** test that first reproduces the defect on the old binary (19
    checks). A failed control then means the check has stopped exercising the
    vulnerable path — a silent false pass — rather than a broken build.
  - Python because Cyrius has no test-harness/scripting spinoff yet; it should
    move over when one exists. Nothing in it needs Python specifically.
- **52 → 69 assertions** in `tests/whirl.tcyr`. New groups:
  `url-reject-injection` (CRLF, LF, tab and space refused in host and path;
  ordinary and percent-encoded URLs still accepted, so the check cannot
  over-reject) and `credential-headers` (case-insensitive matching,
  non-credentials not matched, and short/empty header lines that must not
  overrun).
- `tests/whirl.tcyr` now exits via `syscall(SYS_EXIT, …)` rather than a bare
  `syscall(60, …)`, matching the project idiom.

### Known latent (found and confirmed, deliberately not fixed here)
- The crawl has no **scheme** confinement: an `https` crawl follows same-host
  `http://` links over cleartext. Same-host is enforced; same-scheme is not.
- `robots.txt` is fetched from port 80/443 rather than the port being crawled,
  and relative links lose a non-default `:port` — `-r` is effectively unusable
  against a non-default port. `_resolve_link` needs the `_authority` treatment
  this release gave `_abs_location`.
- `_save_tree` follows symlinks and truncates pre-existing files (`O_CREAT|O_TRUNC`).
- `http_build_request` truncates an oversized request silently; no caller can
  detect it. `_http_puts` clamps at `bufmax` and returns as if it wrote.
- `_agnos_ca_hook` allocates 1 MiB per TLS connect and never reclaims it (bump
  allocator), and probes only `/etc/ssl/cert.pem`. It may also now be redundant
  — cyrius v6.2.23 fixed the `set_ca_system` agnos ABI it works around — but
  removing it needs a run on real agnos.
- `alloc()` failure is unchecked at every call site in `src/`.
- `transport_fetch` and `transport_fetch_tls` remain near-duplicates; this
  release had to fix the same read-loop bug in both.

### Not validated here
- **AGNOS runtime.** The new CI step and the local `--agnos` build are
  **compile-only**. Several fixes touch code paths shared with the agnos arm
  (`transport.cyr`'s read loops and send-all, `output.cyr`'s callers); a QEMU
  smoke against a re-staged 0.6.6 rootfs is still owed, and iron on archaemenid
  remains open.
- The behavioral suite runs against local test servers over plain HTTP; the
  fixes are transport-agnostic, but the TLS arm was exercised only by live
  `https://example.com` / `https://github.com` fetches and a fail-closed check
  against a local self-signed server.

## [0.6.5] — 2026-08-26 (toolchain 6.5.35; taar 0.5.0; vendored stdlib re-cut)

Housekeeping cut: toolchain, substrate and vendored stdlib all move to the
family-current versions. **No transport, HTTP or CLI logic changed** — the only
source edit is the default User-Agent string. Both targets build, the suite is
green, and the Linux binary drops ~86%.

### Changed
- **Toolchain pin `6.4.25` → `6.5.35`** — realigns with the family (`yo` and
  `taar` are both on 6.5.35) and clears the `manifest-pin: 6.4.25 (drift —
  wrapper is 6.5.35)` warning the local toolchain has been emitting. Required
  **zero** source changes: `src/` builds untouched on both targets. Note this is
  a deliberate, substantively-motivated bump, not drift-chasing — the 6.2.6 →
  6.4.25 move at 0.6.3 set the same precedent.
- **`[deps.taar]` `0.3.1` → `0.5.0`.** The load-bearing dep edit: `path =
  "../taar"` wins locally, so local builds were already on 0.5.0 while **CI —
  which has no `../taar` sibling — was still resolving 0.3.1**. What the shipped
  artifact gains:
  - **Fail-closed DNS query-ID entropy.** taar 0.3.1's Linux
    `_taar_plat_random_u16` opened `/dev/urandom` and *discarded the read
    result*, so a short or failed read left the query ID as uninitialised stack
    (RFC 5452). 0.5.0 zero-inits, uses `sys_getrandom`, checks the count, and
    fails the resolve rather than querying with a guessable ID. whirl hits this
    on every hostname fetch (`src/transport.cyr` `transport_fetch` /
    `transport_fetch_tls`).
  - RFC 5452 reply acceptance, TC→TCP-53 fallback (from taar 0.4.0), empty-host
    rejection, and an IPv4-literal fast path that skips DNS entirely.
  - Linux socket primitives moved off hardcoded x86_64 syscall numbers onto
    arch-dispatched `sys_*` wrappers (`sys_openat` in place of x86-only
    `open(2)`) — aarch64 correctness for free.
- **Default User-Agent `whirl/0.5.3` → `whirl/0.6.5`** (`src/http.cyr`). It had
  been stale since 0.5.3 and misreported the version on the wire. `-A` /
  `--user-agent` still overrides it; no test asserts the value.
- **Vendored stdlib snapshot re-cut against 6.5.35.** `lib/` was rebuilt from
  scratch (`rm -rf lib && cyrius lib sync && cyrius deps`) rather than overlaid,
  which prunes 37 undeclared modules that had accumulated from the 6.2.x era —
  including `lib/agnosys.cyr`, which exists in no 6.4.x or 6.5.x snapshot at
  all. `cyrius.lock` 98 → 61 entries; the `./lib/ shadows version-pinned …`
  warning (9 stale modules: `sandhi`, `mabda`, `sankoch`, `patra`, `yukti`,
  `vani`, `sakshi`, `ganita`, `niyama`) is gone. `lib/` is gitignored, so only
  the lock appears in the diff.

### Fixed (inherited from the toolchain, no whirl code change)
- **Silent HTTPS body truncation on the `tls_native` backend.** 6.4.25's
  `tls_native_read` returned `TLS_ERR_BUFFER_FULL` — a *negative* — when a
  decrypted record exceeded the caller's remaining buffer. whirl's read loop
  treats any `n <= 0` as clean EOF (`src/transport.cyr`), so a truncated body
  was reported as a **successful** fetch. Reachable as the 256 KB response cap
  fills and the remaining ask drops below one 16 KB record. 6.5.35 adds a ctx
  read-hold (`TLS_CTX_OFF_READ_HOLD*`) and returns a partial read instead.
  Applies wherever `tls_native` is the active backend — the AGNOS path always
  (it calls `tls_native_*` directly since 0.6.3), and the Linux path whenever
  libssl.so.3 is absent and the facade falls back to native.

### Performance
- **Linux binary 13,935,360 → 2,013,744 bytes (−85.6%)**; static data
  12,980,976 → 726,752 (−94.4%). AGNOS binary 2,002,352 bytes. Attributed to
  the **toolchain pin alone**, verified by experiment: holding `lib/` and
  `cyrius.lock` fixed at the 0.6.4 snapshot and changing only the pin reproduces
  2,013,744 bytes exactly. The `lib/` prune is hygiene, not the cause.

### Validated
- `cyrius build` (Linux) and `cyrius build --agnos` both `OK`; the two images
  differ, so the `#ifdef CYRIUS_TARGET_AGNOS` arm is genuinely taken.
- `cyrius test` → **52 passed, 0 failed** (13 groups: url, http framing, links,
  path-normalize).
- Live over the new stack: `http://example.com` and `https://example.com` both
  return `HTTP/1.1 200 OK`, exit 0.
- **TLS still fails closed**: a *reachable* local `openssl s_server` presenting a
  self-signed cert on `127.0.0.1:18443` is rejected (exit 9), while
  `https://example.com` succeeds. (The usual `*.badssl.com` probes are not
  reachable from this network — a valid-cert control against `badssl.com` also
  fails — so they were not used as evidence.)

### Not validated here
- **AGNOS runtime.** Both `--agnos` results above are **compile-only**; the
  `#ifdef CYRIUS_TARGET_AGNOS` arms are not executed. The QEMU smoke needs a
  re-run against a re-staged 0.6.5 `rootfs/bin/whirl`.
- **CI on a fresh checkout.** Every local build resolves taar through
  `path = "../taar"`; only a real CI run exercises the `git`+`tag` path this
  release fixes.
- **taar's TC→TCP-53 fallback on AGNOS** — no executed coverage anywhere; the
  QEMU smoke will not reach it (example.com's A RRset never sets TC).
- **Iron on archaemenid** — still open, unchanged by this cut.

### Known latent (found while verifying; deliberately not fixed here)
- **CI never compiles the AGNOS arm.** `.github/workflows/` has no `--agnos`
  step, so a hard break inside an agnos-only block lands green. `yo` gates this;
  whirl should adopt it in its own commit.
- `transport_fetch`'s `taar_tcp_send(fd, req, reqlen)` discards the return and
  never loops on a partial write. Reachable with a large `-d @file` body; real
  exposure is the AGNOS backend (`sock_send`#48 may accept `< len`). The TLS
  path is unaffected — `tls_write` / `tls_native_write` already send-all.
- `_agnos_ca_hook` (`src/transport.cyr`) may now be redundant: the upstream
  `tls_native_set_ca_system` agnos-ABI defect it works around was fixed at
  cyrius v6.2.23 and that fix is in the vendored snapshot. Needs its own
  investigation on real agnos before removal.
- `-L https://github.com` fails with `whirl: malformed chunked body` (exit 9) on
  both a taar-0.3.1 baseline and this build — pre-existing, unrelated.

## [0.6.4] — 2026-07-08 (validation re-cut — HTTPS confirmed under mirshi)

### Validated
- **HTTPS under mirshi confirmed working** — no whirl code change vs 0.6.3. The transient
  HTTPS-under-mirshi segfault seen during 0.6.3 bring-up was root-caused to a NULL-deref in
  the **stale pre-6.4.25 sigil** snapshot whirl's old vendored `lib/` carried (heap
  crypto-scratch `mmap` returned 0, zeroed unchecked → SIGSEGV `faultaddr=0`). The 6.4.25
  sigil (static crypto banks) already fixes it. Confirmed: whirl HTTPS fetches over **both**
  mirshi (`--root <ca> --net-allow`) and the real agnos kernel. No mirshi patch / cyrius
  issue required.

## [0.6.3] — 2026-07-08 (AGNOS build under cyrius 6.4.x — fdlopen → tls_native; toolchain 6.4.25)

### Changed
- **Toolchain pin `6.2.6` → `6.4.25`** (latest cyrius). Clears the stale-pin drift; the
  build fix below is mandated by 6.4.x's stricter reachable-undef gate — 6.2.6 tolerated
  the unreachable `fdlopen_*` refs, 6.4.x refuses to emit a binary with them.
- **stdlib list gains `dynlib` + `fdlopen`.** cyrius 6.4.x resolves the `tls` facade's
  libssl.so.3-bridge `fdlopen_*` refs from the explicit include list (no longer
  auto-pulled via tls's transitive requires), so the **Linux** build needs them named or
  it fails reachable-undef. On `--agnos` they compile (Linux path is
  `#ifdef CYRIUS_TARGET_LINUX`-gated) and stay unreachable (native TLS path) → DCE'd.

### Fixed — AGNOS build under cyrius 6.4.x (fdlopen reachable-undef)
- **`cyrius build --agnos` no longer fails on `fdlopen_*` reachable-undef.** On the
  6.4.x toolchain the `lib/tls.cyr` facade's `tls_connect*` verbs pull in
  `tls_connect_alloc → _tls_init → fdlopen_init_full` — the libssl.so.3 dynamic-loader
  bridge (fdlopen bootstraps ld.so to `dlopen` glibc). AGNOS binaries are STATIC (no
  ld.so, no fdlopen), so those symbols were both unbuildable (`refusing to emit binary
  with 4 reachable undefined function(s)`) and structurally unusable. The agnos HTTPS
  path now calls the sovereign `tls_native_*` API directly (`_agnos_tls_native_connect`:
  `tls_native_new_client` → CA roots via the agnos-ABI `_agnos_ca_hook` →
  `tls_native_connect`, chain+hostname fail-closed), returning a native-backed shim so
  the shared `tls_read/write/close` still drive it. fdlopen is now unreachable on
  `--agnos` and DCE-eliminated; the Linux path is byte-identical (all changes are
  `#ifdef CYRIUS_TARGET_AGNOS`-guarded). Rounds out the net-tools (yo + dig) in the
  agnos-dev docker image.

### Validated on AGNOS (QEMU + KVM real kernel, virtio-net + SLIRP)
- **HTTP and HTTPS both PASS** with the rebuilt binary — `whirl https://example.com`
  fetched the real Example Domain page (tls_native over taar, cert-verified) over the
  sovereign stack. Also runs under mirshi (`--net-allow`): HTTP over the emulated net
  band PASS. (HTTPS *under mirshi* segfaults inside cyrius `tls_native_connect` — a
  mirshi net-band emulation gap, NOT a whirl issue; the identical binary does HTTPS
  fine on the real kernel.)

## [0.6.2] — 2026-06-23 (AGNOS QEMU validation + HTTPS CA fix + kernel-leased resolver)

### Changed
- **AGNOS DNS resolution prefers the kernel-leased on-subnet resolver** (via **taar
  0.3.1**, dep bumped 0.3.0 → 0.3.1). `taar_resolve_ipv4` now consults the new agnos
  `net_config(3)`#61 syscall (the DHCP option-6 resolver) before the off-subnet
  `8.8.8.8` fallback. The off-subnet fallback needs working gateway routing the kernel
  can't guarantee on real iron — it froze `whirl https://google.com` on archaemenid
  (the binary exec'd and resolved into the void). The leased resolver is on-subnet +
  directly reachable. Linux is unchanged. **Requires agnos ≥ 1.45.16.**

### Validated on AGNOS (QEMU + KVM, virtio-net + SLIRP)
- **whirl runs on agnos end-to-end** — booted a production kernel with the staged
  rootfs (`/bin/whirl`) and fetched **real example.com pages over the sovereign
  stack**: exec-from-disk (1.1 MB binary, ring 3) → taar DNS (`udp_*`#51-54) →
  `sock_connect`#47 → HTTP framing → body. **HTTP and HTTPS both PASS.** Harness:
  `agnos/scripts/whirl-smoke.sh`.

### Fixed — HTTPS on AGNOS (the 0.6.1 path didn't actually work)
- 0.6.1 claimed HTTPS-on-agnos "correct-by-construction"; QEMU testing proved it
  failed: cyrius's `tls_native_set_ca_system` opens the CA bundle with the **Linux**
  `sys_open(path, flags, mode)` ABI, but agnos `sys_open` is `(name, namelen, flags)`
  → `namelen=0` → the trust store never loads → fail-closed handshake. (A verify-none
  handshake completes fine on agnos, isolating the fault to trust-root loading — the
  `set_transport`-over-taar path itself is correct.)
- **`_agnos_ca_hook`** (`src/transport.cyr`, `#ifdef CYRIUS_TARGET_AGNOS`): loads the
  staged `/etc/ssl/cert.pem` with the correct agnos ABI and installs it via
  `tls_native_set_ca_bundle` through `tls_connect_with_ctx_hook` — fail-closed cert +
  hostname verification now passes on agnos. Stopgap until the cyrius fix lands (filed
  `cyrius/docs/development/issues/2026-06-18-tls-native-set-ca-system-agnos-sys-open-abi.md`).
- Requires the CA bundle staged on the agnos-fs — wired into `agnos/scripts/stage-tools.sh`.
- Linux unchanged (the `#ifndef` path still uses plain `tls_connect`; HTTPS regression green).

## [0.6.1] — 2026-06-18 — HTTPS on AGNOS (tls_native transport hook)

Closes the `https://` path on agnos. On Linux, tls_native does raw `sys_read`/
`sys_write` on the real socket fd — but taar's agnos TCP "fd" is a sentinel (the
real conn_id lives in a taar module global), so the default path can't route.

### Added
- **`tls_native_set_transport(&taar_tcp_recv, &taar_tcp_send, 0)`** in
  `transport_fetch_tls`, under `#ifdef CYRIUS_TARGET_AGNOS` — installs taar's TCP
  recv/send as tls_native's transport vtable (the v6.2.4 "Option C" hook). The
  per-conn handle whirl passes to `tls_connect` is forwarded to the leaf helpers,
  but taar's recv/send read the active conn from their own global, so any handle
  works. `now_fn = 0` keeps the agnos default (`_tn_now_unix` → `sys_time_unix`#46)
  for cert-window validation — **fail-closed cert + hostname verification is
  unchanged on agnos**.

### Notes
- Zero new cyrius/kernel surface: `tls_native_set_transport` (cyrius v6.2.4) and
  `sys_time_unix`#46 (v6.2.3) are both ≤ the pinned 6.2.6. Linux is untouched
  (the `#ifdef` is agnos-only; the default raw-fd path still serves Linux).

### Verified
- **Linux**: HTTPS regression unchanged (example.com fetched; `expired.badssl.com`
  fail-closed). 52 unit assertions green.
- **AGNOS**: compiles clean — `tls_native_set_transport` + `&taar_tcp_recv` /
  `&taar_tcp_send` resolve. End-to-end `https://` is correct-by-construction
  (transport vtable + matching read/write signatures + agnos cert clock); iron
  validation on archaemenid is 0.6.2.

## [0.6.0] — 2026-06-18 — HTTP on AGNOS (sovereign backend)

whirl's plain-HTTP path now runs over the **AGNOS kernel's own network stack** —
no POSIX `socket()`, no Linux syscall numbers anywhere in the agnos build. The
transport rides **taar 0.3.0**'s sovereign backend; the rest of whirl's I/O was
made target-agnostic so the whole tool compiles + behaves correctly on agnos.

### Added
- **`[deps.taar]` → 0.3.0** — taar's AGNOS backend (TCP over `sock_connect`#47 /
  `sock_send`#48 / `sock_recv`#49 / `sock_close`#50; DNS over `udp_*`#51-54;
  entropy via `getrandom`#45). `transport_fetch` needed **zero** changes — the
  `taar_tcp_*` / `taar_resolve_ipv4` API is identical across Linux and agnos.
- **AGNOS build target** — `CYRIUS_TARGET_AGNOS=1 cyrius build src/main.cyr`
  emits an agnos ring-3 binary (1.10 MB). The full stack (HTTP framing, links,
  robots, tls) compiles for agnos.

### Changed (portable I/O — correctness on agnos)
- `_puts` / `_eputs` / `_eput_int` now use the **`sys_write`** wrapper (raw
  `syscall(1,…)` is Linux-only; agnos's syscall ABI differs — `1` isn't `write`).
- `_sleep_ms` → chrono **`sleep_ms`** (was raw `nanosleep`#35).
- `-d @file` → portable **`file_read_all`** (io); `-d @-` stdin + `--retry` read
  via the **`sys_read`** wrapper.
- `_mkdir` and `output_file_size` carry a minimal `#ifdef CYRIUS_TARGET_AGNOS`
  branch (the `sys_mkdir` / `sys_stat` signatures differ; agnos size via
  `sys_stat` STAT_SIZE). `-C` append: Linux true `O_APPEND`; agnos read-modify-
  write (no `O_APPEND`/flock in the frozen FS surface; ≤1 MB resume cap there).

### Verified
- **Linux**: build + **52** unit assertions + live regression (HTTP, HTTPS w/
  cert verify, `-C` resume → reassembled, `-d @file`, `--retry`) — no behavior
  change from the portable-I/O refactor.
- **AGNOS**: compiles clean (no undefined-function warnings; `sys_sock_*` /
  `sys_udp_*` / `sys_getrandom` / `sys_stat` / `sys_mkdir` resolve). Iron
  validation on archaemenid (`whirl http://… ` over the sovereign stack) is the
  0.6.x roadmap step.

### Still ahead
- **0.6.1**: HTTPS on agnos — the taar TCP "fd" is a sentinel there, so
  tls_native's default raw-fd read/write won't route; wire
  `tls_native_set_transport(read, write, now)` → `taar_tcp_recv`/`send`.
- Iron burn + curl parity benchmark (latency / RSS / binary size).

## [0.5.3] — 2026-06-18 — polish (curl/wget flag round-out)

### Added
- **`-A UA` / `--user-agent UA`** — override the `User-Agent` (default `whirl/<ver>`). New `http_set_user_agent`.
- **`-i`** — include the response status line + headers in the output (verbatim response).
- **`-I`** — HEAD request (headers only; method override + implies header output).
- **`-f`** — fail on HTTP ≥ 400: suppress the body, report `whirl: HTTP <code>`, exit **22** (curl-compatible).
- **`-d @file` / `-d @-`** — read the request body from a file or stdin (≤ 256 KB). **`--data-binary`** added (same loader, raw body).
- **robots.txt `Allow:` precedence** — `-r` now parses `Allow:` as well as `Disallow:` and applies RFC 9309 longest-match specificity (a tie resolves to Allow). New `_robots_dup`; `_robots_parse`/`_robots_load`/`_robots_blocked` carry a parallel allow/disallow flag array.

### Validated
- Live (postman-echo / example.com): `-A` echoed; `-i` emitted status+headers; `-I` returned headers only; `-f` on a 404 → exit 22, 0 body bytes; `-d @file` and `-d @-` echoed the body. **Allow precedence proven on `en.wikipedia.org`** — `/w/load.php?…` saved (matches the longer `Allow: /w/load.php?`) while `/w/index.php?…` and `/w/rest.php/…` blocked (only `Disallow: /w/`). 52 unit assertions green.

## [0.5.2] — 2026-06-18 — resume (-C)

### Added
- **`-C`** — resume a partial download. When the `-o`/`-O` output file already exists, whirl sends `Range: bytes=<size>-` and:
  - **206 Partial Content** → appends the remainder (`output_append`),
  - **200 OK** (server ignores Range) → overwrites with the full body,
  - **416 Range Not Satisfiable** → reports "already complete".
  Resume applies to the first hop only (a redirect falls back to a full GET). New `output_file_size` (`lseek` SEEK_END) + `_build_range_header`.
- Live-validated: example.com 559 B → truncated to 300 B → `-C` → "resumed at 300 bytes" → reassembled to 559 B (valid tail); `Range: bytes=N-` confirmed sent via postman-echo; 200-overwrite path confirmed.

## [0.5.1] — 2026-06-18 — -r niceties

### Added / Changed
- **Directory-tree mirroring** — `-r` saves each resource to a path tree under cwd (`/docs/g.html` → `docs/g.html`, creating dirs; `/` or `/d/` → `…/index.html`) instead of flat `a_b.html` names.
- **`../` / `.` path normalization** (RFC 3986 §5.2.4) — new `links_path_normalize`; relative + root-relative links are normalized before fetch/dedup (6 unit tests).
- **robots.txt** — `-r` fetches `/robots.txt` and honors `Disallow` for `User-agent: *`; blocked paths are skipped.
- **Protocol-relative links** (`//host/path`) now resolve to scheme + host (→ cross-host, filtered) instead of being mis-saved as a base-host path.
- **52** unit assertions. Live: info.cern.ch saved a nested tree; the Wikipedia crawl honored robots (`/w/…` blocked) and filtered cross-host (`upload.wikimedia.org`).

## [0.5.0] — 2026-06-18 — wget side (-O / --retry / -r)

### Added
- **`-O`** — save the body to a filename derived from the URL path (last segment; `index.html` for `/` or a trailing slash). New `url_filename(path)`.
- **`--retry N`** — retry transient connection failures N times with linear backoff (`200·attempt` ms).
- **`-r` recursive fetch** (`-l N` depth, default 1) — `src/links.cyr` extracts `href`/`src` values; the crawl resolves them (absolute / root-relative / relative), **bounds to the same host**, dedups visited, caps at 64 fetches, and saves each resource to a flat file (`/a/b.html` → `a_b.html`). Cross-host / `#`-fragment / `mailto:` links are skipped.
- **46** unit assertions (links extraction + `url_filename`). Live-validated: `-O https://example.com` → `index.html`; `--retry 2` on a bad host retries then fails; `-r http://info.cern.ch` saved `index.html` + `hypertext_WWW_TheProject.html` (same-host relative link followed, cross-host filtered).

### Still ahead
- `-r` niceties: directory-tree mirroring (vs flat names), `robots.txt`, `../` path normalization.
- resume (`-C`), `--data-binary` / stdin body.
- AGNOS socket backend (taar `#ifdef` + tls_native `set_transport`).

## [0.4.0] — 2026-06-18 — methods + bodies

### Added
- **`-X METHOD`** — arbitrary request method (default GET, or POST when `-d` is given).
- **`-d DATA`** — request body → POST + `Content-Length` + default `Content-Type: application/x-www-form-urlencoded`.
- **`-H 'Header: value'`** — repeatable custom headers; a caller `Content-Type` overrides the default.
- `http.cyr` generalized to `http_build_request(method, host, path, hdrs, nhdrs, body, bodylen, …)`; `http_build_get` is now a thin wrapper. Redirects (`-L`) follow as **GET with the body dropped** (the 301/302/303 norm); custom headers persist across hops.
- **Validated live over HTTPS** (postman-echo): `-d` POST echoed as form data, `-H` header echoed back, `-X DELETE` reached the delete endpoint. **37** unit assertions (6 new for request build + custom headers).

## [0.3.0] — 2026-06-18 — HTTPS + redirect UX

### Added
- **HTTPS** (`src/transport.cyr` `transport_fetch_tls`): TLS session over taar's TCP
  socket via the stdlib `tls_connect`/`tls_read`/`tls_write`/`tls_close`. The
  `tls_native` engine verifies the cert chain + hostname **fail-closed** (CVE-18) —
  `https://expired.badssl.com` is rejected. Sovereign: tls_native's default raw
  read/write on the fd is used; the libssl/`fdlopen` fallback is DCE'd out.
- `main.cyr` routes `https://` (and https redirect targets, with `-L`) to the TLS path.
- **Opt-in deps** (vendored via `cyrius lib sync`, wired into CI): `chrono` / `ct` /
  `keccak` / `random` / `bayan` / `sigil` / `tls_native` / `tls`.
- **Redirect UX**: a bare 3xx without `-L` now prints `whirl: <code> redirect -> <loc>
  (use -L to follow)` to stderr (stdout stays clean) instead of a silent empty body.

### Validated
- `whirl https://example.com` fetches end-to-end (handshake + cert verify + GET);
  `-o FILE` works. Bad-cert host fails closed.

### Still ahead
- POST (`-d`), arbitrary methods (`-X`), custom headers (`-H`).
- AGNOS socket backend (taar's socket is Linux-only; tls_native's `set_transport`
  wires over taar's agnos socket there).

## [0.2.0] — 2026-06-18 — HTTP/1.1 GET MVP (over taar)

whirl fetches real HTTP end-to-end. The transport is sovereign raw-syscall over
the **taar** substrate (no stdlib net): taar's DNS + TCP under whirl's own HTTP
framing — the option chosen for the family's lean per-backend posture.

### Added
- **`src/url.cyr`** — http/https URL parse (scheme / host / port / path; default 80/443; rejects bad scheme / empty host / port > 65535).
- **`src/http.cyr`** — HTTP/1.1 request build + response parse: status code, body offset, case-insensitive header lookup, Content-Length, chunked detect + decode.
- **`src/transport.cyr`** — resolve (`taar_resolve_ipv4`) + TCP connect/send/recv (`taar_tcp_*`) with a recv timeout. Sovereign, no `lib/net.cyr`.
- **`src/cli.cyr`** (`<url>` / `-o FILE` / `-L` / `-h`) + **`src/output.cyr`** (stdout or file via `file_write_all`).
- `main.cyr` wiring with redirect following (`-L`, up to 10 hops).
- **`[deps.taar]`** — whirl is taar's third consumer; pins `taar` **0.2.0** (socket + dns).
- `tests/whirl.tcyr` → **31 assertions** (URL + HTTP framing).

### Validated
- Live: `whirl http://neverssl.com` fetches the page to stdout and via `-o FILE`.

## [0.1.0] — 2026-06-18 — scaffold

### Added
- Repo skeleton mirroring the network-tools family (`yo` / `dig` / `taar`): `cyrius.cyml` (pin 6.2.6), `VERSION`, `LICENSE` (GPL-3.0-only), `README.md`, `CLAUDE.md`, `.gitignore`.
- CI + release workflows using the upstream `install.sh` toolchain pattern from the start (lays out `~/.cyrius/versions/<v>/` — avoids the hand-rolled curl+cp `cyrius deps` pin-check failure).
- `docs/development/roadmap.md` (MVP scope, backlog, v1.0 criteria, and the **AGNOS call surface** — the syscalls/peer functions whirl's agnos backend binds) + `docs/development/state.md`.
- Compilable `src/main.cyr` stub (prints usage; transport WIP) + `src/test.cyr` entry.
