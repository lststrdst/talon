from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
from threading import Thread
import unittest
from urllib.parse import parse_qs, urlsplit


SCRIPT = (Path(__file__).resolve().parents[1] / "plugins/talon/skills/checks/assets/sentry/query_issues.py")


@unittest.skipUnless(shutil.which("openssl"), "openssl is needed for the local HTTPS fixture")
class SentryIssuesTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        self.cert = directory / "cert.pem"
        key = directory / "key.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048", "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
            "-keyout", str(key), "-out", str(self.cert),
        ], check=True, capture_output=True)

        self.requests = []
        self.project = "test-project"
        self.redirect = False
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                test.requests.append((self.path, self.headers.get("Authorization")))
                if test.redirect:
                    self.send_response(302)
                    self.send_header("Location", "/redirected")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Link", '<https://example.invalid/?cursor=123%3A0%3A0>; '
                                 'rel="next"; results="true"')
                self.end_headers()
                issue = {"id": "1", "project": {"slug": test.project}, "shortId": "TEST-1",
                         "title": "fixture secret", "user": {"email": "example@invalid"}}
                self.wfile.write(json.dumps([issue]).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(server.server_close)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        self.origin = f"https://localhost:{server.server_port}"
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)

    def invoke(self, *extra):
        env = dict(os.environ, SENTRY_AUTH_TOKEN="fixture-bearer", no_proxy="localhost")
        return subprocess.run([
            sys.executable, str(SCRIPT), "--origin", self.origin, "--organization", "fixture-org",
            "--project", "test-project", "--environment", "fixture", "--period", "2h", "--limit", "3",
            "--ca-file", str(self.cert), *extra,
        ], env=env, capture_output=True, text=True, timeout=15)

    def test_issues_request_is_scoped_and_summary_excludes_payload(self):
        result = self.invoke("--cursor", "7:0:0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "issues": [{"id": "1", "shortId": "TEST-1"}], "next_cursor": "123:0:0",
        })
        self.assertEqual(len(self.requests), 1)
        path, auth = self.requests[0]
        self.assertEqual(auth, "Bearer fixture-bearer")
        self.assertEqual(urlsplit(path).path, "/api/0/organizations/fixture-org/issues/")
        self.assertEqual(parse_qs(urlsplit(path).query), {
            "project": ["test-project"], "environment": ["fixture"], "statsPeriod": ["2h"],
            "query": ["is:unresolved"], "sort": ["date"], "limit": ["3"], "cursor": ["7:0:0"],
        })

    def test_redirect_is_rejected_without_visiting_target(self):
        self.redirect = True
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertIn("HTTP 302", result.stderr)
        self.assertEqual(len(self.requests), 1)

    def test_issue_outside_project_is_rejected(self):
        self.project = "different-project"
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertIn("outside the requested project", result.stderr)
        self.assertEqual(result.stdout, "")
