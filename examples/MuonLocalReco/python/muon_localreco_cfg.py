# Muon local reco validation: toy DT/CSC/RPC digis -> rec hits -> segments,
# with the muon geometries built from the DDD XML detector description and
# fake/parameter-based conditions everywhere.
#
# Runs on both releases; the one difference is the muon numbering, below.
import os

import FWCore.ParameterSet.Config as cms

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("MUONRECO")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

# --- geometry: the 2016 detector XML filtered to the world volumes and the
# muon system (the muon content resolves the muonBase/cmsMuon envelopes)
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
                # the reco spec-pars the DT/CSC/RPC geometry builders
                # filter on (MuStructure etc.)
                "Geometry/DTGeometryBuilder/",
                "Geometry/CSCGeometryBuilder/",
                "Geometry/RPCGeometryBuilder/",
            )
        )
        # the tracker envelope stays out (no tracker content loaded)
        and not f.endswith("cmsTracker.xml")
    ]
)

# muon numbering constants + the DT/CSC/RPC geometry builders
process.load("Geometry.MuonNumbering.muonNumberingInitialization_cfi")
# 20_1 splits the numbering in two: MuonNumberingInitialization still fills
# MuonNumberingRecord, but the geometry builders additionally want
# MuonGeometryConstants in the IdealGeometryRecord, which is a separate ES
# module that did not exist in the 10_6 era.
if not _is_10_6:
    process.load("Geometry.MuonNumbering.muonGeometryConstants_cff")
process.load("Geometry.DTGeometryBuilder.dtGeometry_cfi")
process.DTGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.CSCGeometryBuilder.cscGeometry_cfi")
process.CSCGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.RPCGeometryBuilder.rpcGeometry_cfi")

# --- conditions: fake CSC DB constants; DT and RPC run without any DB
process.load("CalibMuon.CSCCalibration.CSCFakeDBGains_cfi")
process.load("CalibMuon.CSCCalibration.CSCFakeDBPedestals_cfi")
process.load("CalibMuon.CSCCalibration.CSCFakeDBNoiseMatrix_cfi")
process.load("CalibMuon.CSCCalibration.CSCFakeDBCrosstalk_cfi")
process.load("CalibMuon.CSCCalibration.CSCChannelMapper_cfi")
process.load("CalibMuon.CSCCalibration.CSCIndexer_cfi")

# --- the toy digis
process.toyDigis = cms.EDProducer("ToyMuonDigiProducer")

# --- DT: rec hits with the constant-drift-velocity algorithm and the
# parameter-based TOF synchronization (no conditions DB involved), then the
# standard combinatorial 4D segment building
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
# present in the maintained FromDB cfi variants but missing in the
# LinearDrift ones
process.dt4DSegments.Reco4DAlgoConfig.perform_delta_rejecting = cms.bool(False)
process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.perform_delta_rejecting = cms.bool(False)

# --- CSC: rec hits + segments
from RecoLocalMuon.CSCRecHitD.cscRecHitD_cfi import csc2DRecHits as _csc2DRecHits
from RecoLocalMuon.CSCSegment.cscSegments_cfi import cscSegments as _cscSegments
from RecoLocalMuon.RPCRecHit.rpcRecHits_cfi import rpcRecHits as _rpcRecHits

process.csc2DRecHits = _csc2DRecHits.clone(
    stripDigiTag=cms.InputTag("toyDigis", "MuonCSCStripDigi"),
    wireDigiTag=cms.InputTag("toyDigis", "MuonCSCWireDigi"),
    # the bad-channel/chamber lists and the timing/gas-gain corrections only
    # exist as conditions-DB payloads
    readBadChannels=cms.bool(False),
    readBadChambers=cms.bool(False),
    CSCUseTimingCorrections=cms.bool(False),
    CSCUseGasGainCorrections=cms.bool(False),
)
process.cscSegments = _cscSegments.clone(inputObjects=cms.InputTag("csc2DRecHits"))

# --- RPC: rec hits (mask/dead lists from the packaged data files)
process.rpcRecHits = _rpcRecHits.clone(rpcDigiLabel=cms.InputTag("toyDigis"))

# --- check the outcome
process.checker = cms.EDAnalyzer(
    "MuonLocalRecoChecker",
    dtRecHits=cms.InputTag("dt1DRecHits"),
    dtSegments=cms.InputTag("dt4DSegments"),
    cscRecHits=cms.InputTag("csc2DRecHits"),
    cscSegments=cms.InputTag("cscSegments"),
    rpcRecHits=cms.InputTag("rpcRecHits"),
)

process.p = cms.Path(
    process.toyDigis
    * process.dt1DRecHits
    * process.dt4DSegments
    * process.csc2DRecHits
    * process.cscSegments
    * process.rpcRecHits
    * process.checker
)
