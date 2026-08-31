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
import FWCore.ParameterSet.Config as cms

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
# applied: DTDigiSyncTOFCorr with the same 500 ns offset. Get this wrong and
# every drift distance is displaced by a constant, the segments still fit, and
# the muon comes out at the wrong angle.
from RecoLocalMuon.DTRecHit.dt1DRecHits_LinearDrift_cfi import dt1DRecHits as _dt1DRecHits

process.dt1DRecHits = _dt1DRecHits.clone(dtDigiLabel=cms.InputTag("simMuonDTDigis"))
process.dt1DRecHits.recAlgoConfig.tTrigMode = cms.string("DTTTrigSyncTOFCorr")
process.dt1DRecHits.recAlgoConfig.tTrigModeConfig.tTrig = cms.double(500.0)

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
    maxMedianPtResolution=cms.double(0.5),
    minEfficiency=cms.double(0.5),
    # At 20% momentum resolution the curvature sign is genuinely uncertain
    # for the stiffest muons, so a wrong charge now and then is physics
    minChargeAgreement=cms.double(0.8),
)

process.p = cms.Path(
    process.offlineBeamSpot
    * process.dt1DRecHits
    * process.dt4DSegments
    * process.ancientMuonSeed
    * process.standAloneMuons
    * process.muons
)
