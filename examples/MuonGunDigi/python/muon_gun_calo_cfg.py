# The calorimeters: digitisation and local reconstruction of the energy the
# muons left in ECAL and HCAL on their way out.
#
# Every stage so far has followed the muon through the *tracking* detectors -
# silicon, then drift tubes. Between them sit the calorimeters, and Geant4 has
# been depositing energy in them all along: muon_gun_digi.root carries
# EcalHitsEB and HcalHits alongside the tracker SimHits, and until now nothing
# has read them.
#
# This job digitises those hits with the real ECAL and HCAL digitisers and
# reconstructs them back, which makes it a different kind of measurement from
# the ones before. A tracker rec hit is a *position*, and the question was
# whether it lands where the particle crossed. A calorimeter rec hit is an
# *energy*, and the question is whether the number that comes out is the
# number Geant4 put in - through the photostatistics, the preamplifier pulse
# shape, the ten-sample digitisation, and the weights that fit an amplitude
# back out of those samples.
#
# The muons make this a sharp test rather than a vague one. A muon is a
# minimum-ionising particle: it does not shower, it crosses one crystal and
# deposits a couple of hundred MeV, and that is the smallest signal ECAL is
# ever asked to reconstruct - a few times the noise. If the energy scale is
# wrong anywhere in that chain, a MIP is where it shows.
#
# The calorimeter digitisers are run here rather than in
# python/muon_gun_digi_cfg.py on purpose. They would share that job's mixing
# module, and the digitisers inside one MixingModule draw their noise from one
# random engine, so adding them would move every tracker digi and shift the
# measured residuals of four downstream jobs. Nothing is lost by the split:
# `mix` reads the SimHits out of the event it is given, and the SimHits are in
# the file.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os

import FWCore.ParameterSet.Config as cms

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("CALO")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:muon_gun_digi.root"),
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

# --- geometry ---------------------------------------------------------------
# The same 2018 description the simulation ran in, plus the calorimeter
# geometry built on top of it. examples/CaloLocalReco builds the same set of
# ES producers from a *filtered* XML file list, because it loads only the
# calorimeter subdetectors and has to drop the world-detail files that
# position volumes it no longer defines. Here the whole detector is loaded, so
# there is nothing to filter.
process.load("Configuration.Geometry.GeometryExtended2018_cff")

# The Hcal DDD constants and topology: their cfi files are scram-generated and
# not part of this build, so the ES producers are declared directly.
process.hcalParameters = cms.ESProducer("HcalParametersESModule")
process.hcalDDDSimConstants = cms.ESProducer("HcalDDDSimConstantsESModule")
process.hcalDDDRecConstants = cms.ESProducer("HcalDDDRecConstantsESModule")
process.hcalTopologyIdeal = cms.ESProducer(
    "HcalTopologyIdealEP",
    Exclude=cms.untracked.string(""),
    MergePosition=cms.untracked.bool(False),
)

process.load("Geometry.EcalAlgo.EcalGeometry_cfi")
process.load("Geometry.HcalEventSetup.HcalGeometry_cfi")
process.load("Geometry.HcalEventSetup.CaloTowerGeometry_cfi")
process.load("Geometry.HcalEventSetup.CaloTowerTopology_cfi")
process.load("Geometry.CaloEventSetup.CaloGeometryBuilder_cfi")
process.CaloGeometryBuilder.SelectedCalos = cms.vstring(
    "HCAL", "EcalBarrel", "EcalEndcap", "EcalPreshower", "TOWER"
)
process.load("Geometry.CaloEventSetup.CaloTopology_cfi")
process.load("Geometry.CaloEventSetup.CaloTowerConstituents_cfi")
process.load("Geometry.CaloEventSetup.EcalTrigTowerConstituents_cfi")

# --- conditions -------------------------------------------------------------
# Everything ECAL from the trivial retriever, everything HCAL from the
# hardcoded calibrations source - the same providers examples/CaloLocalReco
# uses, and the reason this works at all without a conditions database.
#
# It also makes the measurement below a fair one. The digitiser and the
# reconstruction read the *same* pedestals, gain ratios, intercalibration
# constants and ADC-to-GeV constant out of this one ES source, so an energy
# that goes in and comes out unchanged is a statement about the chain rather
# than about how well two sets of constants happen to agree.
process.load("CalibCalorimetry.EcalTrivialCondModules.EcalTrivialCondRetriever_cfi")
# read from paths relative to the working directory - run cmsRun from the
# example root. These are the EB/EE/APD pulse shapes extracted from the
# hardcoded arrays in SimCalorimetry/EcalSimAlgos; in production the payload
# comes from the conditions database.
process.EcalTrivialConditionRetriever.EBSimPulseShapeFile = cms.untracked.string(
    "data/EB_SimPulseShape.txt")
