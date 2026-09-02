# Muon reconstruction: DT digis -> drift-time rec hits -> 4D segments ->
# seeds -> a standalone muon track fitted in the return yoke, and then the
# question this stage exists to answer - does the muon system, on its own,
# find the muons the gun fired and measure them?
#
# The tracker measured them to 0.8% (python/muon_gun_tracks_cfg.py). The muon
# system will do far worse, and that is the physics: a muon reaching the
# chambers has crossed the calorimeters and the return yoke, several metres of
# material, and the multiple scattering in it dominates the measurement. What
# the muon system does have is a very long lever arm in a field that reverses
# sign inside the iron, which is why CMS measures muons with both and why the
# standalone track is worth reconstructing at all.
#
# This is the same chain as examples/MuonChain, whose digis come from a
# hand-written ToyMuonTrackDigiProducer firing one straight 50 GeV muon
# through wheel 0, sector 1. Here they come from Geant4 transporting real
# muons through the real chambers.
#
# Only DT is reconstructed. The gun fires into |eta| < 0.8, which is the
# barrel: CSC is endcap and sees nothing, and the RPC digitiser is packaged
# but not run here.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os

import FWCore.ParameterSet.Config as cms

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("MUONS")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:muon_gun_digi.root"),
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

# --- geometry: the same 2018 description the digis were made in --------------
process.load("Configuration.Geometry.GeometryExtended2018_cff")
process.TrackerParametersESModule = cms.ESProducer("TrackerParametersESModule")
process.trackerTopology = cms.ESProducer("TrackerTopologyEP")
# New in 20_1: the tracker digi geometry depends on a per-det additional
# parameters record that did not exist in the 10_6 era.
if not _is_10_6:
    process.TrackerAdditionalParametersPerDetESModule = cms.ESProducer(
        "TrackerAdditionalParametersPerDetESModule"
    )
process.TrackerDigiGeometryESModule = cms.ESProducer(
    "TrackerDigiGeometryESModule",
    fromDDD=cms.bool(True),
    applyAlignment=cms.bool(False),
    alignmentsLabel=cms.string(""),
    appendToDataLabel=cms.string(""),
)
# The muon navigation is defined over tracker *and* muon layers, and the
# standalone track loader fills the reco::Track hit pattern through
# TrackerTopology, so the tracker geometry has to be here even though no
# tracker hit is read.
process.load("RecoTracker.GeometryESProducer.TrackerRecoGeometryESProducer_cfi")
process.load("TrackingTools.RecoGeometry.GlobalDetLayerGeometryESProducer_cfi")

process.load("Geometry.MuonNumbering.muonNumberingInitialization_cfi")
process.load("Geometry.DTGeometryBuilder.dtGeometry_cfi")
process.DTGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.CSCGeometryBuilder.cscGeometry_cfi")
process.CSCGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.RPCGeometryBuilder.rpcGeometry_cfi")

process.GlobalTrackingGeometryESProducer = cms.ESProducer("GlobalTrackingGeometryESProducer")
process.load("RecoMuon.DetLayers.muonDetLayerGeometry_cfi")
process.load("RecoMuon.TransientTrackingRecHit.MuonTransientTrackingRecHitBuilder_cfi")

# The field the muon was bent by, in the yoke as well as the tracker. A muon
# measured in the chambers is measured almost entirely by the return field, so
# this matters here even more than it did for the tracker fit.
process.load("MagneticField.Engine.volumeBasedMagneticField_160812_cfi")

