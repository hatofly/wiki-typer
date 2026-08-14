#!/usr/bin/env python3

import argparse
import http.server
import socketserver
import threading
import time
import sys
import socket

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def run_server(minutes: int, port: int):
    handler = http.server.SimpleHTTPRequestHandler

    with ReusableTCPServer(("", port), handler) as httpd:
        print(f"Serving HTTP on port {port} for {minutes} minutes")

        # タイマー用スレッド
        def shutdown_later():
            time.sleep(minutes * 60)
            print("Time elapsed. Shutting down server.")
            httpd.shutdown()

        t = threading.Thread(target=shutdown_later, daemon=True)
        t.start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nInterrupted. Shutting down.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=int, required=True, help="server lifetime in minutes")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.min <= 0:
        print("--min must be positive", file=sys.stderr)
        sys.exit(1)

    run_server(args.min, args.port)

if __name__ == "__main__":
    main()