process.EcalTrivialConditionRetriever.EESimPulseShapeFile = cms.untracked.string(
    "data/EE_SimPulseShape.txt")
process.EcalTrivialConditionRetriever.APDSimPulseShapeFile = cms.untracked.string(
    "data/APD_SimPulseShape.txt")
process.load("CalibCalorimetry.EcalLaserCorrection.ecalLaserCorrectionService_cfi")

process.load("CalibCalorimetry.HcalPlugins.Hcal_Conditions_forGlobalTag_cff")
process.es_hardcode.toGet = cms.untracked.vstring(
    "GainWidths", "Gains", "Pedestals", "PedestalWidths",
    "EffectivePedestals", "EffectivePedestalWidths",
    "QIEData", "QIETypes", "ElectronicsMap", "ChannelQuality",
    "RespCorrs", "TimeCorrs", "LUTCorrs", "PFCorrs", "ZSThresholds",
    "L1TriggerObjects", "RecoParams", "SiPMParameters",
    "SiPMCharacteristics", "LutMetadata", "MCParams", "FrontEndMap",
    "TPParameters", "TPChannelParameters",
)
process.es_hardcode.GainWidthsForTrigPrims = cms.bool(True)

# The preshower conditions. Nothing here reads them - the preshower is at
# |eta| > 1.65 and this gun fires into |eta| < 0.8 - but EcalDigiProducer
# constructs its preshower digitiser before it looks at doES and then fetches
# four ES records whether or not it will use them, and nothing in the release
# provides them without a conditions database. See
# plugins/PreshowerTrivialConditions.cc.
process.preshowerConditions = cms.ESProducer(
    "PreshowerTrivialConditions",
    gain=cms.double(1.0),
    mipToGeVLow=cms.double(9.0e-6),
    mipToGeVHigh=cms.double(9.0e-6),
)
for _record in ("ESGainRcd", "ESMIPToGeVConstantRcd", "ESPedestalsRcd",
                "ESIntercalibConstantsRcd"):
    setattr(process, "essource" + _record, cms.ESSource(
        "EmptyESSource",
        recordName=cms.string(_record),
        firstValid=cms.vuint32(1),
        iovIsRunNotTime=cms.bool(True),
    ))

# The severity-level computers the rec-hit producers consult to decide which
# channels to trust. The HCAL one is declared with its fillDescriptions
# defaults: its cfi is scram-generated and not part of this build.
process.load("RecoLocalCalo.EcalRecAlgos.EcalSeverityLevelESProducer_cfi")
process.essourceSev = cms.ESSource(
    "EmptyESSource",
    recordName=cms.string("HcalSeverityLevelComputerRcd"),
    firstValid=cms.vuint32(1),
    iovIsRunNotTime=cms.bool(True),
)


def _severityLevel(level, flags=[""], status=[""]):
    return cms.PSet(
        RecHitFlags=cms.vstring(*flags),
        ChannelStatus=cms.vstring(*status),
        Level=cms.int32(level),
    )


process.hcalRecAlgos = cms.ESProducer(
    "HcalRecAlgoESProducer",
    phase=cms.uint32(0),
    RecoveredRecHitBits=cms.vstring("TimingAddedBit", "TimingSubtractedBit"),
    SeverityLevels=cms.VPSet(
        _severityLevel(0),
        _severityLevel(1, status=["HcalCellCaloTowerProb"]),
        _severityLevel(
            5,
            flags=["HSCP_R1R2", "HSCP_FracLeader", "HSCP_OuterEnergy",
                   "HSCP_ExpFit", "ADCSaturationBit", "HBHEIsolatedNoise",
                   "AddedSimHcalNoise"],
            status=["HcalCellExcludeFromHBHENoiseSummary"],
        ),
        _severityLevel(
            8,
            flags=["HBHEHpdHitMultiplicity", "HBHEPulseShape", "HOBit",
                   "HFDigiTime", "HFInTimeWindow", "ZDCBit", "CalibrationBit",
                   "TimingErrorBit", "HBHEFlatNoise", "HBHESpikeNoise",
                   "HBHETriangleNoise", "HBHETS4TS5Noise",
                   "HBHENegativeNoise", "HBHEOOTPU"],
        ),
        _severityLevel(11, flags=["HFLongShort", "HFPET", "HFS8S1Ratio"]),
        _severityLevel(12, status=["HcalCellCaloTowerMask"]),
        _severityLevel(15, status=["HcalCellHot"]),
        _severityLevel(20, status=["HcalCellOff", "HcalCellDead"]),
    ),
    DropChannelStatusBits=cms.vstring(
        "HcalCellMask", "HcalCellOff", "HcalCellDead"
    ),
)


