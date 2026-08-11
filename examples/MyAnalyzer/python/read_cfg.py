"""Read back myelectrons.root and print the electron kinematics."""

import FWCore.ParameterSet.Config as cms

process = cms.Process("READ")

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:myelectrons.root"),
)

process.analyzer = cms.EDAnalyzer("MyAnalyzer")

process.p = cms.Path(process.analyzer)
