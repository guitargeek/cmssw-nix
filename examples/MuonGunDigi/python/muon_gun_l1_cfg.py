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
import os
import sys

import FWCore.ParameterSet.Config as cms

sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_l1_muon_emulation

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

# --- the emulation: muon_gun_stages.add_l1_muon_emulation -----------------------
# DT trigger primitives -> TwinMux -> Kalman BMTF -> uGMT, each configured
# from python: the chamber electronics' settings and the TRACO lookup tables
# computed from the geometry, the BMTF masks and Kalman constants, and the
# uGMT parameters. No RPC digis are simulated (plugins/EmptyL1MuonInputs.cc),
# so TwinMux passes the DT primitives through; the overlap and endcap track
# finders and the calorimeter tower sums get empty inputs, as the gun fires
# into the barrel.
process.l1Emulation = add_l1_muon_emulation(process)

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

process.p = cms.Path(process.l1Emulation * process.l1Muons)
