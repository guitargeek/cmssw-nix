# Standalone muon reconstruction on toy DT digis: digis -> rec hits -> 4D
# segments -> muon seed -> standalone muon track, in the *real* magnetic
# field.
#
# This is the step the uniform 3.8 T field cannot do. A standalone muon is
# fitted entirely in the muon system, where the flux has returned through the
# iron and points the other way; with a uniform field the trajectory
# propagation is wrong from the first station on and no track comes out. The
# volume-based engine (see examples/MagneticFieldMap) gives the right field
# there.
import FWCore.ParameterSet.Config as cms

process = cms.Process("MUONSTA")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

# --- detector geometry: the 2016 XML filtered to the world volumes and the
# muon system, exactly as in examples/MuonLocalReco
from Geometry.CMSCommonData.cmsExtendedGeometry2016XML_cfi import (
    XMLIdealGeometryESSource as _xmlsrc,
)
process.XMLIdealGeometryESSource = _xmlsrc.clone()
process.XMLIdealGeometryESSource.geomXMLFiles = cms.vstring(
    [
        f
        for f in _xmlsrc.geomXMLFiles
        if f.startswith(
            (
                "Geometry/CMSCommonData/",
                "Geometry/MuonCommonData/",
                "Geometry/MuonSimData/",
                "Geometry/DTGeometryBuilder/",
                "Geometry/CSCGeometryBuilder/",
                "Geometry/RPCGeometryBuilder/",
                # the tracker content is needed for the tracker *numbering*
                # only: the standalone track loader fills the hit pattern of
                # the reco::Track through TrackerTopology, which is built
                # from the tracker spec-pars
                "Geometry/TrackerCommonData/",
            )
        )
    ]
)
process.TrackerParametersESModule = cms.ESProducer("TrackerParametersESModule")
process.trackerTopology = cms.ESProducer("TrackerTopologyEP")
# ... and the muon navigation is defined over tracker *and* muon layers, so
# the tracker reco geometry has to be there as well (it stays empty of hits)
process.TrackerGeometricDetESModule = cms.ESProducer(
    "TrackerGeometricDetESModule", fromDDD=cms.bool(True)
)
process.TrackerDigiGeometryESModule = cms.ESProducer(
    "TrackerDigiGeometryESModule",
    fromDDD=cms.bool(True),
    applyAlignment=cms.bool(False),
    alignmentsLabel=cms.string(""),
    appendToDataLabel=cms.string(""),
)
process.load("RecoTracker.GeometryESProducer.TrackerRecoGeometryESProducer_cfi")
# the DetLayerGeometry the KF fitters navigate on spans tracker *and* muon
process.load("TrackingTools.RecoGeometry.GlobalDetLayerGeometryESProducer_cfi")

process.load("Geometry.MuonNumbering.muonNumberingInitialization_cfi")
process.load("Geometry.DTGeometryBuilder.dtGeometry_cfi")
process.DTGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.CSCGeometryBuilder.cscGeometry_cfi")
process.CSCGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.RPCGeometryBuilder.rpcGeometry_cfi")

# the tracking geometry the muon trajectory machinery navigates on. The
# tracker part is absent here and GlobalTrackingGeometry only warns about it.
process.GlobalTrackingGeometryESProducer = cms.ESProducer("GlobalTrackingGeometryESProducer")
process.load("RecoMuon.DetLayers.muonDetLayerGeometry_cfi")
process.load("RecoMuon.TransientTrackingRecHit.MuonTransientTrackingRecHitBuilder_cfi")

# --- the real magnetic field (field volumes from their own XML source, field
# values interpolated from the 3.8 T grid tables)
process.load("MagneticField.Engine.volumeBasedMagneticField_160812_cfi")

