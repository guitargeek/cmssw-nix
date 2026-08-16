"""Read the BeamSpotObjects payload back through PoolDBESSource.

Needs beamspot.db, so run write_conditions_cfg.py first. The reader module
asserts the values it gets out of the EventSetup against the ones the writer
put in, and throws if they do not match.
"""

import FWCore.ParameterSet.Config as cms

process = cms.Process("READCOND")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(3))

process.source = cms.Source(
    "EmptySource",
    firstRun=cms.untracked.uint32(1),
)

process.load("CondCore.CondDB.CondDB_cfi")
process.CondDB.connect = cms.string("sqlite_file:beamspot.db")

# The ordinary conditions path: this is the same ESSource a real job points at
# a global tag, with a local file instead of a frontier server.
process.beamSpotSource = cms.ESSource(
    "PoolDBESSource",
    process.CondDB,
    toGet=cms.VPSet(
        cms.PSet(
            record=cms.string("BeamSpotObjectsRcd"),
            tag=cms.string("BeamSpotObjects_test"),
        )
    ),
)

process.reader = cms.EDAnalyzer(
    "BeamSpotDBReader",
    expectedX=cms.double(0.0918),
    expectedY=cms.double(-0.0374),
    expectedZ=cms.double(0.4271),
    expectedSigmaZ=cms.double(3.7215),
    tolerance=cms.double(1e-9),
)

process.p = cms.Path(process.reader)
