"""A minimal stand-in for a Frontier servlet, enough to prove the transport.

The real thing translates an HTTP request into SQL against the CMS conditions
Oracle databases and returns the result set in Frontier's binary encoding.
This serves the one response a client needs no database to interpret: a
`<global_error>`, which the frontier client surfaces verbatim as the reason
the query failed.

That makes it a precise probe. If a CMSSW job reports the marker below, then
every layer in between did its job - CondCore built a connection, CORAL
loaded liblcg_FrontierAccess.so and translated the frontier:// URL, the
frontier client built the request, sent it over HTTP, parsed the XML, and
propagated the error back up. Only the payload decoding is left untested,
and that needs a real server.

    python3 frontier_stub.py --port-file port.txt --request-log requests.log

Binds an ephemeral port on the loopback interface and writes it to
--port-file, so nothing has to agree on a port number in advance and two
runs cannot collide.
"""

import argparse
import http.server
import sys
import threading

MARKER = "cmssw-nix frontier stub: no database behind this endpoint"

RESPONSE = f"""<?xml version="1.0" encoding="US-ASCII"?>
<frontier version="3.31" xmlversion="1.0">
<global_error msg="{MARKER}"/>
</frontier>
""".encode()


def make_handler(request_log):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            with open(request_log, "a") as f:
                f.write(self.path + "\n")
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.send_header("Content-Length", str(len(RESPONSE)))
            self.end_headers()
            self.wfile.write(RESPONSE)

        def log_message(self, *args):
            pass  # the request log is the record we care about

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port-file", required=True)
    p.add_argument("--request-log", required=True)
    # The stub has to outlive the config that starts it - cmsRun finalizes
    # its interpreter before the event loop, so the config cannot shut this
    # down afterwards. A lifetime cap is what stops an interactive run from
    # leaving it behind; the nix sandbox would clean it up either way.
    p.add_argument("--lifetime", type=float, default=60.0)
    args = p.parse_args()

    open(args.request_log, "w").close()

    server = http.server.HTTPServer(("127.0.0.1", 0), make_handler(args.request_log))
    port = server.server_address[1]

    # write the port only once the socket is listening, so a reader that sees
    # the file can connect immediately
    with open(args.port_file, "w") as f:
        f.write(str(port))

    print(f"frontier stub listening on 127.0.0.1:{port}", flush=True)
    threading.Timer(args.lifetime, server.shutdown).start()
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
