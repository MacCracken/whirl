#!/usr/bin/env python3
"""whirl behavioral test suite — end-to-end checks against a real binary.

Complements tests/whirl.tcyr, which covers pure logic (URL parse, HTTP framing,
link extraction). The defects fixed in 0.6.6 all live in the *interaction*
between the CLI, the transport and the filesystem, so none of them are reachable
from a pure-logic suite: they need a real server that answers adversarially, and
a real binary with a real working directory.

Python because Cyrius has no scripting/test-harness spinoff yet. When it does,
this should move over — nothing here needs Python specifically, it just needs a
socket server, a subprocess and a scratch directory.

    usage: python3 tests/behavior.py <whirl-binary> [--baseline <old-binary>]
                                     [--workdir DIR] [--keep]

Without --baseline, every assertion runs against <whirl-binary> alone: these are
the checks that must hold for the build to ship, and they are what CI runs.

With --baseline pointing at an older binary, each fix additionally runs as a
*paired* test: the defect is first reproduced on the old binary, so a check that
has silently stopped exercising the vulnerable path shows up as a failed control
rather than a false pass. That pairing is what makes these fixes trustworthy;
use it when you have an older binary to hand.

Controls are tagged with the release that fixed the defect, and the baseline's
version is read off the `User-Agent` it puts on the wire. A control whose fix
the baseline already contains is SKIPPED, not failed — otherwise every future
release would report phantom failures for every fix older than its baseline.
An unknown baseline version runs every control, which is the safe direction.

Exit status: 0 if every check passed, 1 otherwise.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

# ---------------------------------------------------------------- infrastructure

_NEXT_PORT = [20100]


def newport():
    """A fresh port per server, so a lingering thread never collides."""
    _NEXT_PORT[0] += 1
    return _NEXT_PORT[0]


def serve(port, handler, n=8):
    """Answer up to `n` connections on `port` with `handler(conn, request_text)`."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen(16)
    s.settimeout(15)

    def loop():
        for _ in range(n):
            try:
                conn, _addr = s.accept()
            except Exception:
                break
            try:
                handler(conn, conn.recv(8192).decode("latin1"))
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        try:
            s.close()
        except Exception:
            pass

    threading.Thread(target=loop, daemon=True).start()


class Runner:
    def __init__(self, workdir):
        self.workdir = workdir

    def __call__(self, binary, args, tag, timeout=25):
        """Run `binary` in a clean subdirectory; return (rc, stdout, stderr, dir)."""
        d = os.path.join(self.workdir, tag)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        try:
            p = subprocess.run([binary] + args, cwd=d, capture_output=True, timeout=timeout)
            return (p.returncode,
                    p.stdout.decode("latin1", "replace"),
                    p.stderr.decode("latin1", "replace"),
                    d)
        except subprocess.TimeoutExpired:
            return -99, "", "TIMEOUT", d


class Report:
    def __init__(self, baseline_version=None):
        self.checks = []
        self.skipped = 0
        # (major, minor, patch) of the --baseline binary, or None. A control is
        # only meaningful against a baseline OLDER than the release that fixed
        # the defect: run against a newer one it cannot reproduce, and would
        # report a phantom failure on every future release.
        self.baseline_version = baseline_version

    def check(self, name, ok, detail=""):
        self.checks.append((name, ok))
        print(("  PASS  " if ok else "  FAIL  ") + name + (("   :: " + detail) if detail else ""))

    def control(self, name, ok, fixed_in, detail=""):
        """Assert the baseline binary really did exhibit the defect.

        A failed control does not mean the shipping binary is broken — it means
        the check has stopped exercising the path it was written for, so the
        corresponding PASS proves less than it appears to. That is a silent
        false pass, so it counts as a failure.

        `fixed_in` is the release that closed the defect. Against a baseline at
        or after it the control is skipped rather than failed: the baseline is
        simply already fixed, which is information, not a regression.
        """
        if self.baseline_version is not None and self.baseline_version >= fixed_in:
            self.skipped += 1
            print("  skip  %s   :: baseline %s already has the %s fix"
                  % (name, ver_str(self.baseline_version), ver_str(fixed_in)))
            return
        self.checks.append((name, ok))
        print(("  CTRL  " if ok else "  FAIL  ") + name + (("   :: " + detail) if detail else ""))

    def summary(self):
        passed = sum(1 for _n, ok in self.checks if ok)
        total = len(self.checks)
        extra = ("  (%d control(s) skipped: baseline already fixed)" % self.skipped) if self.skipped else ""
        print("\n==== %d/%d checks passed ====%s" % (passed, total, extra))
        return passed == total


