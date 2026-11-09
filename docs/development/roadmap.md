# whirl — Roadmap

> **What is left before 1.0.0, in release order, and what waits until after it.**
> Completed work is not listed: per-release history is in
> [`../../CHANGELOG.md`](../../CHANGELOG.md), current state and open defects in
> [`state.md`](state.md), and audit reports in [`../audit/`](../audit/). The last
> audit (0.7.2) is [`2026-11-09-audit.md`](../audit/2026-11-09-audit.md); its
> deferred items are folded in below.

---

## 0.8.x — correctness and limits

The wget half of the tool is bounded in ways a 1.0 should lift, and a few
audit items need work larger than a repair.

- [ ] **Stream large transfers (D1).** The whole response is held in a 1 MiB
      buffer, and a body over it is an error (reported, never silent). Large
      downloads are the wget use case. Stream to the output sink instead; that
      touches `-C` resume, chunked decode and the truncation check. It also
      settles the audit's info item: a close-delimited body of exactly 1 MiB is
      reported as truncated.
- [ ] **`-r` follows redirects.** A 3xx in a crawl is reported and skipped
      (not counted as a failure since 0.7.2). Follow same-origin redirects
      within the fetch cap, as robots.txt already does.
- [ ] **Configurable crawl caps (D2).** 64 resources and 64 links per page are
      reported when hit, but cannot be raised.
- [ ] **`--retry` on transient HTTP errors.** 0.7.2 stopped retrying TLS
      failures and re-sending a POST. Still missing: 408 / 429 / 500 / 502 /
      503 / 504 and truncated bodies, for idempotent methods only.
- [ ] **Framing strictness.** Duplicate or conflicting `Content-Length`,
      `Transfer-Encoding` together with `Content-Length`, and bare-LF header
      lines are accepted leniently today. Decide which to refuse (RFC 9112 §6.3).
- [ ] **Regression tests the 0.7.2 audit could not add.** Several repairs are
      covered by review, not by a test that fails without them: the chunk-size
      digit bound, stderr escaping, the 1xx skip, half header blocks under
      `-i`/`-I`, `Location` whitespace trimming, the crawl's case-insensitive
      host match and `?query` link resolution, the `set_timeout` check, and
      `Content-Length: 0` for an empty body. Listed in the audit report's
      *Deferred* table.
- [ ] **B5 — symlinked intermediate directory.** `O_NOFOLLOW` guards only the
      final component, so a symlinked *directory* planted in the mirror (the
      per-host directory itself included) is still followed. Needs a
      per-component `openat` walk. Unblocked on Linux.
- [ ] **CLI on cmdit.** See *Plan: adopting cmdit* below. It also gives
      `--version`, names unknown flags, and lets combinations whirl ignores
      today (`-r` with `-o`, `-O`, `-C`, `-i` or `-I`) become usage errors.

## 0.9.x — substrate decision and surface freeze

- [ ] **C1 — decide what taar should own.** whirl's HTTP framing
      (`src/http.cyr`) and TLS composition (`src/transport.cyr`) are the
      candidates for taar's unwritten `tls` / `http` modules (zero
      `taar_tls_*` / `taar_http_*` symbols at taar 0.6.2). Settle whether they
      belong in a shared substrate, or whether the 1.0 criterion narrows to
      `tcp` + `dns`: a module with one consumer is not yet shared code.
- [ ] **C2 — extract whatever C1 selects**, in taar, with whirl as the consumer.
- [ ] **Freeze the surface.** Flags, the exit codes (0 / 2 / 9 / 22, listed by
      `whirl -h` since 0.7.2, D3), the `-r` layout (`./HOST[:PORT]/`) and the
      stderr message forms, documented in the README as stable.

## 1.0.0 — release criteria

- [x] GET, POST, arbitrary methods and custom headers; redirects; chunked;
      HTTPS with certificate and hostname verification, fail-closed.
- [x] No POSIX `socket()` in the AGNOS backend: it binds `sock_*`#47-50 and
      `udp_*`#51-54 only.
- [x] HTTP and HTTPS end to end on a real AGNOS kernel (QEMU), and `-r` too
      since 0.7.2.
- [ ] **A3 — iron on archaemenid.** The same runs over the r8169 NIC, plus a
      parity benchmark against `curl` (latency, RSS, binary size). **The
      critical path to 1.0.**
- [ ] **No known unfixed security defect.** Open today: **B2** (AGNOS has no
      no-follow `open`, so the crawl's symlink refusal is a pre-check; blocked
      on agnos `2026-08-27-open-ao-nofollow-flag`) and **B5** (above). Both
      need local write access to the mirror directory. Either close them or
      document them as the accepted bound.
- [ ] Consumes taar with no network primitives vendored locally (C1/C2), or a
      deliberate narrowing of that criterion.
- [ ] Large transfers are not bounded by memory (D1), or the bound is
      documented as intended.

---

## Post-v1 backlog (not scoped)

Recorded so they are not mistaken for 1.0 gaps:
- HTTP/2; connection reuse and keep-alive; parallel crawl fetches;
- cookie jar; proxy support; `--limit-rate`;
- IPv6 (`taar_resolve_ipv4` is A-record only) and IDN / punycode hosts;
- compression (`Accept-Encoding`);
- `-I -L` printing every hop's headers, as curl does (whirl prints the final
  response's);
- robots.txt `Crawl-delay`, and HTML entity decoding in extracted links;
- escaping C1 control bytes on stderr, which would mangle UTF-8 (accepted at
  0.7.2: UTF-8 terminals do not act on a lone C1 byte).

---

## Plan: adopting cmdit (CLI parsing)

