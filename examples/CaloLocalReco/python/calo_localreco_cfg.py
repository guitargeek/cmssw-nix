# Calorimeter local reco validation: toy EB + HB digis -> uncalibrated /
# calibrated rec hits -> calo towers, with the CaloGeometry built from the
# DDD XML detector description and all conditions from the trivial (Ecal) /
# fake (Hcal) conditions providers.
import os

import FWCore.ParameterSet.Config as cms

# Runs on both releases. Three cfi names differ; each is commented where it is
# used, and nothing else about the configuration changes.
_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("CALORECO")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

# --- geometry: the 2016 detector XML filtered to the world/envelope volumes
# and the Ecal + Hcal subdetectors
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
                "Geometry/EcalCommonData/",
                "Geometry/EcalSimData/",
                "Geometry/HcalCommonData/",
            )
        )
        # sim-only sens declarations whose part selectors reach into the
        # dropped forward-shield volumes (broken spec-pars crash the DDD
        # spec-par iteration in HcalParametersFromDD)
        and not f.endswith("hcalsenspmf.xml")
        # world-detail files that position volumes defined in dropped
        # subdetector files (ghost logical parts crash the spec-par scan)
        and not f.endswith(
            (
                "muonMB.xml",
                "muonMagnet.xml",
                "mgnt.xml",
                "cmsBeam.xml",
                "beampipe.xml",
                "cavern.xml",
                "cmsTracker.xml",
                "muonBase.xml",
                "cmsMuon.xml",
            )
        )
    ]
)

# Hcal DDD constants and topology (their cfi files are scram-generated and
# not part of this build - declare the ES producers directly)
process.hcalParameters = cms.ESProducer("HcalParametersESModule")
process.hcalDDDSimConstants = cms.ESProducer("HcalDDDSimConstantsESModule")
process.hcalDDDRecConstants = cms.ESProducer("HcalDDDRecConstantsESModule")
process.hcalTopologyIdeal = cms.ESProducer(
    "HcalTopologyIdealEP",
    Exclude=cms.untracked.string(""),
    MergePosition=cms.untracked.bool(False),
)

# the calo geometry builders (Ecal from the DD, Hcal from the DDD rec
# constants, calo-tower geometry/topology); restrict the merged CaloGeometry
# to the subdetectors whose XML is loaded
process.load("Geometry.EcalAlgo.EcalGeometry_cfi")
process.load("Geometry.HcalEventSetup.HcalGeometry_cfi")
process.load("Geometry.HcalEventSetup.CaloTowerGeometry_cfi")
# Declared directly rather than loaded: in 20_1 the cfi of that name is a
# backwards-compatibility shim that imports CaloTowerTopologyEP_cfi, which is
# scram-generated and not part of this build. The module takes no parameters,
# and this is exactly what the 10_6 cfi contains.
process.CaloTowerTopologyEP = cms.ESProducer("CaloTowerTopologyEP")
process.load("Geometry.CaloEventSetup.CaloGeometryBuilder_cfi")
process.CaloGeometryBuilder.SelectedCalos = cms.vstring(
    "HCAL", "EcalBarrel", "EcalEndcap", "TOWER"
)
process.load("Geometry.CaloEventSetup.CaloTopology_cfi")
process.load("Geometry.CaloEventSetup.CaloTowerConstituents_cfi")
process.load("Geometry.CaloEventSetup.EcalTrigTowerConstituents_cfi")

# --- conditions: everything Ecal from the trivial retriever, everything
# Hcal from the hardcoded calibrations ES source
process.load("CalibCalorimetry.EcalTrivialCondModules.EcalTrivialCondRetriever_cfi")
# the sim pulse shape files are read from plain paths relative to the
# working directory (run cmsRun from the example root)
process.EcalTrivialConditionRetriever.EBSimPulseShapeFile = cms.untracked.string("data/EB_SimPulseShape.txt")
process.EcalTrivialConditionRetriever.EESimPulseShapeFile = cms.untracked.string("data/EE_SimPulseShape.txt")
process.EcalTrivialConditionRetriever.APDSimPulseShapeFile = cms.untracked.string("data/APD_SimPulseShape.txt")
process.load("CalibCalorimetry.EcalLaserCorrection.ecalLaserCorrectionService_cfi")
process.load("CalibCalorimetry.HcalPlugins.Hcal_Conditions_forGlobalTag_cff")
# New in 20_1: HcalHardcodeCalibrations reaches for the ZDC topology as well,
# through the same HcalRecNumberingRecord. Nothing here reconstructs the ZDC -
# it is 140 m down the beam line - but the record has to be complete.
if not _is_10_6:
    process.zdcTopologyEP = cms.ESProducer("ZdcTopologyEP")
    # Also new in 20_1: the HBHE reconstructor reads its per-channel
    # calibrations through one bundled HcalChannelPropertiesRecord instead of
    # fetching the individual payloads itself - the same consolidation the
    # strip clusteriser went through (see examples/TrackerLocalReco).
    process.hcalChannelPropertiesEP = cms.ESProducer("HcalChannelPropertiesEP")
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