def ver_str(v):
    return ".".join(str(x) for x in v)


def probe_version(run, binary):
    """Learn a binary's version from the User-Agent it puts on the wire.

    Self-describing, and it needs no flag the older binaries do not have: whirl
    has sent `User-Agent: whirl/<version>` by default since 0.6.5. Returns a
    (major, minor, patch) tuple, or None if it could not be determined (in which
    case every control runs, which is the safe direction).
    """
    seen = []
    p = newport()
    serve(p, h_ok(seen))
    run(binary, ["http://127.0.0.1:%d/" % p], "probe")
    for req in seen:
        for line in req.splitlines():
            if line.lower().startswith("user-agent:") and "whirl/" in line:
                raw = line.split("whirl/", 1)[1].strip()
                parts = raw.split(".")
                try:
                    return tuple(int(x) for x in parts[:3])
                except ValueError:
                    return None
    return None


# ---------------------------------------------------------------- shared handlers

def h_ok(seen=None, body=b"hi"):
    def h(conn, req):
        if seen is not None:
            seen.append(req)
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
    return h


def h_redirect_to(port, path="/steal"):
    def h(conn, _req):
        conn.sendall(("HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:%d%s\r\n"
                      "Content-Length: 0\r\n\r\n" % (port, path)).encode())
    return h


# ---------------------------------------------------------------- the checks

def check_path_traversal(run, rep, new, old, marker, marker2):
    """0.6.6: a crawled page must not be able to write outside the crawl directory."""
    print("\n[1] -r path traversal -> remote arbitrary file write")

    def make(port):
        def h(conn, req):
            if "robots.txt" in req:
                conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                return
            if "pwned" in req:
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nPWNED")
                return
            # Two escapes: a "../" ladder, and the "//" form that survives a
            # single leading-slash strip as an absolute path.
            body = ('<a href="http://127.0.0.1:%d/../../../..%s">a</a>'
                    '<a href="http://127.0.0.1:%d/%s">b</a>' % (port, marker, port, marker2)).encode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
        return h

    def escaped():
        return [f for f in (marker, marker2) if os.path.exists(f)]

    def clean():
        for f in (marker, marker2):
            if os.path.exists(f):
                os.remove(f)

    if old:
        clean()
        p = newport()
        serve(p, make(p))
        run(old, ["-r", "-l", "1", "http://127.0.0.1:%d/" % p], "trav_baseline")
        rep.control("baseline writes outside cwd", bool(escaped()), (0, 6, 6), str(escaped()))

    clean()
    p = newport()
    serve(p, make(p))
    _rc, _o, err, _d = run(new, ["-r", "-l", "1", "http://127.0.0.1:%d/" % p], "trav")
    leaked = escaped()
    clean()
    rep.check("traversal blocked", not leaked,
              err.strip().replace("\n", " | ")[:150] if not leaked else "ESCAPED: %s" % leaked)


def check_crlf_injection(run, rep, new, old):
    """0.6.6: a Location with bare LFs must not splice headers into the next request."""
    print("\n[2] CRLF injection via redirect Location")

    def make(port, seen):
        def h(conn, req):
            if req.startswith("GET /go"):
                conn.sendall(("HTTP/1.1 302 Found\r\n"
                              "Location: http://127.0.0.1:%d/a HTTP/1.1\nHost: x\nX-Injected: yes\n\r\n"
                              "Content-Length: 0\r\n\r\n" % port).encode())
                return
            seen.append(req)
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        return h

    if old:
        seen = []
        p = newport()
        serve(p, make(p, seen))
        run(old, ["-L", "http://127.0.0.1:%d/go" % p], "crlf_baseline")
        rep.control("baseline injects a header", any("X-Injected" in r for r in seen), (0, 6, 6))

    seen = []
    p = newport()
    serve(p, make(p, seen))
    _rc, _o, err, _d = run(new, ["-L", "http://127.0.0.1:%d/go" % p], "crlf")
    rep.check("injected Location rejected", not any("X-Injected" in r for r in seen),
              err.strip()[:110])


