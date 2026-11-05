# The fast simulation: the same muon gun, without Geant4.
#
# The full chain of this example - Geant4 in MuonGunSim, then digitisation,
# clustering and tracking here - costs seconds per event. CMS simulates the
# billions of events of its signal scans with FastSim instead, which replaces
# each step by a parametrisation tuned on the full one:
#
#   FastSimProducer          propagates the particles through a simplified
#                            tracker - cylinders and disks of material in
#                            the real field - with parametrised multiple
#                            scattering, energy loss and bremsstrahlung, and
#                            records a SimHit where a particle crosses a layer
#   TrackingRecHitProducer   turns the SimHits straight into rec hits,
#                            smeared with the resolution histograms of the
#                            pixel templates and per-layer strip resolutions:
#                            no digis, no clusters
#   TrajectorySeedProducer,  the tracking: seeds from hit triplets in the
#   TrackCandidateProducer   pixel layers, as in the full reconstruction, but
#                            the pattern recognition is skipped - a candidate
#                            is all the hits of the particle that made the
#                            seed, which the simulation knows
#   TrackProducer            the same Kalman fit as the full reconstruction
#
# plugins/TrackResolution.cc measures the tracks as in muon_gun_tracks_cfg.py,
# so the two simulations can be compared on the same numbers.
#
# Only the tracker is simulated: the calorimetry and the muon system would
# need conditions and data files this build does not have (the calorimeter
# showers' energy response, the nuclear interaction library). The standard
# configuration is the fastSim era, which retunes the whole reconstruction;
# this job declares the few modules it runs instead.
#
# 20_1 only: the 10_6 configuration does not build the fast simulation.
#
# Reads the pixel templates from sim_conditions.db, so run
# python/write_sim_conditions_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_detinfo_fixups, add_tracking_reco

# phase1Pixel: the 2018 pixel detector has four barrel layers and three
# disks, and the fast simulation's material description gains the fourth
# and third only under this modifier (the reconstruction's configuration
# already describes the phase-1 detector without it)
from Configuration.Eras.Modifier_phase1Pixel_cff import phase1Pixel

process = cms.Process("FASTSIM", phase1Pixel)

# The geometry, field, conditions, beam spot and fit of the full
# reconstruction, which the fast one shares.
add_tracking_reco(process, False)
add_detinfo_fixups(process, False)

# Events from the gun rather than from the digi file. Ten times as many as
# the full simulation's five: after the first, they take under a
# millisecond each.
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(50))

process.RandomNumberGeneratorService = cms.Service(
    "RandomNumberGeneratorService",
    **{label: cms.PSet(initialSeed=cms.untracked.uint32(seed), engineName=cms.untracked.string("HepJamesRandom"))
       for label, seed in (("generator", 123456789), ("generatorSmeared", 98765432),
                           ("fastSimProducer", 11), ("fastTrackerRecHits", 12))}
)

# --- the gun: as in muon_gun_digi_cfg.py ---------------------------------------
process.load("SimGeneral.HepPDTESSource.pythiapdt_cfi")
process.generator = cms.EDProducer(
    "FlatRandomPtGunProducer",
    PGunParameters=cms.PSet(
        PartID=cms.vint32(13, -13, 13, -13),
        MinPt=cms.double(10.0),
        MaxPt=cms.double(50.0),
        MinEta=cms.double(-0.8),
        MaxEta=cms.double(0.8),
        MinPhi=cms.double(-3.14159265359),
        MaxPhi=cms.double(3.14159265359),
    ),
    AddAntiParticle=cms.bool(False),
    Verbosity=cms.untracked.int32(0),
    firstRun=cms.untracked.uint32(1),
    psethack=cms.string("single mu pt 10-50"),
)
process.load("IOMC.EventVertexGenerators.VtxSmearedRealistic25ns13TeVEarly2018Collision_cfi")
process.generatorSmeared = process.VtxSmeared.clone()
del process.VtxSmeared

# --- the simulation -------------------------------------------------------------
# FastSim simulates in a tracker geometry of its own, labelled "MisAligned":
# production configurations can misalign it to simulate a detector that is
# not where the reconstruction thinks it is. Here it is the ideal one again.
process.misalignedTrackerGeometry = process.TrackerDigiGeometryESModule.clone(appendToDataLabel="MisAligned")
process.load("FastSimulation.Configuration.TrackerRecoGeometryESProducer_cfi")

# loaded rather than cloned: its calorimetry parameters refer to PSets the
# cff defines beside it, even with the calorimetry off
process.load("FastSimulation.SimplifiedGeometryPropagator.fastSimProducer_cff")
process.fastSimProducer.simulateCalorimetry = False
process.fastSimProducer.simulateMuons = False
# The same file the full simulation lacks (see MuonGunSim): the HF shower
# library, named in a block the calorimetry configuration refers to and
# resolved when the configuration is read, whether or not anything opens it.
# Pointed at a file that ships, as there.
process.HFLibraryFileBlock.FileName = cms.FileInPath("SimG4CMS/Calo/data/responsTBpim50.dat")
# The nuclear interactions are drawn from a library of Geant4 events which
# the release does not ship (its download.url points behind the CERN single
# sign-on). Muons do not interact strongly, so the model has nothing to do.
del process.fastSimProducer.interactionModels.nuclearInteraction
for _layer in (process.fastSimProducer.trackerDefinition.BarrelLayers
               + process.fastSimProducer.trackerDefinition.EndcapLayers):
    _layer.interactionModels = [m for m in _layer.interactionModels if m != "nuclearInteraction"]