# severity-level computers used by the rec-hit producers / tower creator
# (the Hcal one is declared explicitly with the fillDescriptions defaults:
# its cfi is scram-generated and not part of this build)
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

# --- the toy digis
process.toyDigis = cms.EDProducer("ToyCaloDigiProducer")
process.emptyHcalRecHits = cms.EDProducer("EmptyHcalRecHitProducer")

# --- Ecal: weights-method uncalibrated rec hits, then calibrated rec hits
# (no dead-channel recovery: that would need the trigger-primitive path)
# The 20_1 ecalWeightUncalibRecHit_cfi is a one-line shim over a generated
# cfi (ecalWeightsUncalibRecHitProducer_cfi) that this build does not produce:
# EcalUncalibRecHitProducer registers several named descriptions, one per
# amplitude-reconstruction worker, and the generator emits only one of them.
# The one it does emit, ecalUncalibRecHit, is byte for byte what the 10_6
# hand-written cfi contains - the weights worker with an empty algoPSet.
if _is_10_6:
    from RecoLocalCalo.EcalRecProducers.ecalWeightUncalibRecHit_cfi import (
        ecalWeightUncalibRecHit as _ecalWeightUncalibRecHit,
    )
else:
    from RecoLocalCalo.EcalRecProducers.ecalUncalibRecHit_cfi import (
        ecalUncalibRecHit as _ecalWeightUncalibRecHit,
    )
process.ecalWeightUncalibRecHit = _ecalWeightUncalibRecHit.clone(
    EBdigiCollection=cms.InputTag("toyDigis"),
    EEdigiCollection=cms.InputTag("toyDigis"),
)
from RecoLocalCalo.EcalRecProducers.ecalRecHit_cfi import ecalRecHit as _ecalRecHit
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

# --- Hcal: the phase-1 HBHE reconstructor (Mahi/M2/M0) on the QIE8 digis
from RecoLocalCalo.HcalRecProducers.HBHEPhase1Reconstructor_cfi import (
    hbheprereco as _hbheprereco,
)
process.hbheprereco = _hbheprereco.clone(
    digiLabelQIE8=cms.InputTag("toyDigis"),
    processQIE11=cms.bool(False),
    # the negative-energy filter payload only exists in the conditions DB
    setNegativeFlagsQIE8=cms.bool(False),
)
# Mahi (the UL default) with the M0 fallback; the M3 deterministic fit needs
# time-slew delay parameters we do not carry
process.hbheprereco.algorithm.useM3 = cms.bool(False)

# --- calo towers from the EB + HBHE rec hits (HO/HF empty)
from RecoLocalCalo.CaloTowersCreator.calotowermaker_cfi import (
    calotowermaker as _calotowermaker,
)
process.towerMaker = _calotowermaker.clone(
    hbheInput=cms.InputTag("hbheprereco"),
    hoInput=cms.InputTag("emptyHcalRecHits"),
    hfInput=cms.InputTag("emptyHcalRecHits"),
    ecalInputs=cms.VInputTag(
        cms.InputTag("ecalRecHit", "EcalRecHitsEB"),
        cms.InputTag("ecalRecHit", "EcalRecHitsEE"),
    ),
)

# --- check the outcome
process.checker = cms.EDAnalyzer(
    "CaloLocalRecoChecker",
    ebRecHits=cms.InputTag("ecalRecHit", "EcalRecHitsEB"),
    hbheRecHits=cms.InputTag("hbheprereco"),
    towers=cms.InputTag("towerMaker"),
)

process.p = cms.Path(
    process.toyDigis
    * process.emptyHcalRecHits
    * process.ecalWeightUncalibRecHit
    * process.ecalRecHit
    * process.hbheprereco
    * process.towerMaker
    * process.checker
)
