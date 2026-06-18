# whirl

HTTP / HTTPS transfer written in [Cyrius](https://github.com/MacCracken/cyrius). `curl` + `wget`, unified into one verb.

> *The packet **whirls** out; the response **whirls** back. `curl` and `wget` split one fundamental network operation — fetch a URL — into two tools with two flag dialects. whirl merges them: one verb, smart defaults, no curl-vs-wget mental tax. English-wordplay naming lane (curl + wget = whirl).*

## What it will do

```sh
$ whirl https://example.com            # GET -> stdout (text auto-detected)
$ whirl -o page.html https://example.com   # save body to a file (the wget side)
$ whirl -L https://example.com         # follow redirects
$ whirl -d 'a=1&b=2' https://api/x     # POST (later)
$ whirl -X DELETE https://api/x        # arbitrary method (later)
$ whirl -r https://site/              # recursive fetch (the wget side, later)
```

Smart-default behaviour: auto-detect download-to-file (binary) vs print-to-stdout (text), follow redirects, one tool with the combined feature set.

## Sovereignty posture

Per-backend rule (same as `yo` / `dig`): the Linux backend uses POSIX `socket()` pragmatically; the **AGNOS backend uses sovereign kernel syscalls only** — TCP client `sock_connect`#47 / `sock_send`#48 / `sock_recv`#49 / `sock_close`#50, `getrandom`#45, UDP-53 `#51-54` (DNS), and `tls_native` (transport-agnostic) wired over the socket calls for HTTPS. No POSIX on the AGNOS backend. See [`docs/development/roadmap.md`](docs/development/roadmap.md) § *AGNOS call surface*.

## Family

Third tool in the AGNOS **network-tools family** — after [`yo`](https://github.com/MacCracken/yo) (ping/ICMP) and [`dig`](https://github.com/MacCracken/dig) (DNS). whirl is the third consumer of the [`taar`](https://github.com/MacCracken/taar) network-probe substrate, adding its `tcp` / `tls` / `http` modules.

## Status

**Scaffold (0.1.0)** — repo skeleton, manifest, CI/release, and docs are in place; the HTTP/1.1 + TLS transport is the next bite. See [`docs/development/roadmap.md`](docs/development/roadmap.md).

## License

GPL-3.0-only. Genesis repo: [agnosticos](https://github.com/MacCracken/agnosticos).
