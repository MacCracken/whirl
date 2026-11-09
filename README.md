# whirl

HTTP / HTTPS transfer written in [Cyrius](https://github.com/MacCracken/cyrius). `curl` + `wget`, unified into one verb.

> *The packet **whirls** out; the response **whirls** back. `curl` and `wget` split one fundamental network operation — fetch a URL — into two tools with two flag dialects. whirl merges them: one verb, smart defaults, no curl-vs-wget mental tax. English-wordplay naming lane (curl + wget = whirl).*

## What it does

```sh
$ whirl https://example.com                 # GET -> stdout
$ whirl -o page.html https://example.com    # save body to a file (the wget side)
$ whirl -O https://site/file.tar.gz         # filename derived from the URL
$ whirl -C -O https://site/big.iso          # resume a partial download (Range)
$ whirl -L https://example.com              # follow redirects
$ whirl -d 'a=1&b=2' https://api/x          # POST (@file / @- also work)
$ whirl -X DELETE https://api/x             # arbitrary method
$ whirl -H 'Accept: application/json' url   # add a header (repeatable)
$ whirl -I https://example.com              # HEAD — headers only
$ whirl -r -l 2 https://site/               # recursive fetch into ./site/ (the wget side)
```

Full flag surface: `-X` `-d` `--data-binary` `-H` `-A`/`--user-agent` `-o` `-O`
`-C` `-i` `-I` `-f` `-L` `-r` `-l` `--retry` `-h`/`--help`.

Defaults: the body goes to stdout unless `-o` / `-O` names a file, and redirects
are followed only with `-L` (up to 10). `-r` mirrors same-origin pages under
`./HOST[:PORT]/` and never writes a path with a hidden (dot-leading) segment;
it honours robots.txt per RFC 9309.

Exit status: `0` success, `2` usage or bad input, `9` transfer, response or
write failure (including too many redirects, and any failure during `-r`),
`22` HTTP ≥ 400 under `-f`.

## Sovereignty posture

Per-backend rule (same as `yo` / `dig`): the Linux backend uses POSIX `socket()` pragmatically (by raw syscall, via `taar` — no libc); the **AGNOS backend uses sovereign kernel syscalls only** — TCP client `sock_connect`#47 / `sock_send`#48 / `sock_recv`#49 / `sock_close`#50, `getrandom`#45, UDP-53 `#51-54` (DNS), `net_config`#61 (the kernel-leased resolver), and `tls_native` (transport-agnostic) wired over the socket calls for HTTPS. No POSIX on the AGNOS backend. See [`docs/development/roadmap.md`](docs/development/roadmap.md) § *Reference: AGNOS call surface*.

## Family

Third tool in the AGNOS **network-tools family** — after [`yo`](https://github.com/MacCracken/yo) (ping/ICMP) and [`dig`](https://github.com/MacCracken/dig) (DNS). whirl is the third consumer of the [`taar`](https://github.com/MacCracken/taar) network-probe substrate: it runs on taar's `tcp` and `dns` modules, and is the candidate donor for taar's unwritten `tls` / `http` modules (roadmap C1).

## Status

Pre-1.0, and working: HTTP/1.1 + HTTPS with fail-closed certificate and hostname
verification, on **both** the Linux and AGNOS backends. AGNOS is QEMU-validated;
validation on iron is the critical path to v1.0. The latest audit is
[`docs/audit/2026-11-09-audit.md`](docs/audit/2026-11-09-audit.md).

See [`docs/development/state.md`](docs/development/state.md) for the current
version and surface area, and [`docs/development/roadmap.md`](docs/development/roadmap.md)
for the milestone path.

## License

GPL-3.0-only. Genesis repo: [agnosticos](https://github.com/MacCracken/agnosticos).
