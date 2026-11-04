# NanoGen: generate Z -> mumu with Pythia 8 and write the gen-level nanoAOD
# tables (GenPart, GenJet, generator info and weights) to a flat NanoAOD
# file - the first end-to-end "process -> NanoAOD" chain of this build.
#
# The PDF is pythia's internal NNPDF 2.3 default, so no LHAPDF data sets are
# needed; the shipped nanogen_cff is not used because it also runs the
# Rivet-based particle-level tables and the pat jet-flavour machinery, which
# are not part of this build. The tables below are the core NanoGen content.
import FWCore.ParameterSet.Config as cms

process = cms.Process("NANOGEN")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 100
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(200))

process.RandomNumberGeneratorService = cms.Service(
    "RandomNumberGeneratorService",
    generator=cms.PSet(
        initialSeed=cms.untracked.uint32(12345),
        engineName=cms.untracked.string("HepJamesRandom"),
    ),
)

# --- the generator: on-shell Z production, Z -> mumu
process.generator = cms.EDFilter(
    "Pythia8GeneratorFilter",
    comEnergy=cms.double(13000.0),
    maxEventsToPrint=cms.untracked.int32(1),
    pythiaPylistVerbosity=cms.untracked.int32(1),
    pythiaHepMCVerbosity=cms.untracked.bool(False),
    filterEfficiency=cms.untracked.double(1.0),
    PythiaParameters=cms.PSet(
        processParameters=cms.vstring(
            "WeakSingleBoson:ffbar2gmZ = on",
            "23:onMode = off",
            "23:onIfAny = 13",
            "PhaseSpace:mHatMin = 50.",
        ),
        parameterSets=cms.vstring("processParameters"),
    ),
)

# --- particle data table (from the packaged .tbl file, no conditions DB)
process.load("SimGeneral.HepPDTESSource.pythiapdt_cfi")

# --- reco::GenParticles straight from the generator (no vertex smearing in
# this gen-only job, so read the "unsmeared" HepMC product directly)
from PhysicsTools.HepMCCandAlgos.genParticles_cfi import genParticles as _genParticles
process.genParticles = _genParticles.clone(src=cms.InputTag("generator", "unsmeared"))

# --- the nano GenPart table: the standard pruning + flat-table producer.
# The 10_6 cff is written for miniAOD input, so point the pruner at our
# freshly produced genParticles instead of pat's prunedGenParticles.
process.load("PhysicsTools.NanoAOD.genparticles_cff")
process.finalGenParticles.src = cms.InputTag("genParticles")
# Later releases add a lepton isolation column computed from miniAOD's packed
# gen particles, which a gen-only job does not have; drop it, as the shipped
# nanogen_cff's customizeNanoGEN does.
if hasattr(getattr(process.genParticleTable, "externalVariables", None), "iso"):
    delattr(process.genParticleTable.externalVariables, "iso")

# --- gen jets: the standard AK4 clustering on stable gen particles (without
# neutrinos, as the nano GenJet collection has it). The selector is declared
# inline: its cff lives in RecoJets/Configuration, a python-only package not
# in this build.
process.genParticlesForJets = cms.EDProducer(
    "InputGenJetsParticleSelector",
    src=cms.InputTag("genParticles"),
    ignoreParticleIDs=cms.vuint32(
        1000022, 1000012, 1000014, 1000016,
        2000012, 2000014, 2000016,
        1000039, 5100039,
        4000012, 4000014, 4000016,
        9900012, 9900014, 9900016,
        39,
        # no neutrinos in the jet clustering
        12, 14, 16,
    ),
    partonicFinalState=cms.bool(False),
    excludeResonances=cms.bool(False),
    excludeFromResonancePids=cms.vuint32(12, 13, 14, 16),
    tausAsJets=cms.bool(False),
)
process.load("RecoJets.JetProducers.ak4GenJets_cfi")
from PhysicsTools.NanoAOD.common_cff import P4Vars
process.genJetTable = cms.EDProducer(
    "SimpleCandidateFlatTableProducer",
    src=cms.InputTag("ak4GenJets"),
    cut=cms.string("pt > 10"),
    name=cms.string("GenJet"),
    doc=cms.string("AK4 gen jets (no neutrinos), pt > 10 GeV"),
    singleton=cms.bool(False),
    extension=cms.bool(False),
    variables=cms.PSet(P4Vars),
)

# --- generator info: the event weight table and the run/event-level info
process.load("PhysicsTools.NanoAOD.genWeightsTable_cfi")
from PhysicsTools.NanoAOD.globals_cff import genTable as _genTable
process.genTable = _genTable.clone()

process.nanoMetadata = cms.EDProducer(
    "UniqueStringProducer",
    strings=cms.PSet(tag=cms.string("nanogen")),
)

# --- in-process validation of the generated events
process.checker = cms.EDAnalyzer(
    "GenZmumuChecker",
    genParticles=cms.InputTag("genParticles"),
    minZFraction=cms.double(0.8),
)

process.p = cms.Path(
    process.generator
    * process.genParticles
    * process.finalGenParticles
    * process.genParticleTable
    * process.genParticlesForJets
    * process.ak4GenJets
    * process.genJetTable
    * process.genWeightsTable
    * process.genTable
    * process.nanoMetadata
    * process.checker
)

process.out = cms.OutputModule(
    "NanoAODOutputModule",
    fileName=cms.untracked.string("nanogen.root"),
    outputCommands=cms.untracked.vstring(
        "drop *",
        "keep nanoaodFlatTable_*_*_*",
        "keep nanoaodMergeableCounterTable_*_*_*",
        "keep nanoaodUniqueString_nanoMetadata_*_*",
        "keep edmTriggerResults_*_*_*",
    ),
    compressionLevel=cms.untracked.int32(9),
    compressionAlgorithm=cms.untracked.string("LZMA"),
    SelectEvents=cms.untracked.PSet(SelectEvents=cms.vstring("p")),
)

process.end = cms.EndPath(process.out)
