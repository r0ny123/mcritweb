"""usage: countproxy.py <listen_port> <target_host> <target_port> <counter_log>
HTTP reverse proxy that forwards every request to the target and appends one line per
request (method + path) to counter_log, so calls made through it can be counted exactly.
"""
import http.server
import sys
import urllib.request
import threading

listen_port = int(sys.argv[1])
target_host = sys.argv[2]
target_port = int(sys.argv[3])
counter_log = sys.argv[4]
target_base = f"http://{target_host}:{target_port}"
lock = threading.Lock()

class Handler(http.server.BaseHTTPRequestHandler):
    def _proxy(self):
        with lock:
            with open(counter_log, "a") as f:
                f.write(self.command + " " + self.path + "\n")
        url = target_base + self.path
        body = None
        length = self.headers.get("Content-Length")
        if length:
            body = self.rfile.read(int(length))
        req = urllib.request.Request(url, data=body, method=self.command)
        for h in ("Content-Type",):
            if self.headers.get(h):
                req.add_header(h, self.headers.get(h))
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                for k, v in resp.getheaders():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_PUT(self):
        self._proxy()

    def do_DELETE(self):
        self._proxy()

    def log_message(self, fmt, *args):
        pass

class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

server = ThreadingHTTPServer(("127.0.0.1", listen_port), Handler)
print(f"counting proxy 127.0.0.1:{listen_port} -> {target_base}, logging to {counter_log}", flush=True)
server.serve_forever()
