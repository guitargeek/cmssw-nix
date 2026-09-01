# Readback validation of the simulation output, from outside the job.
#
# The analyzer in the path already asserts on the hits, but it sees them as
# objects the framework handed it in memory. This opens the written file with
# FWLite - the way an analysis reads an EDM file - so it also covers the part
# the analyzer cannot: that the SimHit collections survived being streamed to
# ROOT and read back, which is exactly what DIGI and RECO will do to them next.
#
# FWLite rather than plain ROOT because a SIM file holds edm::Wrapper objects
# with the collection inside; reading those by hand through TTree::Draw
# depends on the split level, while FWLite goes through the same dictionaries
# CMSSW itself uses.
import os
import sys

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gSystem.Load("libFWCoreFWLite")
ROOT.FWLiteEnabler.enable()

from DataFormats.FWLite import Events, Handle  # noqa: E402

FILENAME = "muon_gun_sim.root"

# instance label -> the minimum number of events that must contain hits
REQUIRED = {
    "TrackerHitsPixelBarrelLowTof": 1,
    "TrackerHitsTIBLowTof": 1,
    "TrackerHitsTOBLowTof": 1,
    "MuonDTHits": 1,
}

events = Events(FILENAME)
n = events.size()
print(f"{FILENAME}: {n} events")
if n == 0:
    sys.exit("the file has no events")

# CMSSW_20_1 puts the persistent data formats in versioned I/O namespaces:
# the dictionary declares io_v1::PSimHit, not PSimHit, so the 10_6 spelling
# fails here with "edm::Wrapper<std::vector<PSimHit>> is not a known C++
# class" - the class the file was written with simply has another name. The
# branch names are unchanged, so only the type handed to Handle moves.
_ns = "" if os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_") else "io_v1::"

handle = Handle(f"std::vector<{_ns}PSimHit>")
tracks = Handle(f"std::vector<{_ns}SimTrack>")

nonempty = {k: 0 for k in REQUIRED}
totals = {k: 0 for k in REQUIRED}
n_tracks = 0

for event in events:
    for instance in REQUIRED:
        event.getByLabel(("g4SimHits", instance), handle)
        if not handle.isValid():
            continue
        hits = handle.product()
        if hits.size() > 0:
            nonempty[instance] += 1
            totals[instance] += hits.size()

    event.getByLabel(("g4SimHits", ""), tracks)
    if tracks.isValid():
        n_tracks += tracks.product().size()

failures = []
for instance, minimum in REQUIRED.items():
    print(f"  g4SimHits:{instance}: {totals[instance]} hits, "
          f"non-empty in {nonempty[instance]}/{n} events")
    if nonempty[instance] < minimum:
        failures.append(
            f"g4SimHits:{instance} has hits in {nonempty[instance]} events, need >= {minimum}")

print(f"  SimTracks: {n_tracks}")
if n_tracks == 0:
    failures.append("no SimTracks in the file")

if failures:
    for msg in failures:
        print(f"FAIL: {msg}")
    sys.exit(1)

print("simulation output OK")
