# The tracking validation: the standard one, the way every CMSSW release is
# checked before it is used.
#
# python/muon_gun_tracks_cfg.py measures the tracks with an analyzer written
# for this example. A release is not validated that way. It is validated by
# the same few standard suites run on standard samples, writing histograms
# into the DQM store, then a harvesting step that turns per-event counts into
# efficiencies and rates, and then a comparison of the resulting plots against
# the previous release's. This job runs the first two of those steps for the
# tracking, on the muon gun:
#
#   tpClusterProducer           which TrackingParticle left each cluster
#                               (TrackingParticles: the simulated charged
#                               particles with their hits, which the digi job
#                               had the mixing module assemble)
#   quickTrackAssociatorByHits  a track and a TrackingParticle match when
#                               enough of the track's hits are the particle's
#   MultiTrackValidator         fills the histograms: simulated particles,
#                               reconstructed tracks, and which of each found
#                               the other, against eta, pt, hits, layers, ...
#   DQMGenericClient            the harvesting: divides them into efficiency,
#                               fake and duplicate rate plots
#   DQMFileSaver                writes the DQM file a release comparison reads
#
# plugins/TrackValidationCheck.cc then reads the harvested plots back and puts
# bounds on them, since there is no previous release to compare against.
#
# 20_1 only: the 10_6 configuration does not build the validation.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_detinfo_fixups, add_tracking_reco

process = cms.Process("VALIDATION")

add_tracking_reco(process, False)
add_detinfo_fixups(process, False)

# --- matching tracks to the simulated particles -------------------------------
process.load("SimTracker.TrackerHitAssociation.tpClusterProducer_cfi")
process.load("SimTracker.TrackAssociatorProducers.quickTrackAssociatorByHits_cfi")
process.load("SimTracker.TrackAssociation.trackingParticleRecoTrackAsssociation_cfi")
# how many tracker layers each simulated particle crossed, for the
# efficiency-vs-layers plots
process.load("SimGeneral.TrackingAnalysis.trackingParticleNumberOfLayersProducer_cff")

# --- the validation -----------------------------------------------------------
process.load("DQMServices.Core.DQMStore_cfi")
from Validation.RecoTrack.MultiTrackValidator_cfi import multiTrackValidator

process.trackValidator = multiTrackValidator.clone(
    # the jet cores give the fake rate near high-pt jets; there are no jets
    cores="",
)

# --- the harvesting -------------------------------------------------------------
# The post-processor and the check are DQMEDHarvesters: they run at the end
# of the run, on what the validator filled. In production the harvesting
# is a job of its own, reading the DQM files of all the jobs of a sample; in
# a single job it can follow directly.
from DQMServices.Core.DQMEDHarvester import DQMEDHarvester
from Validation.RecoTrack.PostProcessorTracker_cfi import postProcessorTrack

process.postProcessorTrack = postProcessorTrack.clone(
    # only the folder trackValidator fills; the default list names the
    # standard sequence's other validators too, and complains about each
    subDirs=["Tracking/Track/*"],
)

process.checkValidation = DQMEDHarvester(
    "TrackValidationCheck",
    # after the post-processor: harvesters run in the order of the
    # histograms they read, and this one reads what postProcessorTrack made
    inputMEs=cms.untracked.VInputTag(cms.InputTag("postProcessorTrack", "DQMGenerationHarvestingRun")),
    # MultiTrackValidator's folder: its dirName, the track collection (with
    # "Tracks" dropped) and the association
    folder=cms.string("Tracking/Track/general_trackingParticleRecoAsssociation"),
    # Measured: 19/20. Four muons per event at pt 10-50 in the barrel are the
    # easiest tracks CMS ever reconstructs; with twenty of them, the bound
    # allows two to be lost, and more than that is a broken reconstruction
    # or a broken association.
    minEfficiency=cms.double(0.9),
    # Measured: 0 of 19 tracks. A fake is a track no simulated particle
    # accounts for.
    maxFakeRate=cms.double(0.1),
    # Measured: 0. A duplicate is a second track for the same particle.
    maxDuplicateRate=cms.double(0.1),
    # The pull - (measured - true)/(estimated error) - of q/p has an RMS of 1
    # when the fit's errors are the right size. Measured: 0.88. From twenty
    # tracks, the bounds can only catch errors that are wrong by a large
    # factor, which is what a broken material description or field would do.
    minPullWidth=cms.double(0.5),
    maxPullWidth=cms.double(2.0),
)

process.dqmSaver = cms.EDAnalyzer(
    "DQMFileSaver",
    convention=cms.untracked.string("Offline"),
    fileFormat=cms.untracked.string("ROOT"),
    producer=cms.untracked.string("DQM"),
    # the file is DQM_V0001_R000000001__MuonGun__Validation__RECO.root
    workflow=cms.untracked.string("/MuonGun/Validation/RECO"),
    dirName=cms.untracked.string("."),
    filterName=cms.untracked.string(""),
    version=cms.untracked.int32(1),
    runIsComplete=cms.untracked.bool(False),
    saveByLumiSection=cms.untracked.int32(-1),
    saveByRun=cms.untracked.int32(-1),
    saveAtJobEnd=cms.untracked.bool(True),
    forceRunNumber=cms.untracked.int32(-1),
    referenceHandling=cms.untracked.string("all"),
    referenceRequireStatus=cms.untracked.int32(100),
)

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
    * process.tpClusterProducer
    * process.quickTrackAssociatorByHits
    * process.trackingParticleRecoTrackAsssociation
    * process.trackingParticleNumberOfLayersProducer
    * process.trackValidator
)
process.harvesting = cms.EndPath(process.postProcessorTrack * process.checkValidation * process.dqmSaver)
