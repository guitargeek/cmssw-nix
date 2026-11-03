# Tracking: rec hits -> pixel triplet seeds -> CKF pattern recognition ->
# Kalman-fitted tracks, and then the measurement that closes the chain -
# how well does the fitted momentum agree with the muon the gun fired?
#
# Everything before this validates positions. A residual of 9 um says the hit
# is in the right place; it says nothing about whether the reconstruction can
# assemble hits across nine layers into a trajectory, or whether the magnetic
# field that bent the muon during simulation is the one the fit uses to
# measure its momentum. The gun fires at a known pt, so the fitted pt is a
# number with a right answer, and it is the only number here that tests the
# field quantitatively.
#
# The chain is the standard one, and identical to examples/TrackingChain
# except that its rec hits come from a real simulation rather than from a
# hand-written ToyTrackerDigiProducer: pixel triplets seed proto-tracks, those
# become trajectory seeds, the CKF extends them through the strip detector,
# and ctfWithMaterialTracks does the final Kalman fit with material effects.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

# the shared reconstruction stages live beside this file; cmsRun does not
# put the config's directory on sys.path
sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_detinfo_fixups, add_tracking_reco

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("TRACKS")

add_tracking_reco(process, _is_10_6)

# --- the measurement --------------------------------------------------------
process.tracks = cms.EDAnalyzer(
    "TrackResolution",
    tracks=cms.InputTag("generalTracks"),
    # the SimTracks carry what Geant4 was handed; genpartIndex() >= 0 picks the
    # generator muons out from the secondaries the shower produced
    simTracks=cms.InputTag("g4SimHits"),
    minPt=cms.double(1.0),
    # the gun's four muons per event are spread in phi and eta, so a
    # generous cone still cannot match the wrong one
    maxDeltaR=cms.double(0.1),
    # Measured: 0.69%, which is what CMS achieves for muons of this
    # momentum. The bound is 2%: loose enough for ten muons of
    # statistics, tight enough that a magnetic field disagreeing with the
    # one used in simulation cannot pass - which is the whole reason to
    # measure momentum rather than position.
    maxMedianPtResolution=cms.double(0.02),
    minEfficiency=cms.double(0.8),
    # 0.8% momentum resolution leaves no ambiguity in the sign of the
    # curvature, so every charge must be right
    minChargeAgreement=cms.double(1.0),
    # A tracker fit that describes its own hits. Measured: 1.0.
    maxMedianChi2=cms.double(2.0),
)

process.vertex = cms.EDAnalyzer(
    "VertexResolution",
    vertices=cms.InputTag("offlinePrimaryVertices"),
    # the gun's production vertex: the SimVertex with no parent track
    simVertices=cms.InputTag("g4SimHits"),
    # Measured: 8.8 um transverse, 11.5 um along the beam, from four tracks.
    # The bounds keep an order of magnitude of headroom, which five events
    # of statistics warrants, and still catch a vertex that has run away
    # from the production point.
    maxMedianTransverse=cms.double(0.01),
    maxMedianLongitudinal=cms.double(0.02),
    minEfficiency=cms.double(0.8),
)

add_detinfo_fixups(process, _is_10_6)

process.p = cms.Path(
    process.siStripClusters
    * process.siPixelClusters
    * process.siStripMatchedRecHits
    * process.siPixelRecHits
    * process.offlineBeamSpot
    * process.MeasurementTrackerEvent
    * process.PixelLayerTriplets
    * process.pixelTracksTrackingRegions
    * process.trackerClusterCheck
    * process.pixelTracksHitDoublets
    * process.pixelTracksHitTriplets
    * process.pixelFitterByHelixProjections
    * process.pixelTrackFilterByKinematics
    * process.pixelTracks
    * process.pixelTrackSeeds
    * process.ckfTrackCandidates
    * process.generalTracks
    * process.offlinePrimaryVertices
    * process.tracks
    * process.vertex
)
