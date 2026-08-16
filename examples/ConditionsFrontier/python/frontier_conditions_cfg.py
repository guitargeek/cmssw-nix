"""Talk to a Frontier server from CondCore, over HTTP, with no CERN access.

Starts python/frontier_stub.py on an ephemeral loopback port and points a
CondCore session at it through a frontier:// connect string. The stub answers
with a `<global_error>`, so the job is expected to get an error back - the
test is *which* error, see plugins/FrontierProbe.cc.

The stub runs as a subprocess rather than a thread: the config is executed by
cmsRun's embedded interpreter, which is in no way obliged to keep running
python threads once the C++ event loop takes over.
"""

import os
import shutil
import subprocess
import sys
import time

import FWCore.ParameterSet.Config as cms

HERE = os.path.dirname(os.path.abspath(__file__))
PORT_FILE = "frontier_port.txt"
REQUEST_LOG = "frontier_requests.log"

# must agree with MARKER in frontier_stub.py
MARKER = "cmssw-nix frontier stub: no database behind this endpoint"

for stale in (PORT_FILE, REQUEST_LOG):
    if os.path.exists(stale):
        os.remove(stale)

python3 = shutil.which("python3")
if python3 is None:
    raise RuntimeError("no python3 on PATH to run the frontier stub with")

# No atexit handler to shut this down, and no `with` block: cmsRun finalizes
# the interpreter once the config has been read, well before the event loop
# runs, and anything registered here would take the server down with it. The
# stub caps its own lifetime instead.
stub = subprocess.Popen(
    [python3, os.path.join(HERE, "frontier_stub.py"),
     "--port-file", PORT_FILE, "--request-log", REQUEST_LOG],
)

# the stub writes the port only once its socket is listening
deadline = time.time() + 30
while not os.path.exists(PORT_FILE):
    if time.time() > deadline:
        stub.terminate()
        raise RuntimeError("the frontier stub did not come up within 30 s")
    if stub.poll() is not None:
        raise RuntimeError(f"the frontier stub exited with {stub.returncode}")
    time.sleep(0.1)

with open(PORT_FILE) as f:
    port = int(f.read().strip())
print(f"frontier stub is on port {port}", file=sys.stderr)

# CORAL splits this into the server URL and the schema at the last slash, and
# prefixes the rest with http:// - so this becomes a query against
# http://127.0.0.1:<port>/FrontierTest for schema CMS_CONDITIONS
CONNECT = f"frontier://127.0.0.1:{port}/FrontierTest/CMS_CONDITIONS"

process = cms.Process("FRONTIER")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

process.source = cms.Source("EmptySource", firstRun=cms.untracked.uint32(1))

process.probe = cms.EDAnalyzer(
    "FrontierProbe",
    connect=cms.string(CONNECT),
    expectedError=cms.string(MARKER),
)

process.p = cms.Path(process.probe)