def check_credential_replay(run, rep, new, old):
    """0.6.6: credentials must not follow a redirect to another origin."""
    print("\n[3] Authorization replay on cross-origin redirect")

    if old:
        seen = []
        a, b = newport(), newport()
        serve(a, h_redirect_to(b))
        serve(b, h_ok(seen))
        run(old, ["-L", "-H", "Authorization: Bearer SECRET", "http://127.0.0.1:%d/x" % a],
            "cred_baseline")
        rep.control("baseline leaks the credential", any("SECRET" in r for r in seen), (0, 6, 6))

    seen = []
    a, b = newport(), newport()
    serve(a, h_redirect_to(b))
    serve(b, h_ok(seen))
    run(new, ["-L", "-H", "Authorization: Bearer SECRET", "http://127.0.0.1:%d/x" % a], "cred")
    rep.check("credential dropped cross-origin", not any("SECRET" in r for r in seen))

    # The complement: the fix must not strip credentials it has no reason to.
    seen = []
    a = newport()
    serve(a, h_ok(seen))
    run(new, ["-H", "Authorization: Bearer KEEP", "http://127.0.0.1:%d/x" % a], "cred_same")
    rep.check("credential kept when no redirect", any("KEEP" in r for r in seen))


def check_relative_location(run, rep, new, old):
    """0.6.6: -L must follow a schemeless Location (RFC 9110 permits one)."""
    print("\n[4] relative Location is followed")

    def h(conn, req):
        if req.startswith("GET /docs "):
            conn.sendall(b"HTTP/1.1 301 Moved\r\nLocation: /docs/\r\nContent-Length: 0\r\n\r\n")
            return
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nPAYLOAD-OK")

    if old:
        p = newport()
        serve(p, h)
        _rc, out, _e, _d = run(old, ["-L", "http://127.0.0.1:%d/docs" % p], "rel_baseline")
        rep.control("baseline fails to follow", "PAYLOAD-OK" not in out, (0, 6, 6), repr(out[:40]))

    p = newport()
    serve(p, h)
    rc, out, _e, _d = run(new, ["-L", "http://127.0.0.1:%d/docs" % p], "rel")
    rep.check("relative Location followed", "PAYLOAD-OK" in out, "rc=%d %r" % (rc, out[:40]))


def check_truncation(run, rep, new, old):
    """0.6.6: a body short of its Content-Length must not exit 0."""
    print("\n[5] short body vs Content-Length must not exit 0")

    def h(conn, _req):
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5000\r\n\r\n" + b"A" * 100)
        conn.close()

    if old:
        p = newport()
        serve(p, h)
        rc, _o, _e, _d = run(old, ["http://127.0.0.1:%d/f" % p], "trunc_baseline")
        rep.control("baseline exits 0 on truncation", rc == 0, (0, 6, 6), "rc=%d" % rc)

    p = newport()
    serve(p, h)
    rc, _o, err, _d = run(new, ["http://127.0.0.1:%d/f" % p], "trunc")
    rep.check("truncation reported as failure", rc != 0, "rc=%d %s" % (rc, err.strip()[:100]))


def check_crawl_dechunk(run, rep, new, old):
    """0.6.6: -r must save the decoded body, not the chunk framing."""
    print("\n[6] -r saves the decoded body")

    def h(conn, req):
        if "robots" in req:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            return
        conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                     b"5\r\nHELLO\r\n5\r\nWORLD\r\n0\r\n\r\n")

    def saved(d):
        f = os.path.join(d, "p.html")
        return open(f, "rb").read() if os.path.exists(f) else b""

    if old:
        p = newport()
        serve(p, h)
        _rc, _o, _e, d = run(old, ["-r", "-l", "0", "http://127.0.0.1:%d/p.html" % p], "chunk_baseline")
        rep.control("baseline writes raw chunk framing", b"5\r\n" in saved(d), (0, 6, 6), repr(saved(d)[:28]))

    p = newport()
    serve(p, h)
    _rc, _o, _e, d = run(new, ["-r", "-l", "0", "http://127.0.0.1:%d/p.html" % p], "chunk")
    rep.check("decoded body written", saved(d) == b"HELLOWORLD", repr(saved(d)[:28]))


