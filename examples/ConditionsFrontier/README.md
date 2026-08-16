# ConditionsFrontier

Proves the **Frontier transport** works: a CondCore session opened on a
`frontier://` connect string reaches an HTTP server and gets its answer back.

Frontier is how a real CMS job reads a global tag — the conditions live in
Oracle at CERN, and jobs everywhere read them over HTTP through a hierarchy
of caching squids. Without it, `PoolDBESSource` can only open a local sqlite
file (see [../ConditionsSqlite](../ConditionsSqlite)).

Two things had to be packaged for this:

* `pkgs/frontier-client.nix` — the Fermilab frontier client, which is what
  turns a query into an HTTP request. It bundles its own HTTP client rather
  than using libcurl, so it needs only expat, openssl, zlib and pacparser.
* `gen/coral-CMakeLists.txt` now builds CORAL's `FrontierAccess` backend
  against it, producing `liblcg_FrontierAccess.so`. CMSSW never links that —
  CoralKernel dlopens it the first time a `frontier://` string shows up.

## What is and is not tested here

`python/frontier_stub.py` stands in for a Frontier servlet. It answers every
query with a `<global_error>` carrying a marker string, which is the one
response a client can interpret without a database behind it.

That makes for a precise test, because of what it rules out. If CORAL had
been built without the Frontier backend the job would fail in the plugin
manager, long before any socket was opened; if the frontier client were
broken it would fail in the transport. Getting the *stub's own message* back
means CondCore, CORAL's `FrontierAccess`, the frontier client, HTTP and the
XML response parser all did their jobs. `FrontierProbe` asserts exactly that,
and treats any other error as a failure.

The check script then looks at the other end of the wire and confirms the
server was sent a real Frontier query — the servlet path, `type=frontier_request`,
an encoding, and a compressed query parameter.

## The catch: cmsRun aborts at exit

The job does all of the above correctly and then **aborts with exit code 134**
on the way out:

```
terminate called after throwing an instance of 'boost::wrapexcept<boost::lock_error>'
  what():  boost: mutex lock failed in pthread_mutex_lock: Invalid argument
```

This happens after the event loop, after the MessageLogger summary — every
result above is already in hand. The backtrace is unambiguous:

```
coral::Context::~Context()                          <- from exit()
 coral::ConnectionService::ConnectionService::~ConnectionService()
  coral::ConnectionService::ConnectionPool::clearConnectionPool()
   coral::ConnectionService::ConnectionHandle::~ConnectionHandle()
    coral::FrontierAccess::Connection::~Connection()
     coral::FrontierAccess::Connection::disconnect()   <- throws here
```

`disconnect()` starts by locking `m_domainProperties.lock()`, a `boost::mutex`
owned by the Frontier plugin's `Domain`. At `exit()` the `Domain` has already
been destroyed, so the lock fails, and the exception escapes a destructor —
which is `std::terminate`.

It is an upstream destruction-order bug between `liblcg_FrontierAccess.so`
and `liblcg_ConnectionService.so`, not something this example causes: it
happens just as reliably when the server refuses the connection, so merely
*creating* a Frontier connection is enough. The same code against the sqlite
backend exits 0, and `purgeConnectionPool()` in `endJob` does not release the
connection either. Fixing it properly means patching CORAL's teardown.

Because of this the example is **not part of `nix flake check`** — see
`_excluded` in `examples/jobs.json`. Any real job in this build that reads
conditions over Frontier will hit the same abort, after doing its work.

## What else is not tested

Decoding a real payload, which needs a real server.
This machine cannot reach one: ports 8000, 3128 and 8443 on
`cmsfrontier.cern.ch` are all blocked here, as is 443 (DNS resolves and
general HTTPS egress works, so it is a port filter, not a routing problem).
Where frontier *is* reachable, the natural next test is a real global tag:

```python
process.GlobalTag = cms.ESSource(
    "PoolDBESSource",
    connect=cms.string("frontier://FrontierProd/CMS_CONDITIONS"),
    globaltag=cms.string("106X_dataRun2_v37"),
)
```

which additionally needs a site-local-config that maps `FrontierProd` to a
squid — the package already ships one, see `gen/site-local-config-10_6.xml`.

This example needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30`:

```bash
cmake -B build -S . -G Ninja
cmake --build build

export LD_LIBRARY_PATH=$PWD/build:$LD_LIBRARY_PATH
edmPluginRefresh $PWD/build

cmsRun python/frontier_conditions_cfg.py
python3 python/frontier_conditions_cfg_check.py
```

Expected output:

```
frontier stub listening on 127.0.0.1:NNNNN
connecting to frontier://127.0.0.1:NNNNN/FrontierTest/CMS_CONDITIONS
the frontier server was reached, and answered: ... Server has signalled Global
Error [cmssw-nix frontier stub: no database behind this endpoint] ...
frontier_requests.log: 1 request(s) reached the stub server
frontier transport OK
```
