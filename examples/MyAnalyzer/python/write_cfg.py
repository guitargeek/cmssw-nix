"""Produce a few events with toy electrons and write them to myelectrons.root."""

import FWCore.ParameterSet.Config as cms

process = cms.Process("WRITE")

process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))

process.source = cms.Source("EmptySource")

# the toy stand-in for the electron collection of a real MiniAOD file
process.slimmedElectrons = cms.EDProducer("MyElectronProducer")

process.out = cms.OutputModule(
    "PoolOutputModule",
    fileName=cms.untracked.string("myelectrons.root"),
)

process.p = cms.Path(process.slimmedElectrons)
process.e = cms.EndPath(process.out)