def check_body_file(run, rep, new, old):
    """0.6.6: -d @missing must not silently degrade to a bodyless GET."""
    print("\n[7] -d @missing-file must not silently degrade to GET")

    if old:
        seen = []
        p = newport()
        serve(p, h_ok(seen))
        rc, _o, _e, _d = run(old, ["-d", "@/nonexistent/nope", "http://127.0.0.1:%d/x" % p],
                             "body_baseline")
        rep.control("baseline sends a bodyless request", bool(seen) and rc == 0, (0, 6, 6), "rc=%d" % rc)

    seen = []
    p = newport()
    serve(p, h_ok(seen))
    rc, _o, err, _d = run(new, ["-d", "@/nonexistent/nope", "http://127.0.0.1:%d/x" % p], "body")
    rep.check("missing body file is an error", rc == 2 and not seen,
              "rc=%d %s" % (rc, err.strip()[:70]))


def check_regressions(run, rep, new):
    """The fixes above must not break ordinary transfers."""
    print("\n[7b] regressions: ordinary transfers still work")

    p = newport()
    serve(p, h_ok(body=b"hello world"))
    rc, out, _e, _d = run(new, ["http://127.0.0.1:%d/" % p], "reg_plain")
    rep.check("plain 200 fetch", rc == 0 and out == "hello world", "rc=%d %r" % (rc, out[:30]))

    def h_chunked(conn, _req):
        conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                     b"3\r\nabc\r\n3\r\ndef\r\n0\r\n\r\n")

    p = newport()
    serve(p, h_chunked)
    rc, out, _e, _d = run(new, ["http://127.0.0.1:%d/" % p], "reg_chunked")
    rep.check("chunked fetch to stdout", rc == 0 and out == "abcdef", "rc=%d %r" % (rc, out[:30]))

    # -I sets Content-Length for a body that is legitimately absent: the
    # truncation check must not fire on it.
    p = newport()
    serve(p, h_ok(body=b"hello world"))
    rc, out, _e, _d = run(new, ["-I", "http://127.0.0.1:%d/" % p], "reg_head")
    rep.check("-I not treated as truncated", rc == 0 and "200 OK" in out,
              "rc=%d %r" % (rc, out[:40]))

    # -o must write the body to the named file.
    p = newport()
    serve(p, h_ok(body=b"filebody"))
    rc, _o, _e, d = run(new, ["-o", "out.txt", "http://127.0.0.1:%d/" % p], "reg_outfile")
    f = os.path.join(d, "out.txt")
    got = open(f, "rb").read() if os.path.exists(f) else b""
    rep.check("-o writes the body", rc == 0 and got == b"filebody", repr(got[:30]))


# ---------------------------------------------------------------- entry point

def check_origin_confinement(run, rep, new, old):
    """0.6.7: the crawl is bounded by ORIGIN — scheme, host and port — not host alone."""
    print("\n[8] -r origin confinement (scheme + port)")

    def make(other_port):
        def h(conn, req):
            if "robots.txt" in req:
                conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                return
            # A same-host link on another port, and one on another scheme.
            body = ('<a href="http://127.0.0.1:%d/reached.html">port</a>'
                    '<a href="https://127.0.0.1/reached2.html">scheme</a>' % other_port).encode()
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
        return h

    reached = []
    base, other = newport(), newport()
    serve(base, make(other))
    serve(other, h_ok(reached, b"REACHED"))
    _rc, _o, err, _d = run(new, ["-r", "-l", "1", "http://127.0.0.1:%d/" % base], "origin")
    rep.check("cross-port link not followed", not reached, "reached=%d" % len(reached))
    rep.check("cross-scheme link reported", "cross-scheme" in err, err.strip()[:90])


