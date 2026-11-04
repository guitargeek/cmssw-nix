# The tracker DQM: the histograms the detector groups watch during data taking.
#
# python/muon_gun_validation_cfg.py measures the tracking against the
# simulation's truth. Data has no truth, so the detector groups watch
# something else: the distributions of what the reconstruction produced -
# digis and clusters per module, cluster charge and size, tracks per event,
# hits per track, chi2 - and compare them with what they looked like in a
# good run. The modules that fill those histograms are the DQM/ packages;
# the same ones run online on a slice of the data and offline on all of it.
# This job runs the tracker's on the muon gun:
#
#   SiPixelPhase1Digis      pixel digis per module, their ADC, the occupancy
#   SiPixelPhase1Clusters   pixel clusters: charge, size, position
#   SiStripMonitorCluster   strip clusters: charge, width, signal-to-noise
#   TrackingMonitor         tracks per event and their parameters, hits and
#                           layers per track, against the beam spot
#   DQMFileSaver            writes the DQM file a shifter would look at
#
# plugins/DQMHistogramCheck.cc then reads a few of the histograms back and
# puts bounds on them, since there is no good run to compare against.
#
# 20_1 only: the 10_6 configuration does not build the DQM modules.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_detinfo_fixups, add_tracking_reco

process = cms.Process("DQM")

add_tracking_reco(process, False)
add_detinfo_fixups(process, False)

process.load("DQMServices.Core.DQMStore_cfi")
# the module layout of the tracker maps the strip monitor fills
process.load("CalibTracker.SiStripCommon.TkDetMapESProducer_cfi")

# --- pixels -----------------------------------------------------------------
from DQM.SiPixelPhase1Common.HistogramManager_cfi import PerModule
from DQM.SiPixelPhase1Common.SiPixelPhase1Digis_cfi import SiPixelPhase1DigisAnalyzer
from DQM.SiPixelPhase1Common.SiPixelPhase1Clusters_cfi import SiPixelPhase1ClustersAnalyzer

# Per-module histograms are for the online shifter, who drills down to one
# module of the 1856; offline (and here) the per-layer and per-disk ones
# are enough. This is the switch the offline configuration flips: the
# specifications all hold a reference to it.
PerModule.enabled = False

# The pixel monitors fill only on events of the trigger paths named in the
# conditions database (zero bias, in collisions). A simulation has no
# trigger and no such record, so they see every event.
process.pixelDigiMon = SiPixelPhase1DigisAnalyzer.clone(src="simSiPixelDigis", triggerflags=[])
process.pixelClusterMon = SiPixelPhase1ClustersAnalyzer.clone(triggerflags=[])

# --- strips -----------------------------------------------------------------
from DQM.SiStripMonitorCluster.SiStripMonitorCluster_cfi import SiStripMonitorCluster

# Likewise the strip monitor fills only while the pixel and strip
# partitions are powered, as the DCS status in the raw data says; a
# simulation has none, and the detector is always on.
process.stripClusterMon = SiStripMonitorCluster.clone(
    PixelDCSfilter=cms.PSet(),
    StripDCSfilter=cms.PSet(),
    # as offline: no histograms per module (there are 15148) - they are
    # 46 MB of DQM file for five events
    Mod_On=False,
    # and instead the cluster charge and width per subdetector
    TH1ClusterCharge=SiStripMonitorCluster.TH1ClusterCharge.clone(subdetswitchon=True),
    TH1ClusterWidth=SiStripMonitorCluster.TH1ClusterWidth.clone(subdetswitchon=True),
)

# --- tracks -----------------------------------------------------------------
from DQM.TrackingMonitor.TrackingMonitor_cfi import TrackMon

process.trackMon = TrackMon.clone(
    TrackProducer="generalTracks",
    allTrackProducer="generalTracks",
    SeedProducer="pixelTrackSeeds",
    TCProducer="ckfTrackCandidates",
)

# --- the check and the DQM file ----------------------------------------------
from DQMServices.Core.DQMEDHarvester import DQMEDHarvester

def bound(path, minEntries, minMean, maxMean):
    return cms.PSet(path=cms.string(path), minEntries=cms.double(minEntries),
                    minMean=cms.double(minMean), maxMean=cms.double(maxMean))


_pixels = "PixelPhase1/Phase1_MechanicalView/"
_strips = "SiStrip/MechanicalView/"
_tracks = "Tracking/GlobalParameters/"
# Measured values in the comments, from five events of four muons each, at
# pt 10-50 GeV and |eta| < 0.8 (so: barrel only, nothing in the forward
# pixels or the strip endcaps worth a bound). The windows are wide - five
# events are not a reference run - and what they catch is a monitor that
# sees nothing, or a detector response off by a large factor.
process.checkDQM = DQMEDHarvester(
    "DQMHistogramCheck",
    histograms=cms.VPSet(
        # 17 pixel clusters per event: four muons through four barrel layers,
        # and a few delta rays
        bound(_pixels + "num_clusters_PXBarrel", 5, 10, 30),
        # 26500 electrons: a minimum-ionising particle leaves ~22000 in the
        # 285 um of silicon at normal incidence, more when it crosses at an
        # angle - the Landau tail pulls the mean above that
        bound(_pixels + "charge_PXBarrel", 50, 18000, 35000),
        # 2.1 pixels: the charge shares between neighbours by the Lorentz drift
        bound(_pixels + "size_PXBarrel", 50, 1.5, 4),
        # 131 ADC counts in the inner barrel (320 um sensors), 197 in the
        # outer one (500 um): the ratio, 1.51, is that of the thicknesses
        bound(_strips + "TIB/ClusterCharge__TIB", 50, 100, 170),
        bound(_strips + "TOB/ClusterCharge__TOB", 50, 150, 250),
        # 3.8 tracks per event for four muons: one of the twenty was lost,
        # as in the validation job
        bound(_tracks + "GeneralProperties/NumberOfTracks_GenTk", 5, 3, 4.5),
        # 33.5 GeV: the gun's flat 10-50 GeV
        bound(_tracks + "GeneralProperties/TrackPt_ImpactPoint_GenTk", 15, 20, 45),
        # 19.2 hits per track, on 13.9 layers: through the barrel
        bound(_tracks + "GeneralProperties/NumberOfMeanRecHitsPerTrack_GenTk", 5, 12, 30),
        # 1.10: a fit that describes its hits
        bound(_tracks + "GeneralProperties/Chi2oNDF_GenTk", 15, 0.5, 2),
    ),
)

process.dqmSaver = cms.EDAnalyzer(
    "DQMFileSaver",
    convention=cms.untracked.string("Offline"),
    fileFormat=cms.untracked.string("ROOT"),
    producer=cms.untracked.string("DQM"),
    # the file is DQM_V0001_R000000001__MuonGun__DQM__RECO.root
    workflow=cms.untracked.string("/MuonGun/DQM/RECO"),
    dirName=cms.untracked.string("."),
    filterName=cms.untracked.string(""),
    version=cms.untracked.int32(1),
    runIsComplete=cms.untracked.bool(False),
    saveByLumiSection=cms.untracked.int32(-1),
    # at the end of the run: the DQM store releases a run's histograms when
    # the run ends, and only what a harvester booked lives on to the end of
    # the job (which is when the validation job saves)
    saveByRun=cms.untracked.int32(1),
    saveAtJobEnd=cms.untracked.bool(False),
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
    * process.offlinePrimaryVertices
    * process.pixelDigiMon
    * process.pixelClusterMon
    * process.stripClusterMon
    * process.trackMon
)
process.harvesting = cms.EndPath(process.checkDQM * process.dqmSaver)
