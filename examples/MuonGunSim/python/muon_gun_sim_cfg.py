# Geant4 detector simulation: fire muons into the real CMS geometry and read
# back the SimHits they leave.
#
# This is the first example in this flake where a particle is actually
# transported. Everything before it either read hits from a file or made toy
# digis by hand; here OscarMTProducer builds the whole CMS detector out of the
# DDD XML description, hands it to Geant4, and steps muons through it in the
# volume-based magnetic field. The hits come out of the transport, not out of
# a producer that was told what to write.
#
# Runs on both releases. They do not transport the muons through the same
# Geant4: 10_6 links Geant4 10.4, built here against the CLHEP the release
# uses, and 20_1 the nixpkgs Geant4 11 - so this is also the first example
# where the two eras are doing genuinely different physics rather than the
# same physics through a renamed interface. The `_is_10_6` guards below are
# about where a data file is named, not about the simulation itself.
import os

import FWCore.ParameterSet.Config as cms

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("SIM")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))

# --- the full 2018 detector description ------------------------------------
# Not the filtered geometries the reco examples use: a simulation transports
# particles through everything, so the beam pipe, the forward region and the
# support structure all have to be in the DDD description. Leaving a piece out
# does not just lose hits, it changes the material budget the muon crosses.
process.load("Configuration.Geometry.GeometryExtended2018_cff")

# --- the real magnetic field -----------------------------------------------
# The volume-based engine, as in examples/MagneticFieldMap. A muon gun in a
# uniform field would still make hits, so this is not what the assertions
# below test - but the bending is only right with the real map.
process.load("MagneticField.Engine.volumeBasedMagneticField_160812_cfi")

# --- random numbers --------------------------------------------------------
# Both the gun and Geant4 draw from the service; without an entry for a module
# label the framework refuses to run it.
process.RandomNumberGeneratorService = cms.Service(
    "RandomNumberGeneratorService",
    generator=cms.PSet(
        initialSeed=cms.untracked.uint32(123456789),
        engineName=cms.untracked.string("HepJamesRandom"),
    ),
    generatorSmeared=cms.PSet(
        initialSeed=cms.untracked.uint32(98765432),
        engineName=cms.untracked.string("HepJamesRandom"),
    ),
    g4SimHits=cms.PSet(
        initialSeed=cms.untracked.uint32(11),
        engineName=cms.untracked.string("HepJamesRandom"),
    ),
)

# --- the particle data table -----------------------------------------------
# FlatRandomPtGunProducer looks the muon's mass and charge up in the PDT when
# the run begins, and Geant4 builds its own particle list from the same table.
# Without the ESSource the job dies at global begin run with 'No "PDTRecord"
# record found in the EventSetup' before a single event is generated - the gun
# never even gets to fire.
process.load("SimGeneral.HepPDTESSource.pythiapdt_cfi")

# --- the gun ---------------------------------------------------------------
# Muons into the barrel: |eta| < 0.8 keeps them clear of the endcap
# transition, so every one of them crosses the full pixel/strip tracker and
# then all four DT stations. 10-50 GeV is stiff enough to reach the muon
# system but soft enough to bend measurably.
process.generator = cms.EDProducer(
    "FlatRandomPtGunProducer",
    PGunParameters=cms.PSet(
        PartID=cms.vint32(13),
        MinPt=cms.double(10.0),
        MaxPt=cms.double(50.0),
        MinEta=cms.double(-0.8),
        MaxEta=cms.double(0.8),
        MinPhi=cms.double(-3.14159265359),
        MaxPhi=cms.double(3.14159265359),
    ),
    AddAntiParticle=cms.bool(True),
    Verbosity=cms.untracked.int32(0),
    firstRun=cms.untracked.uint32(1),
    psethack=cms.string("single mu pt 10-50"),
)

# --- vertex smearing -------------------------------------------------------
# The real chain is gun -> vertex smearing -> Geant4. The cfi names its module
# VtxSmeared, but g4SimHits reads HepMCProductLabel = "generatorSmeared", and
# nothing in this package subset bridges the two: the rename lives in
# Configuration/StandardSequences, which a simulation-only build does not
# carry. So the module is renamed here, which is what the SIM step ends up
# with anyway. Displacing the vertex over the 2018 beam spot rather than
# firing everything from (0,0,0) is also what makes the muons cross the pixel
# modules at realistic angles.
process.load("IOMC.EventVertexGenerators.VtxSmearedRealistic25ns13TeVEarly2018Collision_cfi")
process.generatorSmeared = process.VtxSmeared.clone()
del process.VtxSmeared