def check_crawl_nondefault_port(run, rep, new, old):
    """0.6.7: relative links must keep :port, or -r is useless off :80/:443."""
    print("\n[9] -r works on a non-default port")

    def h(conn, req):
        if "robots.txt" in req:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            return
        if req.startswith("GET /child.html"):
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nCHILD")
            return
        body = b'<a href="/child.html">c</a>'
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body)

    if old:
        p = newport()
        serve(p, h, n=12)
        _rc, _o, _e, d = run(old, ["-r", "-l", "1", "http://127.0.0.1:%d/" % p], "port_baseline")
        rep.control("baseline cannot crawl off the default port",
                    not os.path.exists(os.path.join(d, "child.html")), (0, 6, 7))

    p = newport()
    serve(p, h, n=12)
    _rc, _o, _e, d = run(new, ["-r", "-l", "1", "http://127.0.0.1:%d/" % p], "port")
    f = os.path.join(d, "child.html")
    got = open(f, "rb").read() if os.path.exists(f) else b""
    rep.check("relative link fetched on odd port", got == b"CHILD", repr(got[:20]))


def check_host_header_port(run, rep, new, old):
    """0.6.7: RFC 9110 s7.2 — Host carries a non-default port."""
    print("\n[10] Host header carries a non-default port")
    seen = []
    p = newport()
    serve(p, h_ok(seen))
    run(new, ["http://127.0.0.1:%d/x" % p], "hosthdr")
    want = "Host: 127.0.0.1:%d" % p
    if old:
        seen_old = []
        q = newport()
        serve(q, h_ok(seen_old))
        run(old, ["http://127.0.0.1:%d/x" % q], "hosthdr_baseline")
        rep.control("baseline omits the port",
                    not any(("Host: 127.0.0.1:%d" % q) in r for r in seen_old), (0, 6, 7))
    rep.check("Host includes the port", any(want in r for r in seen),
              (seen[0].splitlines()[1] if seen else "no request"))


def check_include_chunked(run, rep, new, old):
    """0.6.7: -i must emit the decoded body, not raw chunk framing."""
    print("\n[11] -i on a chunked response emits a decoded body")

    def h(conn, _req):
        conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                     b"5\r\nHELLO\r\n5\r\nWORLD\r\n0\r\n\r\n")

    if old:
        p = newport()
        serve(p, h)
        _rc, out, _e, _d = run(old, ["-i", "http://127.0.0.1:%d/" % p], "inc_baseline")
        rep.control("baseline emits raw chunk framing", "5\r\nHELLO" in out, (0, 6, 7), repr(out[-30:]))

    p = newport()
    serve(p, h)
    rc, out, _e, _d = run(new, ["-i", "http://127.0.0.1:%d/" % p], "inc")
    ok = ("HELLOWORLD" in out) and ("5\r\nHELLO" not in out) and ("200 OK" in out)
    rep.check("-i decoded, headers kept", rc == 0 and ok, repr(out[-40:]))

    # -i -o must put BOTH halves in the file (a two-write fix would lose one).
    p = newport()
    serve(p, h)
    rc, _o, _e, d = run(new, ["-i", "-o", "both.txt", "http://127.0.0.1:%d/" % p], "inc_file")
    f = os.path.join(d, "both.txt")
    got = open(f, "rb").read() if os.path.exists(f) else b""
    rep.check("-i -o writes headers AND body",
              b"200 OK" in got and b"HELLOWORLD" in got, repr(got[-40:]))


def check_retry_on_empty(run, rep, new, old):
    """0.6.7: a zero-byte response is a failure, so --retry must fire on it."""
    print("\n[12] --retry fires on a zero-byte response")
    attempts = []

    def h(conn, req):
        attempts.append(req)
        conn.close()          # accept, send nothing, close

    if old:
        p = newport()
        serve(p, h, n=12)
        run(old, ["--retry", "2", "http://127.0.0.1:%d/" % p], "retry_baseline")
        rep.control("baseline does not retry", len(attempts) == 1, (0, 6, 7), "attempts=%d" % len(attempts))

    attempts.clear()
    p = newport()
    serve(p, h, n=12)
    rc, _o, _e, _d = run(new, ["--retry", "2", "http://127.0.0.1:%d/" % p], "retry")
    rep.check("retried and then failed", len(attempts) == 3 and rc != 0,
              "attempts=%d rc=%d" % (len(attempts), rc))