# --- beam spot at the origin: the standalone track loader refers the track
# to it (fixed fake conditions + the standard producer, as in
# examples/TrackingChain)
process.BeamSpotFakeConditions = cms.ESSource(
    "BeamSpotFakeConditions",
    getDataFromFile=cms.bool(False),
    X0=cms.double(0.0), Y0=cms.double(0.0), Z0=cms.double(0.0),
    dxdz=cms.double(0.0), dydz=cms.double(0.0),
    sigmaZ=cms.double(3.8), widthX=cms.double(0.0015), widthY=cms.double(0.0015),
    emittanceX=cms.double(0.0), emittanceY=cms.double(0.0),
    betaStar=cms.double(0.0),
    errorX0=cms.double(0.0002), errorY0=cms.double(0.0002), errorZ0=cms.double(0.02),
    errorSigmaZ=cms.double(0.01), errordxdz=cms.double(0.0001),
    errordydz=cms.double(0.0001), errorWidth=cms.double(0.0002),
)
process.offlineBeamSpot = cms.EDProducer("BeamSpotProducer")

# --- toy digis along a straight muon through the four barrel stations
process.toyDigis = cms.EDProducer(
    "ToyMuonTrackDigiProducer",
    wheel=cms.int32(0),
    sector=cms.int32(1),
    tTrig=cms.double(500.0),
    pt=cms.double(50.0),
    charge=cms.int32(1),
)

# --- DT local reco (as in examples/MuonLocalReco)
from RecoLocalMuon.DTRecHit.dt1DRecHits_LinearDrift_cfi import dt1DRecHits as _dt1DRecHits
process.dt1DRecHits = _dt1DRecHits.clone(dtDigiLabel=cms.InputTag("toyDigis"))
process.dt1DRecHits.recAlgoConfig.tTrigMode = cms.string("DTTTrigSyncTOFCorr")
process.dt1DRecHits.recAlgoConfig.tTrigModeConfig.tTrig = cms.double(500.0)

from RecoLocalMuon.DTSegment.dt4DSegments_CombPatternReco4D_LinearDrift_cfi import (
    dt4DSegments as _dt4DSegments,
)
process.dt4DSegments = _dt4DSegments.clone(recHits1DLabel=cms.InputTag("dt1DRecHits"))
process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.recAlgoConfig.tTrigMode = \
    cms.string("DTTTrigSyncTOFCorr")
process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.recAlgoConfig.tTrigModeConfig.tTrig = \
    cms.double(500.0)
process.dt4DSegments.Reco4DAlgoConfig.recAlgoConfig.tTrigMode = \
    cms.string("DTTTrigSyncTOFCorr")
process.dt4DSegments.Reco4DAlgoConfig.recAlgoConfig.tTrigModeConfig.tTrig = cms.double(500.0)
process.dt4DSegments.Reco4DAlgoConfig.perform_delta_rejecting = cms.bool(False)
process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.perform_delta_rejecting = cms.bool(False)

# --- muon seeds from the DT segments alone (no CSC/RPC hits in this event)
from RecoMuon.MuonSeedGenerator.ancientMuonSeed_cfi import ancientMuonSeed as _ancientMuonSeed
process.ancientMuonSeed = _ancientMuonSeed.clone(
    EnableCSCMeasurement=cms.bool(False),
    EnableRPCMeasurement=cms.bool(False),
)

# --- standalone muon fit
process.load("RecoMuon.StandAloneMuonProducer.standAloneMuons_cff")
for _pset in (process.standAloneMuons.STATrajBuilderParameters.FilterParameters,
              process.standAloneMuons.STATrajBuilderParameters.BWFilterParameters):
    _pset.EnableCSCMeasurement = cms.bool(False)
    _pset.EnableRPCMeasurement = cms.bool(False)

# --- check the outcome
process.checker = cms.EDAnalyzer(
    "StandAloneMuonChecker",
    seeds=cms.InputTag("ancientMuonSeed"),
    tracks=cms.InputTag("standAloneMuons"),
    minTracks=cms.uint32(1),
    # the injected 50 GeV comes back as ~55: the fit corrects for the energy
    # the muon loses in the yoke iron, which the toy does not simulate
    minPt=cms.double(40.0),
    maxPt=cms.double(70.0),
    charge=cms.int32(1),
)

process.p = cms.Path(
    process.offlineBeamSpot
    * process.toyDigis
    * process.dt1DRecHits
    * process.dt4DSegments
    * process.ancientMuonSeed
    * process.standAloneMuons
    * process.checker
)