# 20_1 moved the per-channel reconstruction constants out of
# HBHEPhase1Reconstructor and into an EventSetup product of their own:
# HcalChannelPropertiesEP gathers the conditions, the reco params, the
# severity computer, the channel quality and the geometry into one
# HcalChannelPropertiesRecord that the reconstructor then consumes. Nothing
# loads it here - in production it comes with the reco sequence cff - so
# without it the job dies with "No HcalChannelPropertiesRecord record found
# in the EventSetup". The 10_6 reconstructor read the parent records itself.
if not _is_10_6:
    process.load("RecoLocalCalo.HcalRecAlgos.hcalChannelPropertiesESProd_cfi")

# --- random numbers ---------------------------------------------------------
# The calorimeter digitisers draw photostatistics and electronics noise, and
# like the tracker ones they draw through the service under the label of the
# module that owns them.
process.RandomNumberGeneratorService = cms.Service(
    "RandomNumberGeneratorService",
    mix=cms.PSet(
        initialSeed=cms.untracked.uint32(24680),
        engineName=cms.untracked.string("HepJamesRandom"),
    ),
)

# --- digitisation -----------------------------------------------------------
# The ECAL and HCAL digitisers, in the mixing module that owns them, reading
# the SimHits out of the input file.
from SimGeneral.MixingModule.mixObjects_cfi import theMixObjects
from SimGeneral.MixingModule.ecalDigitizer_cfi import ecalDigitizer
from SimGeneral.MixingModule.hcalDigitizer_cfi import hcalDigitizer

# The preshower is at |eta| > 1.65 and this gun fires into |eta| < 0.8, so
# there is nothing there to digitise.
ecalDigitizer.doES = cms.bool(False)

process.mix = cms.EDProducer(
    "MixingModule",
    digitizers=cms.PSet(
        ecal=cms.PSet(ecalDigitizer),
        hcal=cms.PSet(hcalDigitizer),
    ),
    LabelPlayback=cms.string(""),
    minBunch=cms.int32(0),
    maxBunch=cms.int32(0),
    bunchspace=cms.int32(25),
    mixProdStep1=cms.bool(False),
    mixProdStep2=cms.bool(False),
    playback=cms.untracked.bool(False),
    useCurrentProcessOnly=cms.bool(False),
    mixObjects=cms.PSet(theMixObjects),
)

from SimGeneral.MixingModule.aliases_cfi import (
    simEcalUnsuppressedDigis,
    simHcalUnsuppressedDigis,
)

process.simEcalUnsuppressedDigis = simEcalUnsuppressedDigis
process.simHcalUnsuppressedDigis = simHcalUnsuppressedDigis

# --- ECAL local reconstruction ----------------------------------------------
# The weights method: ten digitised samples in, one amplitude out, by a linear
# fit whose weights are chosen so that the pedestal and the pulse shape are
# separated. Then the calibrated rec hit, which multiplies that amplitude by
# the intercalibration constant, the laser correction and the ADC-to-GeV
# constant.
#
# The unsuppressed digis are fed straight in. A production job puts the
# selective-readout emulation in between, which decides which crystals are
# read out at full precision - a data-volume question, not a reconstruction
# one, and the muons here would land in whatever is read out anyway.
from RecoLocalCalo.EcalRecProducers.ecalWeightUncalibRecHit_cfi import (
    ecalWeightUncalibRecHit as _ecalWeightUncalibRecHit,
)

process.ecalWeightUncalibRecHit = _ecalWeightUncalibRecHit.clone(
    EBdigiCollection=cms.InputTag("simEcalUnsuppressedDigis"),
    EEdigiCollection=cms.InputTag("simEcalUnsuppressedDigis"),
)

from RecoLocalCalo.EcalRecProducers.ecalRecHit_cfi import ecalRecHit as _ecalRecHit

# No dead-channel recovery: it runs off the trigger primitives, which this
# job does not produce.
process.ecalRecHit = _ecalRecHit.clone(
    EBuncalibRecHitCollection=cms.InputTag("ecalWeightUncalibRecHit", "EcalUncalibRecHitsEB"),
    EEuncalibRecHitCollection=cms.InputTag("ecalWeightUncalibRecHit", "EcalUncalibRecHitsEE"),
    killDeadChannels=cms.bool(False),
    recoverEBIsolatedChannels=cms.bool(False),
    recoverEEIsolatedChannels=cms.bool(False),
    recoverEBVFE=cms.bool(False),
    recoverEEVFE=cms.bool(False),
    recoverEBFE=cms.bool(False),
    recoverEEFE=cms.bool(False),
)