def check_symlink_write(run, rep, new, old):
    """0.6.8: -r must not write THROUGH a symlink planted in the crawl directory."""
    print("\n[13] -r refuses to write through a symlink")

    def h(conn, req):
        if "robots.txt" in req:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            return
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\nPAYLOAD")

    def attempt(binary, tag):
        # Pre-plant target.html -> a file outside the crawl directory, the way an
        # attacker with local write access to the download dir would.
        d = os.path.join(run.workdir, tag)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        outside = os.path.join(run.workdir, "%s-outside.txt" % tag)
        with open(outside, "w") as f:
            f.write("ORIGINAL")
        os.symlink(outside, os.path.join(d, "target.html"))
        p = newport()
        serve(p, h, n=8)
        subprocess.run([binary, "-r", "-l", "0", "http://127.0.0.1:%d/target.html" % p],
                       cwd=d, capture_output=True, timeout=25)
        return open(outside).read()

    if old:
        rep.control("baseline writes through the symlink",
                    attempt(old, "sym_baseline") == "PAYLOAD", (0, 6, 8))

    rep.check("symlink target left untouched", attempt(new, "sym") == "ORIGINAL")


def check_crawl_cap_reported(run, rep, new, old):
    """0.6.8: hitting the crawl cap must be reported, not silently truncate the mirror."""
    print("\n[14] crawl cap is reported, not silent")

    def h(conn, req):
        if "robots.txt" in req:
            conn.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            return
        if req.startswith("GET /p"):
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
            return
        links = "".join('<a href="/p%d.html">x</a>' % i for i in range(200)).encode()
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(links) + links)

    if old:
        p = newport()
        serve(p, h, n=200)
        _rc, _o, err, _d = run(old, ["-r", "-l", "1", "http://127.0.0.1:%d/" % p],
                               "cap_baseline", timeout=90)
        rep.control("baseline drops links silently", "crawl cap" not in err, (0, 6, 8))

    p = newport()
    serve(p, h, n=200)
    _rc, _o, err, _d = run(new, ["-r", "-l", "1", "http://127.0.0.1:%d/" % p], "cap", timeout=90)
    rep.check("crawl cap reported on stderr", "crawl cap reached" in err,
              next((l for l in err.splitlines() if "cap" in l), err.strip()[:80]))


def check_complete_without_close(run, rep, new, old):
    """0.6.9: a complete response must not wait on a peer close it does not need.

    This is the AGNOS failure reproduced on Linux. There, a complete chunked body
    whose peer close was not surfaced burned taar's 10s receive deadline and came
    back as a timeout, which 0.6.6's truncation check reported as an incomplete
    response. Holding the connection open after a complete body reproduces it
    without QEMU: the framing says the response is whole, so whirl must return it.
    """
    print("\n[15] a complete response does not wait for the peer to close")

    def hold(payload):
        def h(conn, _req):
            conn.sendall(payload)
            time.sleep(20)      # never close — force whirl to decide on framing alone
        return h

    chunked = (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
               b"5\r\nHELLO\r\n5\r\nWORLD\r\n0\r\n\r\n")

    if old:
        p = newport()
        serve(p, hold(chunked))
        rc, out, _e, _d = run(old, ["http://127.0.0.1:%d/" % p], "hold_baseline", timeout=20)
        rep.control("baseline stalls then reports a complete body incomplete",
                    rc != 0 and out == "", (0, 6, 9), "rc=%d" % rc)

    p = newport()
    serve(p, hold(chunked))
    rc, out, err, _d = run(new, ["http://127.0.0.1:%d/" % p], "hold_chunked", timeout=15)
    rep.check("chunked body returned without a close", rc == 0 and out == "HELLOWORLD",
              "rc=%d %r %s" % (rc, out[:30], err.strip()[:60]))

    sized = b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"
    p = newport()
    serve(p, hold(sized))
    rc, out, err, _d = run(new, ["http://127.0.0.1:%d/" % p], "hold_sized", timeout=15)
    rep.check("content-length body returned without a close", rc == 0 and out == "hello",
              "rc=%d %r %s" % (rc, out[:30], err.strip()[:60]))

    p = newport()
    serve(p, hold(b"HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\nhello world"))
    rc, out, _e, _d = run(new, ["-I", "http://127.0.0.1:%d/" % p], "hold_head", timeout=15)
    rep.check("-I returns without a close", rc == 0 and "200 OK" in out, "rc=%d" % rc)

    # The truncation check must still fire: an UNTERMINATED chunk stream that
    # then closes is genuinely incomplete and must not be reported as success.
    def cut(conn, _req):
        conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nHELLO\r\n")
        conn.close()
    p = newport()
    serve(p, cut)
    rc, _o, err, _d = run(new, ["http://127.0.0.1:%d/" % p], "cut_chunked", timeout=15)
    rep.check("unterminated chunk stream still fails", rc != 0,
              "rc=%d %s" % (rc, err.strip()[:70]))


