# The last stage: reco::Muons, and NanoAOD.
#
# Everything so far has produced reconstructed *objects* - hits, tracks,
# vertices, standalone muons - and measured them inside the job that made
# them. This stage does the two things that turn that into an analysis:
#
#  1. it combines the two independent measurements of the same muon. The
#     tracker measured it to 0.8% (python/muon_gun_tracks_cfg.py) and the
#     muon system to 23% (python/muon_gun_muons_cfg.py); GlobalMuonProducer
#     matches a standalone track to a tracker track and refits the hits of
#     both as one trajectory, and MuonIdProducer collects what results into
#     reco::Muon - the object an analysis actually asks for.
#
#  2. it writes NanoAOD. Not a POOL file holding C++ objects that only CMSSW
#     can open, but a flat TTree of plain branches - Muon_pt, Muon_eta,
#     GenPart_pdgId - readable by bare ROOT, uproot or pandas. That is where
#     the chain ends for a physicist, and python/muon_gun_nano_cfg_check.py
#     re-opens the file that way, with no CMSSW involved, and matches the
#     reconstructed muons back to the ones the gun fired.
#
# Which closes the loop this set of examples opened: a muon is generated,
# transported through the detector by Geant4, digitised into detector
# readout, reconstructed from that readout alone, and comes out the far end
# as a number in a flat table that agrees with the one the gun was given.
#
# The job is the tracking job and the muon job in one process, because the
# global fit needs both of their outputs in the same event. Up to the primary
# vertex the configuration is exactly what python/muon_gun_tracks_cfg.py runs:
# both jobs call the same stages from muon_gun_stages.py, where every setting
# carries a comment saying why it is what it is.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

# the shared reconstruction stages live beside this file; cmsRun does not
# put the config's directory on sys.path
sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_stages import add_detinfo_fixups, add_muon_reco, add_tracking_reco

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("NANO")

add_tracking_reco(process, _is_10_6)


# --- the muon system --------------------------------------------------------
# From here is the muon system: the same add_muon_reco stage
# python/muon_gun_muons_cfg.py runs - DT digis -> drift-time rec hits -> 4D
# segments -> seeds -> a standalone track fitted in the return yoke. Its
# geometry and beam spot are already set up above; the two ES modules it needs
# on top belong to the muon side of the reconstruction geometry - the layer
# geometry spanning tracker and chambers, and the rec-hit builder that turns
# muon segments into transient hits a fit can use.
process.load("TrackingTools.RecoGeometry.GlobalDetLayerGeometryESProducer_cfi")
process.load("RecoMuon.TransientTrackingRecHit.MuonTransientTrackingRecHitBuilder_cfi")

# --- DT local reconstruction ------------------------------------------------
# The drift-time synchronisation has to undo exactly what the digitiser
# applied: DTDigiSyncTOFCorr with the same 500 ns offset, and tofCorrType = 1
# to cancel its TOFCorrection = 3. The DTLinearDriftAlgo_cfi default of 0
# leaves every drift time short by the flight time to the superlayer, a bias
# that grows with radius. See python/muon_gun_muons_cfg.py for the
# arithmetic - it costs the standalone fit a factor 60 in chi2, and the
# standalone track is half of what the global fit below is made of.
add_muon_reco(process, _is_10_6)


# --- the global fit ---------------------------------------------------------
# GlobalMuonProducer takes a standalone track, looks for a tracker track that
# is compatible with it once both are propagated to a common surface, and
# refits the hits of the two as a single trajectory. The result is a third
# reco::Track collection - not the tracker's and not the muon system's, but a
# fit to all the hits the muon left anywhere in CMS.
#
# At the momenta this gun fires, the combination is dominated by the tracker:
# a 10-50 GeV muon is measured to 0.8% there and to 23% in the chambers, so
# the global fit should land close to the tracker number. The reason CMS does
# it anyway is the other end of the spectrum - above a few hundred GeV the
# tracker curvature gets small and the muon system's lever arm starts to win.
process.load("RecoMuon.GlobalMuonProducer.globalMuons_cff")
# globalMuons_cff pulls in the standard pixel CPE and transient rec-hit
# builders, which put back every default the tracking configuration above had
# to turn off: the CPE goes back to reading Lorentz-angle widths, alignment
# offsets and templates from payloads that do not exist here, and the rec-hit
# builder goes back to the template CPE. This is the second cff in this file
# to reintroduce them - MeasurementTrackerESProducer_cff does it above, for
# the same reason - and each time they have to be turned off again after the
# load, not before.
process.PixelCPEGenericESProducer.UseErrorsFromTemplates = cms.bool(False)
process.PixelCPEGenericESProducer.TruncatePixelCharge = cms.bool(False)
process.PixelCPEGenericESProducer.IrradiationBiasCorrection = cms.bool(False)
process.PixelCPEGenericESProducer.DoCosmics = cms.bool(False)
process.PixelCPEGenericESProducer.LoadTemplatesFromDB = cms.bool(False)
process.PixelCPEGenericESProducer.useLAWidthFromDB = cms.bool(False)
# useLAAlignmentOffsets does not exist in 20_1 - see the CPE block above.
if _is_10_6:
    process.PixelCPEGenericESProducer.useLAAlignmentOffsets = cms.bool(False)
