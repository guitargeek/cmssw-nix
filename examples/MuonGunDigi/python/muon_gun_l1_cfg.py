# The Level-1 trigger: does every muon the gun fired fire the trigger?
#
# Every job so far has asked what the offline reconstruction makes of the
# event. The detector asks something else first. Of the 40 million bunch
# crossings a second, the Level-1 trigger keeps about 100 000, deciding within
# 4 us from coarse data the front ends send at every crossing - and an event
# it rejects is gone. For muons the decision comes from a chain of
# electronics this job emulates bit for bit on the simulated DT digis:
#
#   DT trigger primitives   the chamber electronics (BTI, TRACO, trigger
#                           server) find a track segment in each chamber
#   TwinMux                 merges the DT primitives with RPC hits
#   Kalman BMTF             the barrel muon track finder: a Kalman filter in
#                           firmware, through the four stations
#   uGMT                    the global muon trigger: merges the barrel,
#                           overlap and endcap track finders, removes
#                           duplicates, ranks, and hands the best eight muons
#                           to the menu
#
# This is Run 3's barrel chain. plugins/L1MuonMatch.cc then checks the uGMT
# output against the simulated muons: found in the triggered bunch crossing,
# with single-muon quality, the right charge, and a roughly right pt.
#
# Every parameter comes from the emulators' "fake" (from-python) producers
# and the lookup tables in the cms-data package L1Trigger-L1TMuon, which is
# how the emulators are run without a conditions database. These are the
# firmware settings of the emulators' defaults, not of any particular run.
#
# 20_1 only: the 10_6 configuration does not build the emulators.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import FWCore.ParameterSet.Config as cms

process = cms.Process("L1")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:muon_gun_digi.root"),
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

# --- geometry: the same 2018 description the digis were made in --------------
process.load("Configuration.Geometry.GeometryExtended2018_cff")
process.load("Geometry.MuonNumbering.muonNumberingInitialization_cfi")
process.load("Geometry.DTGeometryBuilder.dtGeometry_cfi")
process.DTGeometryESModule.applyAlignment = cms.bool(False)
# TwinMux maps RPC hits onto DT sectors through the RPC geometry
process.load("Geometry.RPCGeometryBuilder.rpcGeometry_cfi")

# --- DT trigger primitives ----------------------------------------------------
# The chamber trigger electronics, configured from python: BTI, TRACO and
# sector collector settings, and the TRACO lookup tables computed from the
# geometry rather than read from the database.
process.load("L1TriggerConfig.DTTPGConfigProducers.L1DTTPGConfig_cff")
from L1Trigger.DTTrigger.dtTriggerPrimitiveDigis_cfi import dtTriggerPrimitiveDigis
process.simDtTriggerPrimitiveDigis = dtTriggerPrimitiveDigis.clone(digiTag="simMuonDTDigis")

# --- TwinMux ------------------------------------------------------------------
# No RPC digis are simulated here (plugins/EmptyL1MuonInputs.cc), so TwinMux
# passes the DT primitives through.
process.load("L1Trigger.L1TTwinMux.fakeTwinMuxParams_cff")
process.simMuonRPCDigis = cms.EDProducer("EmptyRPCDigiProducer")
from L1Trigger.L1TTwinMux.simTwinMuxDigis_cfi import simTwinMuxDigis
process.simTwinMuxDigis = simTwinMuxDigis.clone()

# --- the barrel track finder ----------------------------------------------------
# The stub producer reads the BMTF masks; the Kalman filter's own constants
# are in its configuration and a lookup table file.
process.load("L1Trigger.L1TMuonBarrel.fakeBmtfParams_cff")
from L1Trigger.L1TMuonBarrel.simKBmtfStubs_cfi import simKBmtfStubs
from L1Trigger.L1TMuonBarrel.simKBmtfDigis_cfi import simKBmtfDigis
process.simKBmtfStubs = simKBmtfStubs.clone()
process.simKBmtfDigis = simKBmtfDigis.clone()

# --- the global muon trigger ----------------------------------------------------
# The overlap and endcap track finders and the calorimeter tower sums get
# empty inputs: the gun fires into the barrel (plugins/EmptyL1MuonInputs.cc).
# The uGMT cfi also defines a conditions source reading its prototype
# parameters from Frontier; only the producer is taken from it.
process.load("L1Trigger.L1TMuon.fakeGmtParams_cff")
process.emptyOverlapTF = cms.EDProducer("EmptyRegionalMuonCandProducer")
process.emptyEndcapTF = cms.EDProducer("EmptyRegionalMuonCandProducer")
process.emptyCaloTowers = cms.EDProducer("EmptyMuonCaloSumProducer")
from L1Trigger.L1TMuon.simGmtStage2Digis_cfi import simGmtStage2Digis
process.simGmtStage2Digis = simGmtStage2Digis.clone(
    overlapTFInput=cms.InputTag("emptyOverlapTF"),
    forwardTFInput=cms.InputTag("emptyEndcapTF"),
    triggerTowerInput=cms.InputTag("emptyCaloTowers"),
)

# --- the measurement ------------------------------------------------------------
process.l1Muons = cms.EDAnalyzer(
    "L1MuonMatch",
    simTracks=cms.InputTag("g4SimHits"),
    l1Muons=cms.InputTag("simGmtStage2Digis"),
    # the L1 eta and phi come from a few bits of hardware precision,
    # extrapolated to the vertex by a lookup table; measured, they agree with
    # the simulated direction to about 0.06
    maxDeltaR=cms.double(0.3),
    # 12 and above is what the single-muon seeds of the L1 menu accept
    minQuality=cms.int32(12),
    # Measured: 19/20, all with quality 14 or 15 but one at 12. The muon that
    # did not trigger left the barrel at eta -0.25, around the gap between
    # wheels 0 and -1.
    minEfficiency=cms.double(0.8),
    # Measured: 19/19.
    minChargeAgreement=cms.double(0.9),
    # Measured: 1.16. The L1 pt is not meant to be unbiased: the scale is
    # calibrated so that a threshold sits at the 90% efficiency point of the
    # turn-on, which puts the typical muon above its true pt.
    minMedianPtRatio=cms.double(0.9),
    maxMedianPtRatio=cms.double(1.4),
)

process.p = cms.Path(
    process.simMuonRPCDigis
    * process.simDtTriggerPrimitiveDigis
    * process.simTwinMuxDigis
    * process.simKBmtfStubs
    * process.simKBmtfDigis
    * process.emptyOverlapTF
    * process.emptyEndcapTF
    * process.emptyCaloTowers
    * process.simGmtStage2Digis
    * process.l1Muons
)