# --- beam spot: the one the simulation smeared over -------------------------
# The standalone track is referred to the beam spot when it is loaded.
process.BeamSpotFakeConditions = cms.ESSource(
    "BeamSpotFakeConditions",
    getDataFromFile=cms.bool(False),
    X0=cms.double(0.0107682), Y0=cms.double(0.041722), Z0=cms.double(0.035748),
    dxdz=cms.double(0.0), dydz=cms.double(0.0),
    sigmaZ=cms.double(3.5), widthX=cms.double(0.0007), widthY=cms.double(0.0007),
    emittanceX=cms.double(0.0), emittanceY=cms.double(0.0),
    betaStar=cms.double(0.0),
    errorX0=cms.double(0.0002), errorY0=cms.double(0.0002), errorZ0=cms.double(0.02),
    errorSigmaZ=cms.double(0.01), errordxdz=cms.double(0.0001),
    errordydz=cms.double(0.0001), errorWidth=cms.double(0.0002),
)
process.offlineBeamSpot = cms.EDProducer("BeamSpotProducer")

# --- DT local reconstruction ------------------------------------------------
# The drift-time synchronisation has to undo exactly what the digitiser
# applied - and that means the correction *type* as well as the 500 ns offset.
# The digitiser runs DTDigiSyncTOFCorr with TOFCorrection = 3, which subtracts
# the flight time to the superlayer centre. The reconstruction has to add the
# same term back, and tofCorrType is what chooses it:
#
#   digi time   = t_drift + |r_hit|/c + prop + 500 - |r_superlayer|/c
#   reco offset = 500 - f2i + prop - tofCorr
#
#   tofCorrType = 1  ->  tofCorr = (|r_chamber| - |r_hit|)/c, and the two
#                        flight-time terms cancel to the few cm between the
#                        chamber and superlayer centres: ~0.1 ns.
#   tofCorrType = 0  ->  tofCorr = -|r_hit|/c, so the reco *adds* the flight
#                        time the digitiser *subtracted*. Nothing cancels and
#                        every drift time is short by |r_superlayer|/c: 15 ns
#                        at MB1, 25 ns at MB4, which at 54.3 um/ns is a 0.8-1.3
#                        mm bias against an assumed hit error of 200 um.
#
# DTLinearDriftAlgo_cfi defaults tofCorrType to 0, so this has to be set. The
# failure is quiet in a way worth knowing about: the bias is nearly common to a
# chamber, so the segment absorbs it into its own position and angle and still
# fits. What it cannot absorb is that the bias grows with radius, so the
# stations disagree with each other, and only the track fit across them sees
# it - as chi2/ndof of 112 instead of 1.8.
from RecoLocalMuon.DTRecHit.dt1DRecHits_LinearDrift_cfi import dt1DRecHits as _dt1DRecHits

process.dt1DRecHits = _dt1DRecHits.clone(dtDigiLabel=cms.InputTag("simMuonDTDigis"))
process.dt1DRecHits.recAlgoConfig.tTrigMode = cms.string("DTTTrigSyncTOFCorr")
process.dt1DRecHits.recAlgoConfig.tTrigModeConfig.tTrig = cms.double(500.0)
process.dt1DRecHits.recAlgoConfig.tTrigModeConfig.tofCorrType = cms.int32(1)

from RecoLocalMuon.DTSegment.dt4DSegments_CombPatternReco4D_LinearDrift_cfi import (
    dt4DSegments as _dt4DSegments,
)

process.dt4DSegments = _dt4DSegments.clone(recHits1DLabel=cms.InputTag("dt1DRecHits"))
for _cfg in (
    process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.recAlgoConfig,
    process.dt4DSegments.Reco4DAlgoConfig.recAlgoConfig,
):
    _cfg.tTrigMode = cms.string("DTTTrigSyncTOFCorr")
    _cfg.tTrigModeConfig.tTrig = cms.double(500.0)
    _cfg.tTrigModeConfig.tofCorrType = cms.int32(1)

# perform_delta_rejecting is required by DTSegmentUpdator and absent from
# this cfi. It belongs to the pattern-recognition algo config, not to the
# rec-hit algo config inside it. The LinearDriftFromDB variant of the same
# algorithm sets it True and the cosmic-data ones False; True is right here,
# because rejectBadHits drops hits inconsistent with the segment fit and a
# simulated collision muon really does make delta rays along its path.
# examples/MuonChain sets False - its toy digis have none.
process.dt4DSegments.Reco4DAlgoConfig.perform_delta_rejecting = cms.bool(True)
process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.perform_delta_rejecting = (
    cms.bool(True)
)