# --- Geant4 ----------------------------------------------------------------
# The stock CMS simulation module: the CMS sensitive detectors, the CMS
# production cuts, and whichever physics list the release defaults to. That
# default is not the same in the two eras - 10_6 picks FTFP_BERT_EMM, 20_1
# FTFP_BERT_EMH - and the difference is real: the EMH variant hands electron,
# positron and gamma transport to G4HepEm, a separate external this flake has
# to build (see pkgs/g4hepem.nix). Both are left as the release ships them,
# because a muon crossing the detector is a hadronic-list question either way.
process.load("SimG4Core.Application.g4SimHits_cfi")

# --- the two forward shower libraries we cannot ship ------------------------
# g4SimHits_cfi names two data files that are not in the release tarball:
#
#   SimG4CMS/Calo/data/HFShowerLibrary_oldpmt_noatt_eta4_16en_v3.root
#   SimG4CMS/Forward/data/CastorShowerLibrary_CMSSW500_Standard.root
#
# They are pre-generated shower libraries for HF and Castor, distributed
# separately. The download.url files in the release point at cmsdoc.cern.ch,
# which now sits behind CERN SSO, and the cms-data/SimG4CMS-Calo repository is
# empty - so there is no way to fetch them here.
#
# This is not optional to work around: edm::FileInPath resolves when the
# python configuration is translated into the C++ ParameterSet, before any
# module is constructed, so an unresolvable path aborts the job at startup
# even though nothing would ever have read the file. Both are pointed at a
# file that does ship, and the libraries are switched off, so HF and Castor
# fall back to parameterised showers.
#
# None of this touches the measurement below: a muon fired into |eta| < 0.8
# never reaches HF (|eta| > 3) or Castor (|eta| > 5).
_present = cms.FileInPath("SimG4CMS/Calo/data/responsTBpim50.dat")
# The switch that decides whether HFShowerLibrary is *constructed* lives in
# HCalSD, not in the HFShower or HFShowerLibrary PSets - those only configure
# the object once it exists. With UseShowerLibrary false and UseParametrize
# left false, HCalSD::HCalSD falls through to plain HFShower, the direct
# Cherenkov simulation, and never opens the file. Setting the switch on the
# wrong PSet leaves the library being built and the job dies on the first
# event with "HFShowerLibrary Events tree absent".
process.g4SimHits.HCalSD.UseShowerLibrary = cms.bool(False)
process.g4SimHits.CastorSD.useShowerLibrary = cms.bool(False)
process.g4SimHits.CastorShowerLibrary.FileName = _present

# The HF library path is in different places in the two releases. 10_6 spells
# it inline in g4SimHits_cfi; 20_1 moved it to Geometry/HcalSimData, where
# HFParameters_cff defines a top-level HFLibraryFileBlock that g4SimHits
# reaches through refToPSet_. Loading g4SimHits_cfi brings that PSet into the
# process along with the module, so it is process.HFLibraryFileBlock that has
# to be redirected - setting it on process.g4SimHits.HFShowerLibrary there
# would write to the PSet holding the reference, not the one holding the path,
# and the job would still die resolving the original FileInPath.
if _is_10_6:
    process.g4SimHits.HFShowerLibrary.FileName = _present
else:
    process.HFLibraryFileBlock.FileName = _present

# --- what has to be there afterwards ---------------------------------------
process.simHits = cms.EDAnalyzer(
    "SimHitCounter",
    required=cms.VInputTag(
        # the pixel barrel and all four strip barrel layers: a barrel muon
        # crosses every one of them
        cms.InputTag("g4SimHits", "TrackerHitsPixelBarrelLowTof"),
        cms.InputTag("g4SimHits", "TrackerHitsTIBLowTof"),
        cms.InputTag("g4SimHits", "TrackerHitsTOBLowTof"),
        # ... and then the drift tubes
        cms.InputTag("g4SimHits", "MuonDTHits"),
    ),
    simTracks=cms.InputTag("g4SimHits"),
    simVertices=cms.InputTag("g4SimHits"),
    # A minimum-ionising muon deposits O(100 keV) per silicon sensor and per
    # DT cell. Summed over 4 collections x 5 events x 2 muons this lands in
    # the MeV range; the window is wide because the gun randomises pt and
    # eta, but it still excludes zero and excludes anything GeV-scale, which
    # is what a broken geometry or a runaway shower would give.
    minTotalEnergy=cms.double(10.0),  # keV
    maxTotalEnergy=cms.double(1.0e6),  # keV = 1 GeV
)

process.out = cms.OutputModule(
    "PoolOutputModule",
    fileName=cms.untracked.string("muon_gun_sim.root"),
    outputCommands=cms.untracked.vstring(
        "drop *",
        "keep *_g4SimHits_*_*",
        "keep *_generator_*_*",
        "keep *_generatorSmeared_*_*",
    ),
)

process.p = cms.Path(
    process.generator * process.generatorSmeared * process.g4SimHits * process.simHits
)
process.e = cms.EndPath(process.out)
