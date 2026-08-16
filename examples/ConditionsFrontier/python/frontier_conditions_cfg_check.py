"""Check what the stub server actually received, from outside CMSSW.

FrontierProbe already asserted that the error it got back came from the
server. This looks at the other end of the wire: the request the server was
sent has to be a real Frontier query, not merely any HTTP request that
happened to arrive.
"""

import sys
import urllib.parse

REQUEST_LOG = "frontier_requests.log"


def fail(msg):
    print("FAILED: " + msg)
    sys.exit(1)


def main():
    try:
        with open(REQUEST_LOG) as f:
            requests = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        fail(f"{REQUEST_LOG} does not exist - the stub server never ran")

    if not requests:
        fail("the stub server was started but received no request at all")

    # e.g. /FrontierTest/Frontier/type=frontier_request:1:DEFAULT&encoding=BLOBzip5&p1=<base64>
    first = requests[0]

    if "/FrontierTest/" not in first:
        fail(f"request did not go to the servlet path CORAL was given: {first}")
    if "type=frontier_request" not in first:
        fail(f"request is not a frontier query: {first}")
    if "encoding=" not in first:
        fail(f"request carries no payload encoding: {first}")

    # p1 is the query itself, base64url of the zlib-compressed SQL
    params = urllib.parse.parse_qs(first.split("?", 1)[-1].split("/")[-1])
    query = params.get("p1", [""])[0]
    if not query:
        fail(f"request carries no query parameter: {first}")

    print(f"{REQUEST_LOG}: {len(requests)} request(s) reached the stub server")
    print(f"  servlet path and query look like Frontier: {first[:96]}...")
    print("frontier transport OK")


if __name__ == "__main__":
    main()