# --- rec hits from the SimHits ------------------------------------------------
# The pixel hits are smeared with the templates' resolution histograms (the
# phase-1 ones, by the modifier), the strip hits with per-layer Gaussians.
process.load("FastSimulation.TrackingRecHitProducer.TrackingRecHitProducer_cfi")
# The pixel smearing reads its templates from SiPixelTemplateDBObjectRcd,
# which the conditions job wrote, through the producer that picks the payload
# for the field (the one that unpacks it, the full reconstruction's
# configuration loads already).
process.pixelConditions.toGet.append(
    cms.PSet(record=cms.string("SiPixelTemplateDBObjectRcd"), tag=cms.string("SiPixelTemplateDBObject_38T_2021"))
)
process.siPixelTemplateDBObjectESProducer = cms.ESProducer("SiPixelTemplateDBObjectESProducer")

# a stereo and an r-phi hit on the same module pair become one matched hit,
# and the hits of each simulated particle are collected into one combination
from FastSimulation.TrackingRecHitProducer.FastTrackerRecHitMatcher_cfi import fastMatchedTrackerRecHits
from FastSimulation.Tracking.FastTrackerRecHitCombiner_cfi import fastTrackerRecHitCombinations

process.fastMatchedTrackerRecHits = fastMatchedTrackerRecHits.clone()
process.fastMatchedTrackerRecHitCombinations = fastTrackerRecHitCombinations.clone(
    simHit2RecHitMap=cms.InputTag("fastMatchedTrackerRecHits", "simHit2RecHitMap"),
)

# --- the tracking ---------------------------------------------------------------
# What the fastSim era does to the measurement tracker: there are no clusters.
process.MeasurementTrackerEvent.pixelClusterProducer = ""
process.MeasurementTrackerEvent.stripClusterProducer = ""
process.MeasurementTrackerEvent.inactivePixelDetectorLabels = []
process.MeasurementTrackerEvent.inactiveStripDetectorLabels = []
process.MeasurementTrackerEvent.switchOffPixelsIfEmpty = False
# FastSim hits carry their position and error already: no refit
process.load("RecoTracker.TransientTrackingRecHit.TransientTrackingRecHitBuilderWithoutRefit_cfi")

# The seeds: pixel triplets on the full reconstruction's layers, from the
# same triplet generator, applied to each particle's hits. Those layers are
# the phase-0 combinations (muon_gun_stages.py), without the fourth barrel
# layer: a muon that misses one of the first three barrel layers through a
# gap gets no seed. Kept, so that the two simulations are compared through
# the same reconstruction.
from FastSimulation.Tracking.SeedingMigration import _hitSetProducerToFactoryPSet
from FastSimulation.Tracking.TrajectorySeedProducer_cfi import trajectorySeedProducer

process.fastSeeds = trajectorySeedProducer.clone(
    trackingRegions="pixelTracksTrackingRegions",
    # in the full field, as everywhere else in this job: the default is the
    # parabolic approximation of it, which is not configured here
    SeedCreatorPSet=dict(propagator="PropagatorWithMaterial", magneticField=""),
    seedFinderSelector=dict(
        layerList=process.PixelLayerTriplets.layerList.value(),
        pixelTripletGeneratorFactory=_hitSetProducerToFactoryPSet(process.pixelTracksHitTriplets),
    ),
)

from FastSimulation.Tracking.TrackCandidateProducer_cfi import trackCandidateProducer

process.fastTrackCandidates = trackCandidateProducer.clone(
    src="fastSeeds",
    MinNumberOfCrossedLayers=3,
)
process.fastTracks = process.generalTracks.clone(
    src="fastTrackCandidates",
    TTRHBuilder="WithoutRefit",
)

# --- the measurement ------------------------------------------------------------
# The same bounds as muon_gun_tracks_cfg.py. On 20_1 the full simulation
# gives 19/20 muons, 0.44% momentum resolution, chi2/ndof 0.98, 14 tracker
# and 4 pixel layers per track. Measured here: 180/200, 0.65%, every charge
# right, chi2/ndof 0.98, 14 and 4 layers. Eighteen of the twenty missed are
# the seeding layers' (with the fourth barrel layer's triplets added, 198
# are found); the resolution agrees within what twenty full-simulation
# muons can tell.
process.tracks = cms.EDAnalyzer(
    "TrackResolution",
    tracks=cms.InputTag("fastTracks"),
    # the SimTracks of the generator's muons: FastSim's own, which carry the
    # generator index the same way Geant4's do (see gen/prepare_sources.py)
    simTracks=cms.InputTag("fastSimProducer"),
    minPt=cms.double(1.0),
    maxDeltaR=cms.double(0.1),
    maxMedianPtResolution=cms.double(0.02),
    minEfficiency=cms.double(0.8),
    minChargeAgreement=cms.double(1.0),
    maxMedianChi2=cms.double(2.0),
)

process.p = cms.Path(
    process.generator
    * process.generatorSmeared
    * process.fastSimProducer
    * process.offlineBeamSpot
    * process.fastTrackerRecHits
    * process.fastMatchedTrackerRecHits
    * process.fastMatchedTrackerRecHitCombinations
    * process.MeasurementTrackerEvent
    * process.pixelTracksTrackingRegions
    * process.fastSeeds
    * process.fastTrackCandidates
    * process.fastTracks
    * process.tracks
)