process.TTRHBuilderAngleAndTemplate.PixelCPE = cms.string("PixelCPEGeneric")

# --- reco::Muon -------------------------------------------------------------
# MuonIdProducer is what an analysis really consumes: it collects the tracker
# track, the standalone track and the global fit of the same muon into one
# reco::Muon carrying all three, so that `muon.isGlobalMuon()` and
# `muon.pt()` mean something.
#
# Most of what it can fill needs subsystems this example does not run. The
# calorimeter energy in a cone (fillEnergy), the calo compatibility used to
# identify calo-only muons, and the isolation deposits all read ECAL/HCAL rec
# hits, which nothing here produces; the shower digis and the segment matching
# behind tracker-muon identification (fillMatching) go through
# TrackDetectorAssociator, which needs a calorimeter geometry whether or not
# the calorimeters are read.
#
# The inner-track collection is left out for the same reason, and it is not
# only about saving work: MuonIdProducer builds a tracker-muon candidate from
# every inner track and calls the track-detector association on it
# unconditionally, before any of the fill flags is consulted. Handing it
# generalTracks would demand the calorimeter geometry through that path even
# with every flag off. The tracker tracks are not lost - a global muon carries
# its inner track through the link that made it.
#
# What is left, global and standalone muons built from the track links, is
# exactly the part of a reco::Muon this chain reconstructed.
from RecoMuon.MuonIdentification.muons1stStep_cfi import muons1stStep as _muons1stStep

process.muons = _muons1stStep.clone(
    inputCollectionLabels=cms.VInputTag(
        cms.InputTag("globalMuons"),
        cms.InputTag("standAloneMuons", "UpdatedAtVtx"),
    ),
    inputCollectionTypes=cms.vstring("links", "outer tracks"),
    # tevMuons (the high-pt refits) are not run, so there is nothing to refit
    # the global track with
    fillGlobalTrackRefits=cms.bool(False),
    fillEnergy=cms.bool(False),
    storeCrossedHcalRecHits=cms.bool(False),
    fillCaloCompatibility=cms.bool(False),
    fillIsolation=cms.bool(False),
    writeIsoDeposits=cms.bool(False),
    fillMatching=cms.bool(False),
    fillShowerDigis=cms.bool(False),
    fillTrackerKink=cms.bool(False),
    # arbitration is between segment matches, which are not filled
    arbitrateTrackerMuons=cms.bool(False),
    runArbitrationCleaner=cms.bool(False),
)

# The calo-compatibility templates are two histogram files that live outside
# the release - RecoMuon/MuonIdentification/data holds a download.url pointing
# at cmsdoc.cern.ch, and this build does not fetch them. MuonIdProducer only
# opens them when fillCaloCompatibility is on, which it is not, but the
# FileInPath in the PSet resolves when the configuration is translated, before
# any module is constructed and regardless of what reads it. Dropping the
# whole block is the only thing that prevents that.
del process.muons.MuonCaloCompatibility

# The muon timing filler runs whether or not it is asked to, and it hands
# every muon to MuonSegmentMatcher, which fetches the CSC segments and the RPC
# rec hits before it can know that a barrel muon will have neither. Nothing in
# this example reconstructs CSC or RPC - the gun fires into |eta| < 0.8 and
# there are no CSC or RPC digis in the file - so both collections are produced
# empty, which is what their local reconstruction would produce here anyway.
# See plugins/EmptyMuonCollectionProducers.cc.
process.cscSegments = cms.EDProducer("EmptyCSCSegmentProducer")
process.rpcRecHits = cms.EDProducer("EmptyRPCRecHitProducer")

# --- generator particles ----------------------------------------------------
# The gun's muons as reco::GenParticles, so that the nanoAOD file carries the
# truth next to the reconstruction and the two can be compared outside CMSSW.
# The digi file kept the generator's HepMC product; only the unsmeared
# instance is in it, which is the right one to compare momenta against - the
# smearing moves the production vertex, not the momentum.
process.load("SimGeneral.HepPDTESSource.pythiapdt_cfi")
from PhysicsTools.HepMCCandAlgos.genParticles_cfi import genParticles as _genParticles