**Demand-gated, not a forced sweep.** The 2026-06-25 ecosystem CLI review
([agnosticos `planning/cmdit.md`](https://github.com/MacCracken/agnosticos/blob/main/docs/development/planning/cmdit.md))
lists whirl as a Tier-1 drop-in, and whirl's `-H` accumulator is what motivated
`cmdit_repeat`. The plan was drafted against cmdit 1.2.6. At whirl's 6.7.18 pin
the matching tag is **1.5.1** (dig runs on it); re-check the calls below against
it before starting. dig's 0.5.0 records two user-visible changes from cmdit
1.3.x: `--help=x` is a usage error, and unknown-flag errors name the token.

**Today.** `cli_parse` (`src/cli.cyr`) is a hand-rolled `streq` chain. It takes
the short-only bools `-L -O -r -C -f -i -I`; `-o`, `-X`; `-d` and
`--data-binary` (one loader, last wins); `-A` / `--user-agent`; `-H`, repeatable
and capped at 16; `--retry` (long only) and `-l` (short only) through
`_cli_atoi`, which stops at the first non-digit and clamps at 1,000,000. `-h` /
`--help` return mid-loop; any other token is the URL, including an unknown `-x`,
and a second one is `CLI_ERR`. `main` maps `CLI_HELP` to `_print_help` (exit 0)
and `CLI_ERR` to the usage line (exit 2). `_print_help` is hand-written, on
stdout.

**Site → cmdit:**
- [ ] `cmdit_new("whirl")`. Bools → `cmdit_bool`. `-o`, `-X` → `cmdit_str`.
      Register `-d` / `--data-binary` as one `cmdit_str`, so last-wins holds
      across both spellings; `-A` / `--user-agent` likewise.
- [ ] `-H` → `cmdit_repeat`. Keep the fail-closed cap in whirl
      (`cmdit_repeat_count > 16` → error), which holds only while 16 stays
      below cmdit's silent 64-entry list cap. Run `_cli_load_data` once, after
      the parse, on `cmdit_get_str`.
- [ ] **Decide** `--retry` / `-l`: `cmdit_int` with `cmdit_range(0, 1000000)`
      rejects (exit 2) what `_cli_atoi` truncates or clamps (`5x` → 5,
      `-1` → 0). For identity, register them as strings and keep `_cli_atoi`.
- [ ] URL → `cmdit_require_positionals_exact(h, 1)`; the missing and too-many
      cases both map to today's usage line, exit 2.
- [ ] `cmdit_version(h, WHIRL_VERSION)` for `--version` (new surface, no clash:
      curl's `-V` is also `--version`), with a row in `_print_help`.
- [ ] Keep `_print_help` hand-written: `cmdit_help_flags` writes to stderr and
      cannot carry whirl's metavars or wrapped lines.

**Behaviour that changes** (all still exit 2): an unknown `-x` is an error
instead of a URL; `-LO` is `CMDIT_ERR_BUNDLED`; `-h` no longer short-circuits.
`--` and `--name=value` become accepted. Exit codes 9 and 22 stay whirl's own.

**`cyrius.cyml`:** add

```
[deps.cmdit]
git = "https://github.com/MacCracken/cmdit.git"
tag = "1.5.1"
modules = ["dist/cmdit.cyr"]
```

**Tests:** `tests/whirl.tcyr` has no CLI test; add synthetic-argv cases on
`cmdit_parse_argv`, which is pure (`CLI_HELP` is 1 but `CMDIT_HELP` is 2).
`tests/agnos_probe.cyr` includes `src/cli.cyr` but calls nothing in it.
`python3 tests/behavior.py build/whirl` must stay green, and `-h` plus the
usage-error paths should be byte-compared against the pre-swap binary.

---

## Reference: AGNOS call surface

whirl's AGNOS arm binds **only** the calls below. There is no
`platform_agnos.cyr`: the dispatch is inline `#ifdef CYRIUS_TARGET_AGNOS` in
`src/transport.cyr`, `src/output.cyr` and `src/mirror.cyr`.

| Need | AGNOS kernel syscall | cyrius peer |
|---|---|---|
| TCP connect / send / recv / close | `sock_connect`#47, `sock_send`#48, `sock_recv`#49 (non-blocking), `sock_close`#50 | via taar's AGNOS socket arm |
| TLS (HTTPS) | none: runs over the TCP calls | `tls_native_set_transport(read, write, now)` over `sock_recv` / `sock_send`, then `tls_native_*`; trust roots from `tls_native_set_ca_system` (cached once per process) |
| Entropy | `getrandom`#45 | `random.cyr` |
| DNS | `udp_bind`#51 / `udp_send`#52 / `udp_recv`#53 / `udp_unbind`#54 | taar's resolver |
| Clock / sleep | `uptime_ms`#40 / `sleep_ms`#41 | `sys_uptime_ms` / `sys_sleep_ms` |
| Kernel-leased resolver | `net_config`#61 field 3 (DHCP option 6) | `sys_net_dns_server()`, tried before `/etc/resolv.conf` |
| Symlink detection (`-r`) | `readlink`#70 (no-follow, final component) | `sys_readlink()` |

whirl needs **zero new kernel syscalls**. The one open kernel ask is **B2**, an
`AO_NOFOLLOW` flag on `open`(7).

> Cross-refs: [agnos net-syscall arc](https://github.com/MacCracken/agnosticos/blob/main/docs/development/state.md) (#45-#57) · [taar](https://github.com/MacCracken/taar) · [yo](https://github.com/MacCracken/yo) · [dig](https://github.com/MacCracken/dig)
