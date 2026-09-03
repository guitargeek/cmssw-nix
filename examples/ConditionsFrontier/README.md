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

## The teardown abort, and the patch that fixes it

This example used to do all of the above correctly and then **abort with exit
code 134** on the way out, after the event loop and after the MessageLogger
summary — every result above was already in hand:

```
terminate called after throwing an instance of 'boost::wrapexcept<boost::lock_error>'
  what():  boost: mutex lock failed in pthread_mutex_lock: Invalid argument
```

The backtrace was unambiguous:

```
coral::Context::~Context()                          <- from exit()
 coral::ConnectionService::ConnectionService::~ConnectionService()
  coral::ConnectionService::ConnectionPool::clearConnectionPool()
   coral::ConnectionService::ConnectionHandle::~ConnectionHandle()
    coral::FrontierAccess::Connection::~Connection()
     coral::FrontierAccess::Connection::disconnect()   <- throws here
```

`disconnect()` begins by locking `DomainProperties::lock()`. That was a
namespace-scope `static boost::mutex` in `liblcg_FrontierAccess.so`, while the
`Context` that owns the connection pool is torn down from `exit()` over in
`liblcg_ConnectionService.so`. Nothing orders static destruction between two
shared libraries, and in practice the mutex went first: `pthread_mutex_lock`
returned `EINVAL`, boost turned that into `lock_error`, and an exception
leaving a destructor is `std::terminate`.

It was not something this example caused. It happened just as reliably when
the server refused the connection, so merely *creating* a Frontier connection
was enough — which meant every real job in this build that read conditions
over Frontier aborted, after doing its work.

`pkgs/coral-frontier-lock-lifetime.patch` gives that mutex a lifetime that
outlasts teardown: it is allocated once, on first use, and never deleted. That
removes the dependency on cross-library destruction order rather than working
around it, at the cost of leaking one mutex at process exit. The job now exits
0, and the example is part of `nix flake check`.

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
squid — the package already ships one, see `gen/site-local-config.xml` and
`gen/site-local-config-10_6.xml`.

Runs in both releases.

## Building and running

From this directory, inside `nix develop .#cmssw_10_6_30` or `nix develop
.#default`:

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