process.genParticles = _genParticles.clone(src=cms.InputTag("generator", "unsmeared"))

# The standard nano gen-particle pruning and table, pointed at those, exactly
# as examples/NanoGen does it.
process.load("PhysicsTools.NanoAOD.genparticles_cff")
process.finalGenParticles.src = cms.InputTag("genParticles")

# --- the nanoAOD tables -----------------------------------------------------
# The Muon table. The shipped nano muon table (PhysicsTools/NanoAOD/python/
# muons_cff.py) reads pat::Muons and fills ~80 columns of identification and
# isolation, none of which exists here; this is the same flat-table producer
# over reco::Muon directly, with the columns this chain actually filled.
from PhysicsTools.NanoAOD.common_cff import P4Vars, Var

process.muonTable = cms.EDProducer(
    "SimpleRecoMuonFlatTableProducer",
    src=cms.InputTag("muons"),
    cut=cms.string(""),
    name=cms.string("Muon"),
    doc=cms.string("reco::Muons from the global + standalone reconstruction"),
    singleton=cms.bool(False),
    extension=cms.bool(False),
    variables=cms.PSet(
        P4Vars,
        charge=Var("charge", int, doc="electric charge"),
        isGlobal=Var("isGlobalMuon", bool, doc="muon is a global muon"),
        isStandalone=Var("isStandAloneMuon", bool, doc="muon is a standalone muon"),
    ),
)

process.nanoMetadata = cms.EDProducer(
    "UniqueStringProducer",
    strings=cms.PSet(tag=cms.string("muon-gun")),
)

# --- the measurement --------------------------------------------------------
# The same analyzer the tracking and muon jobs use, on the global fit.
#
# Measured: 0.87%, against the tracker's 0.81% and the muon system's 23%. That
# is the combination behaving as it should at these momenta - the tracker
# measurement dominates, and adding a 23% measurement to a 0.8% one cannot
# improve it much. The bound is the tracker job's 2%, which a global fit that
# had lost its tracker hits could not pass.
#
# The other number worth reading is in the analyzer's quality line: the fit
# uses 14 tracker layers and 4 pixel layers, and its chi2/ndof is 0.87. The
# standalone fit of the same muons gives 110 (see python/muon_gun_muons_cfg.py
# - not understood, and flagged in the README), so whatever is wrong there
# does not survive into the global fit.
process.globalMuonResolution = cms.EDAnalyzer(
    "TrackResolution",
    tracks=cms.InputTag("globalMuons"),
    simTracks=cms.InputTag("g4SimHits"),
    minPt=cms.double(1.0),
    maxDeltaR=cms.double(0.1),
    maxMedianPtResolution=cms.double(0.02),
    # A global muon needs both a tracker track and a standalone track, so the
    # efficiency is the product of the two stages that made them, and the
    # standalone stage is the limiting one. Measured: 17/20.
    minEfficiency=cms.double(0.7),
    # 0.9% momentum resolution leaves no ambiguity in the sign of the
    # curvature, so every charge must be right - as it is for the tracker,
    # and unlike the standalone fit
    minChargeAgreement=cms.double(1.0),
    # The global fit is dominated by the tracker hits, so its chi2 was the
    # one number in this chain that stayed reasonable even while the muon
    # hits feeding it were displaced - which is exactly why the standalone
    # job, not this one, is where that bound has teeth.
    maxMedianChi2=cms.double(2.0),
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
    * process.cscSegments
    * process.rpcRecHits
    * process.dt1DRecHits
    * process.dt4DSegments
    * process.ancientMuonSeed
    * process.standAloneMuons
    * process.globalMuons
    * process.muons
    * process.genParticles
    * process.finalGenParticles
    * process.genParticleTable
    * process.muonTable
    * process.nanoMetadata
    * process.globalMuonResolution
)

process.out = cms.OutputModule(
    "NanoAODOutputModule",
    fileName=cms.untracked.string("muon_gun_nano.root"),
    outputCommands=cms.untracked.vstring(
        "drop *",
        "keep nanoaodFlatTable_*_*_*",
        "keep nanoaodUniqueString_nanoMetadata_*_*",
        "keep edmTriggerResults_*_*_*",
    ),
    compressionLevel=cms.untracked.int32(9),
    compressionAlgorithm=cms.untracked.string("LZMA"),
    SelectEvents=cms.untracked.PSet(SelectEvents=cms.vstring("p")),
)

process.end = cms.EndPath(process.out)
