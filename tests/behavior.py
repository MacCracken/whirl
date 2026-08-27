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
the checks that must hold for the build to ship. With --baseline pointing at a
pre-0.6.6 binary, each security check additionally runs as a *paired* test — it
first reproduces the defect on the old binary, so a check that silently stopped
exercising the vulnerable path shows up as a failed control rather than a false
pass. That pairing is why these fixes are trustworthy; keep it when you can.

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
    def __init__(self):
        self.checks = []

    def check(self, name, ok, detail=""):
        self.checks.append((name, ok))
        print(("  PASS  " if ok else "  FAIL  ") + name + (("   :: " + detail) if detail else ""))

    def control(self, name, ok, detail=""):
        """A control asserts the OLD binary really was vulnerable.

        A failed control does not mean the shipping binary is broken — it means
        the check is no longer exercising the path it was written for, so the
        corresponding PASS proves less than it appears to. Surfaced loudly for
        that reason, and counted as a failure.
        """
        self.checks.append((name, ok))
        print(("  CTRL  " if ok else "  FAIL  ") + name + (("   :: " + detail) if detail else ""))

    def summary(self):
        passed = sum(1 for _n, ok in self.checks if ok)
        total = len(self.checks)
        print("\n==== %d/%d checks passed ====" % (passed, total))
        return passed == total


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
        rep.control("baseline writes outside cwd", bool(escaped()), str(escaped()))

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
        rep.control("baseline injects a header", any("X-Injected" in r for r in seen))

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
        rep.control("baseline leaks the credential", any("SECRET" in r for r in seen))

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
        rep.control("baseline fails to follow", "PAYLOAD-OK" not in out, repr(out[:40]))

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
        rep.control("baseline exits 0 on truncation", rc == 0, "rc=%d" % rc)

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
        rep.control("baseline writes raw chunk framing", b"5\r\n" in saved(d), repr(saved(d)[:28]))

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
        rep.control("baseline sends a bodyless request", bool(seen) and rc == 0, "rc=%d" % rc)

    seen = []
    p = newport()
    serve(p, h_ok(seen))
    rc, _o, err, _d = run(new, ["-d", "@/nonexistent/nope", "http://127.0.0.1:%d/x" % p], "body")
    rep.check("missing body file is an error", rc == 2 and not seen,
              "rc=%d %s" % (rc, err.strip()[:70]))


def check_regressions(run, rep, new):
    """The fixes above must not break ordinary transfers."""
    print("\n[8] regressions: ordinary transfers still work")

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
    rep = Report()
    try:
        check_path_traversal(run, rep, binary, baseline, marker, marker2)
        check_crlf_injection(run, rep, binary, baseline)
        check_credential_replay(run, rep, binary, baseline)
        check_relative_location(run, rep, binary, baseline)
        check_truncation(run, rep, binary, baseline)
        check_crawl_dechunk(run, rep, binary, baseline)
        check_body_file(run, rep, binary, baseline)
        check_regressions(run, rep, binary)
    finally:
        for f in (marker, marker2):
            if os.path.exists(f):
                os.remove(f)
        if not args.keep and not args.workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    return 0 if rep.summary() else 1


if __name__ == "__main__":
    sys.exit(main())
