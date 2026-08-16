"""Check beamspot.db from outside CMSSW, with python's own sqlite3.

The reader module already proved the payload comes back through the
EventSetup. This proves the file on disk is a genuine CMS conditions
database - the same TAG / IOV / PAYLOAD schema a real one has, written by
coral's sqlite backend - and not an opaque blob that only this build can
make sense of.
"""

import sqlite3
import sys

DB = "beamspot.db"
TAG = "BeamSpotObjects_test"
PAYLOAD_TYPE = "BeamSpotObjects"

# What a conditions database is made of. GLOBAL_TAG and GLOBAL_TAG_MAP are
# what a global tag would live in - empty here, but the schema is the real one.
EXPECTED_TABLES = {"GLOBAL_TAG", "GLOBAL_TAG_MAP", "IOV", "PAYLOAD", "TAG", "TAG_LOG"}


def fail(msg):
    print("FAILED: " + msg)
    sys.exit(1)


def main():
    con = sqlite3.connect(DB)

    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    missing = EXPECTED_TABLES - tables
    if missing:
        fail(f"{DB} is missing the conditions tables {sorted(missing)}")

    rows = list(con.execute("select NAME, TIME_TYPE, OBJECT_TYPE from TAG"))
    if len(rows) != 1:
        fail(f"expected exactly one tag, found {len(rows)}")
    name, time_type, object_type = rows[0]
    if name != TAG:
        fail(f"tag is {name!r}, expected {TAG!r}")
    if time_type != "Run":
        fail(f"tag time type is {time_type!r}, expected 'Run'")
    if object_type != PAYLOAD_TYPE:
        fail(f"tag payload type is {object_type!r}, expected {PAYLOAD_TYPE!r}")

    iovs = list(con.execute("select SINCE, PAYLOAD_HASH from IOV where TAG_NAME = ?", (TAG,)))
    if len(iovs) != 1:
        fail(f"expected exactly one IOV, found {len(iovs)}")
    since, payload_hash = iovs[0]

    payloads = list(
        con.execute("select OBJECT_TYPE, length(DATA) from PAYLOAD where HASH = ?", (payload_hash,))
    )
    if len(payloads) != 1:
        fail(f"IOV points at hash {payload_hash}, which has no payload")
    ptype, nbytes = payloads[0]
    if ptype != PAYLOAD_TYPE:
        fail(f"payload type is {ptype!r}, expected {PAYLOAD_TYPE!r}")
    if not nbytes:
        fail("payload BLOB is empty")

    print(f"{DB}: tag {name!r} ({object_type}, {time_type})")
    print(f"  IOV since {since} -> payload {payload_hash[:16]}..., {nbytes} bytes")
    print("sqlite conditions readback OK")


if __name__ == "__main__":
    main()
