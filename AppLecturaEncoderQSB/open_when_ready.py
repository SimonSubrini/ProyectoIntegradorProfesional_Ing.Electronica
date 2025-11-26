#!/usr/bin/env python3
"""
open_when_ready.py
Uso: python open_when_ready.py <url> [timeout_seconds]

Espera hasta que <url> responda (HTTP 200-399) o agote timeout, luego abre el navegador.
"""

import sys
import time
import urllib.request
import webbrowser

def is_up(url, timeout=2):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'python-http-client'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            return 200 <= code < 400
    except Exception:
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: open_when_ready.py <url> [timeout_seconds]")
        sys.exit(1)

    url = sys.argv[1]
    timeout_total = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
    interval = 0.5
    elapsed = 0.0

    while elapsed < timeout_total:
        if is_up(url):
            webbrowser.open(url)
            return
        time.sleep(interval)
        elapsed += interval

    # Timeout: intentarlo de todas formas
    webbrowser.open(url)

if __name__ == "__main__":
    main()