# --- HCAL local reconstruction ----------------------------------------------
# The phase-1 reconstructor on the QIE8 digis: Mahi, with the M0 fallback.
# M3 needs time-slew delay parameters this build does not carry, and the
# negative-energy filter payload only exists in the conditions database.
from RecoLocalCalo.HcalRecProducers.HBHEPhase1Reconstructor_cfi import (
    hbheprereco as _hbheprereco,
)

process.hbheprereco = _hbheprereco.clone(
    digiLabelQIE8=cms.InputTag("simHcalUnsuppressedDigis"),
    processQIE11=cms.bool(False),
    setNegativeFlagsQIE8=cms.bool(False),
)
process.hbheprereco.algorithm.useM3 = cms.bool(False)

# --- the measurement --------------------------------------------------------
# For every calorimeter cell Geant4 deposited energy in, compare the
# reconstructed energy with the simulated one. See
# plugins/CaloEnergyResponse.cc.
process.calo = cms.EDAnalyzer(
    "CaloEnergyResponse",
    ebRecHits=cms.InputTag("ecalRecHit", "EcalRecHitsEB"),
    hbheRecHits=cms.InputTag("hbheprereco"),
    ebSimHits=cms.InputTag("g4SimHits", "EcalHitsEB"),
    hcalSimHits=cms.InputTag("g4SimHits", "HcalHits"),
    simTracks=cms.InputTag("g4SimHits"),
    # Only cells with a real deposit. The two thresholds differ by two orders
    # of magnitude because the two SimHit energies mean different things: an
    # ECAL PCaloHit carries the energy the crystal absorbed, an HCAL one the
    # much smaller energy the scintillator saw. 20 MeV in a crystal is a
    # tenth of a MIP; 0.5 MeV in a scintillator layer reconstructs to about
    # 60 MeV, which is where HCAL noise starts. With the ECAL threshold
    # applied to HCAL as well, only the top six cells of the whole run
    # survive - the two scales are genuinely that far apart.
    minEbSimEnergy=cms.double(0.02),
    minHbSimEnergy=cms.double(0.0005),
    # Measured: 100% of the cells with a deposit have a rec hit. The bound
    # allows for one cell in ten falling below the reconstruction threshold.
    minEbEfficiency=cms.double(0.9),
    # Measured: 1.03 in 10_6, 1.09 in 20_1. ECAL is homogeneous, so what the
    # crystal absorbed is
    # what the reconstruction should report, and the answer is one. The 20%
    # window is wide enough for the noise on a 300 MeV signal and narrow
    # enough that a wrong calibration constant, pulse shape or amplitude fit
    # cannot pass - those get it wrong by factors, not percent.
    minEbResponse=cms.double(0.8),
    maxEbResponse=cms.double(1.2),
    # Measured: 0.34 GeV in 10_6, 0.44 GeV in 20_1. The two releases run
    # different Geant4 versions (10.4 and 11.4), so what is deposited differs
    # and not only what is made of it.
    # A muon crossing 23 cm of PbWO4 at minimum ionisation
    # deposits about that, and it is the smallest signal ECAL is ever asked to
    # reconstruct - a few times the 40 MeV per-crystal noise.
    minEbMip=cms.double(0.15),
    maxEbMip=cms.double(0.6),
    # Measured: 0.0093 in 10_6, 0.012 in 20_1. This is the statement that the
    # calorimeter is seeing a
    # muon: an electron of the same momentum would deposit essentially all of
    # it, so E/p would be 1 rather than 1%.
    maxEOverP=cms.double(0.05),
    # Measured: 113 in 10_6 and 108 in 20_1, and 2.4 / 2.3 GeV of reconstructed
    # energy per muon, which is
    # the textbook figure for a muon crossing the barrel hadron calorimeter.
    # The HCAL response is the sampling factor, fixed by the
    # brass-to-scintillator ratio of the barrel; it is known to be around a
    # hundred but not to a percent, so the window is wide.
    minHbResponse=cms.double(50.0),
    maxHbResponse=cms.double(250.0),
)

# 20_1 took the det-info map away from the SiStripDetInfoFileReader service and
# made it a parameter of each fake ES source instead. Modules loaded from their
# cfis carry it already; ones declared by hand here do not, and the framework
# refuses to construct them without it. Done by walking the ES sources rather
# than naming them, so a source added later cannot quietly miss out.
if not _is_10_6:
    _detinfo = cms.FileInPath("CalibTracker/SiStripCommon/data/SiStripDetInfo.dat")
    for _essrc in process.es_sources_().values():
        if _essrc.type_().startswith("SiStrip") and _essrc.type_().endswith("FakeESSource"):
            if not hasattr(_essrc, "SiStripDetInfoFile"):
                _essrc.SiStripDetInfoFile = _detinfo

process.p = cms.Path(
    process.mix
    * process.ecalWeightUncalibRecHit
    * process.ecalRecHit
    * process.hbheprereco
    * process.calo
)
