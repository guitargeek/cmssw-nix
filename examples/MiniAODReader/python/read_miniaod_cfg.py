"""Read a real CMS Open Data UL2016 MiniAODSIM file (see README.md for the
download command)."""

import FWCore.ParameterSet.Config as cms

process = cms.Process("READ")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(10))

process.source = cms.Source(
    "PoolSource", fileNames=cms.untracked.vstring("file:miniaod.root")
)

process.analyzer = cms.EDAnalyzer("MiniAODAnalyzer")

process.p = cms.Path(process.analyzer)