# --- seeds and the standalone fit -------------------------------------------
# DT only: the gun fires into the barrel, so there are no CSC hits, and the RPC
# digitiser is packaged but not run here.
from RecoMuon.MuonSeedGenerator.ancientMuonSeed_cfi import ancientMuonSeed as _ancientMuonSeed

process.ancientMuonSeed = _ancientMuonSeed.clone(
    EnableCSCMeasurement=cms.bool(False),
    EnableRPCMeasurement=cms.bool(False),
)

process.load("RecoMuon.StandAloneMuonProducer.standAloneMuons_cff")
for _pset in (
    process.standAloneMuons.STATrajBuilderParameters.FilterParameters,
    process.standAloneMuons.STATrajBuilderParameters.BWFilterParameters,
):
    _pset.EnableCSCMeasurement = cms.bool(False)
    _pset.EnableRPCMeasurement = cms.bool(False)

# --- the measurement --------------------------------------------------------
# The same analyzer the tracking job uses, pointed at the standalone muons.
# The bounds are far looser and that is the physics: a muon reaching the
# chambers has crossed the calorimeters and the return yoke, and the multiple
# scattering in several metres of material dominates the measurement. The
# tracker's 0.8% is not available here.
process.muons = cms.EDAnalyzer(
    "TrackResolution",
    tracks=cms.InputTag("standAloneMuons"),
    simTracks=cms.InputTag("g4SimHits"),
    minPt=cms.double(1.0),
    # a wider cone than the tracker's 0.1: a standalone muon is extrapolated
    # back through the yoke, so its direction at the beam line is coarse
    maxDeltaR=cms.double(0.3),
    # Measured: 11.4%, which is the standalone barrel resolution CMS quotes
    # for muons of this momentum. The bound is 20% - loose enough for twenty
    # muons of statistics, tight enough to notice the chain degrading.
    maxMedianPtResolution=cms.double(0.2),
    # Measured: 19/20. Not 20/20 because a standalone track needs segments in
    # at least two stations and one muon did not give them.
    minEfficiency=cms.double(0.8),
    # At 11% the curvature sign is no longer ambiguous for these muons and all
    # 19 charges are right, but 20 muons is thin statistics for demanding
    # perfection, so the bound is one mistake.
    minChargeAgreement=cms.double(0.9),
    # The bound that matters, and the one this example did not have. Measured:
    # 1.8, against 112 when the drift times were decoded with the wrong
    # time-of-flight convention. Nothing else here separated those two: the
    # momentum was still 23% (inside a 50% bound) and the efficiency 75%
    # (inside a 50% bound), so the job passed while the fit was nonsense.
    maxMedianChi2=cms.double(5.0),
)

# 20_1 took the det-info map away from the SiStripDetInfoFileReader service and
# made it a parameter of each fake ES source instead. Modules loaded from their
# cfis carry it already; ones declared by hand here do not, and the framework
# refuses to construct them without it. Done by walking the ES sources rather
# than naming them, so a source added later cannot quietly miss out.
if not _is_10_6:
    _detinfo = cms.FileInPath("CalibTracker/SiStripCommon/data/SiStripDetInfo.dat")
    for _essrc in process.es_sources_().values():
        if _essrc.type_().startswith("SiStrip") and _essrc.type_().endswith("FakeESSource"):
            if not hasattr(_essrc, "SiStripDetInfoFile"):
                _essrc.SiStripDetInfoFile = _detinfo

process.p = cms.Path(
    process.offlineBeamSpot
    * process.dt1DRecHits
    * process.dt4DSegments
    * process.ancientMuonSeed
    * process.standAloneMuons
    * process.muons
)