def main():
    ap = argparse.ArgumentParser(description="whirl behavioral test suite")
    ap.add_argument("binary", help="the whirl binary under test")
    ap.add_argument("--baseline", help="a pre-0.6.6 binary; enables paired control checks")
    ap.add_argument("--workdir", help="scratch directory (default: a temp dir, removed on exit)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch directory")
    args = ap.parse_args()

    binary = os.path.abspath(args.binary)
    if not os.path.exists(binary):
        print("no such binary: %s" % binary, file=sys.stderr)
        return 2
    baseline = os.path.abspath(args.baseline) if args.baseline else None
    if baseline and not os.path.exists(baseline):
        print("no such baseline binary: %s" % baseline, file=sys.stderr)
        return 2

    workdir = args.workdir or tempfile.mkdtemp(prefix="whirl-behavior-")
    os.makedirs(workdir, exist_ok=True)

    # The traversal check has to prove an escape from the crawl directory, so
    # its markers necessarily live outside the scratch tree. PID-unique so
    # concurrent runs cannot collide, and removed whether or not the check passes.
    marker = "/tmp/whirl-behavior-escape-%d" % os.getpid()
    marker2 = "/tmp/whirl-behavior-escape-%d-b" % os.getpid()

    print("whirl behavioral suite")
    print("  binary:   %s" % binary)
    print("  baseline: %s" % (baseline or "(none — control checks skipped)"))
    print("  workdir:  %s" % workdir)

    run = Runner(workdir)
    baseline_version = probe_version(Runner(workdir), baseline) if baseline else None
    if baseline:
        print("  baseline version: %s" % (ver_str(baseline_version) if baseline_version else "unknown"))
    rep = Report(baseline_version)
    try:
        check_path_traversal(run, rep, binary, baseline, marker, marker2)
        check_crlf_injection(run, rep, binary, baseline)
        check_credential_replay(run, rep, binary, baseline)
        check_relative_location(run, rep, binary, baseline)
        check_truncation(run, rep, binary, baseline)
        check_crawl_dechunk(run, rep, binary, baseline)
        check_body_file(run, rep, binary, baseline)
        check_regressions(run, rep, binary)
        check_origin_confinement(run, rep, binary, baseline)
        check_crawl_nondefault_port(run, rep, binary, baseline)
        check_host_header_port(run, rep, binary, baseline)
        check_include_chunked(run, rep, binary, baseline)
        check_retry_on_empty(run, rep, binary, baseline)
        check_symlink_write(run, rep, binary, baseline)
        check_crawl_cap_reported(run, rep, binary, baseline)
        check_complete_without_close(run, rep, binary, baseline)
    finally:
        for f in (marker, marker2):
            if os.path.exists(f):
                os.remove(f)
        if not args.keep and not args.workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    return 0 if rep.summary() else 1


if __name__ == "__main__":
    sys.exit(main())
