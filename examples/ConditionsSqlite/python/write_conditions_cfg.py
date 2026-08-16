"""Write a BeamSpotObjects payload into a local sqlite conditions database.

Produces beamspot.db, which read_conditions_cfg.py reads back through
PoolDBESSource. Run this one first.
"""

import os

import FWCore.ParameterSet.Config as cms

# a fresh database every time: PoolDBOutputService appends to an existing tag,
# and a leftover file from an earlier run would hide a writer that silently
# stopped working
if os.path.exists("beamspot.db"):
    os.remove("beamspot.db")

process = cms.Process("WRITECOND")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

# EmptySource with a run number: conditions are keyed by IOV, so the job needs
# a place in time even though there is no input file
process.source = cms.Source(
    "EmptySource",
    firstRun=cms.untracked.uint32(1),
)

process.load("CondCore.CondDB.CondDB_cfi")
process.CondDB.connect = cms.string("sqlite_file:beamspot.db")

process.PoolDBOutputService = cms.Service(
    "PoolDBOutputService",
    process.CondDB,
    timetype=cms.untracked.string("runnumber"),
    toPut=cms.VPSet(
        cms.PSet(
            record=cms.string("BeamSpotObjectsRcd"),
            tag=cms.string("BeamSpotObjects_test"),
        )
    ),
)

process.writer = cms.EDAnalyzer(
    "BeamSpotDBWriter",
    record=cms.string("BeamSpotObjectsRcd"),
    x=cms.double(0.0918),
    y=cms.double(-0.0374),
    z=cms.double(0.4271),
    sigmaZ=cms.double(3.7215),
)

process.p = cms.Path(process.writer)
