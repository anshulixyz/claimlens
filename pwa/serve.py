#!/usr/bin/env python3
"""Tiny static server for local PWA preview/testing.

Usage:  python3 code/pwa/serve.py   (serves this directory on :8138)
For real camera use, any static server on localhost/HTTPS works
(e.g. `python3 -m http.server 8000` from inside code/pwa).
"""
import http.server
import os
import socketserver

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("PWA_PORT", "8138"))

with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"serving evidence-capture PWA on http://localhost:{PORT}")
    httpd.serve_forever()
