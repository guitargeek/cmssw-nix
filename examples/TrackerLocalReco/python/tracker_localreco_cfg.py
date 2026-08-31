# Tracker local reco validation: toy digis -> clusters -> rec hits, with the
# TrackerGeometry built from the tracker-only DDD XML geometry and all
# conditions coming from the fake (from-parameters) ES sources.
#
# Runs on both releases. 20_1 builds its geometry from DD4hep by default, but
# the classic DDD path is still there, so the toy runs off the very same 2016
# XML description; the ES modules just have to be told which of the two to
# read. Five further things differ, each commented where it appears:
#
#  * SiPixelFakeLorentzAngleESSource cannot be used in 20_1 at all. Its
#    fillDescriptions default is a FileInPath into SLHCUpgradeSimulations, a
#    data-only package not in this build, and edm::FileInPath resolves when
#    the *description* is built - during validation, whatever this
#    configuration sets. python/write_pixel_la_20_1_cfg.py writes the payload
#    instead, over the DetIds of the geometry actually loaded; run it first.
#  * The strip fake ES sources read the module list from a FileInPath of their
#    own instead of from the SiStripDetInfoFileReader service, which is gone.
#  * The strip clusteriser takes its conditions from one bundled
#    SiStripClusterizerConditionsRcd rather than reaching for SiStripGain,
#    SiStripNoises and SiStripQuality separately.
#  * The tracker digi geometry depends on a new per-det record,
#    PTrackerAdditionalParametersPerDetRcd.
#  * The generic pixel CPE dropped two parameters.
#
# An earlier note here recorded that building the TrackerGeometry from the DDD
# XML spun for over ten minutes in 20_1 against about a minute in 10_6. That is
# no longer true - the same 198 XML files build in under three seconds - and it
# was fixed by some other change to the build rather than by anything here.
import os

import FWCore.ParameterSet.Config as cms

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("LOCALRECO")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))

# --- geometry: the 2016 detector XML, filtered down to the world/envelope
# volumes (CMSCommonData) and the full tracker (TrackerCommonData). The
# calo/muon/forward subdetector files and the sim-only spec-pars are left
# out - subdetector files only position volumes into the envelopes, so
# dropping them leaves no dangling references.
from Geometry.CMSCommonData.cmsExtendedGeometry2016XML_cfi import (
    XMLIdealGeometryESSource as _xmlsrc,
)
process.XMLIdealGeometryESSource = _xmlsrc.clone()
process.XMLIdealGeometryESSource.geomXMLFiles = cms.vstring(
    [
        f
        for f in _xmlsrc.geomXMLFiles
        if f.startswith("Geometry/CMSCommonData/")
        or f.startswith("Geometry/TrackerCommonData/")
    ]
)

# The classic DDD geometry path is still there in 20_1, but the ES modules
# have to be told which of the two descriptions to read, and the digi geometry
# gained a dependency on a per-det additional-parameters record.
if _is_10_6:
    process.TrackerGeometricDetESModule = cms.ESProducer(
        "TrackerGeometricDetESModule", fromDDD=cms.bool(True)
    )
    process.TrackerParametersESModule = cms.ESProducer("TrackerParametersESModule")
else:
    process.TrackerGeometricDetESModule = cms.ESProducer(
        "TrackerGeometricDetESModule",
        fromDDD=cms.bool(True),
        fromDD4hep=cms.bool(False),
    )
    process.TrackerParametersESModule = cms.ESProducer(
        "TrackerParametersESModule", fromDD4hep=cms.bool(False)
    )
    process.TrackerAdditionalParametersPerDetESModule = cms.ESProducer(
        "TrackerAdditionalParametersPerDetESModule"
    )
process.trackerTopology = cms.ESProducer("TrackerTopologyEP")
process.TrackerDigiGeometryESModule = cms.ESProducer(
    "TrackerDigiGeometryESModule",
    fromDDD=cms.bool(True),
    applyAlignment=cms.bool(False),
    alignmentsLabel=cms.string(""),
    appendToDataLabel=cms.string(""),
)

# --- magnetic field: uniform 3.8 T
process.idealMagneticFieldRecordSource = cms.ESSource(
    "EmptyESSource",
    recordName=cms.string("IdealMagneticFieldRecord"),
    iovIsRunNotTime=cms.bool(True),
    firstValid=cms.vuint32(1),
)
process.UniformMagneticFieldESProducer = cms.ESProducer(
    "UniformMagneticFieldESProducer",
    ZFieldInTesla=cms.double(3.8),
    label=cms.untracked.string(""),
)

# --- fake strip conditions: noise (random mode, ~4 ADC), unit gain, no bad
# channels; Lorentz angle / back-plane correction / conf object for the CPE
#
# The two releases differ in where the fake sources get the module list from.
# In 10_6 it comes from the SiStripDetInfoFileReader *service*, and the
# parameters are spelled out here; in 20_1 that service no longer exists and
# each fake source reads a FileInPath of its own, so the shipped fragments are
# cloned and only the two values this example cares about are overridden.
if _is_10_6:
    process.siStripNoisesFakeESSource = cms.ESSource(
        "SiStripNoisesFakeESSource",
        appendToDataLabel=cms.string(""),
        printDebug=cms.untracked.uint32(5),
        StripLengthMode=cms.bool(False),
        NoiseStripLengthSlopeTIB=cms.vdouble(51.0, 51.0, 51.0, 51.0),
        NoiseStripLengthQuoteTIB=cms.vdouble(630.0, 630.0, 630.0, 630.0),
        NoiseStripLengthSlopeTID=cms.vdouble(51.0, 51.0, 51.0),
        NoiseStripLengthQuoteTID=cms.vdouble(630.0, 630.0, 630.0),
        NoiseStripLengthSlopeTOB=cms.vdouble(51.0, 51.0, 51.0, 51.0, 51.0, 51.0),
        NoiseStripLengthQuoteTOB=cms.vdouble(630.0, 630.0, 630.0, 630.0, 630.0, 630.0),
        NoiseStripLengthSlopeTEC=cms.vdouble(51.0, 51.0, 51.0, 51.0, 51.0, 51.0, 51.0),
        NoiseStripLengthQuoteTEC=cms.vdouble(630.0, 630.0, 630.0, 630.0, 630.0, 630.0, 630.0),
        electronPerAdc=cms.double(247.0),
        MeanNoiseTIB=cms.vdouble(4.0, 4.0, 4.0, 4.0),
        SigmaNoiseTIB=cms.vdouble(0.5, 0.5, 0.5, 0.5),
        MeanNoiseTID=cms.vdouble(4.0, 4.0, 4.0),
        SigmaNoiseTID=cms.vdouble(0.5, 0.5, 0.5),
        MeanNoiseTOB=cms.vdouble(4.0, 4.0, 4.0, 4.0, 4.0, 4.0),
        SigmaNoiseTOB=cms.vdouble(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        MeanNoiseTEC=cms.vdouble(4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0),
        SigmaNoiseTEC=cms.vdouble(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        MinPositiveNoise=cms.double(0.1),
    )
    process.SiStripDetInfoFileReader = cms.Service("SiStripDetInfoFileReader")
    # FED cabling + connectivity: the clusterizer resolves its input by det
    # cabling, so provide the fake full-detector cabling
    process.siStripFedCabling = cms.ESSource(
        "SiStripFedCablingFakeESSource",
        FedIdsFile=cms.FileInPath("CalibTracker/SiStripCommon/data/SiStripFedIdList.dat"),
        PopulateAllFeds=cms.bool(True),
    )
else:
    from CalibTracker.SiStripESProducers.fake.SiStripNoisesFakeESSource_cfi import (
        siStripNoisesFakeESSource as _noiseFake,
    )
    from CalibTracker.SiStripESProducers.fake.SiStripFedCablingFakeESSource_cfi import (
        siStripFedCabling as _cablingFake,
    )

    process.siStripNoisesFakeESSource = _noiseFake.clone(
        StripLengthMode=False, electronPerAdc=247.0
    )
    process.siStripFedCabling = _cablingFake.clone(PopulateAllFeds=True)
process.SiStripConnectivity = cms.ESProducer("SiStripConnectivity")
process.load("CalibTracker.SiStripESProducers.fake.SiStripApvGainFakeESSource_cfi")
# conf object with the cross-talk constants the strip CPE requires (one pair
# per module geometry and readout mode; representative values, this is a toy)
_xtalkParams = []
for _geom in ["IB1", "IB2", "OB1", "OB2", "W1A", "W2A", "W3A",
              "W1B", "W2B", "W3B", "W4", "W5", "W6", "W7"]:
    for _mode in ["Deco", "Peak"]:
        for _name, _value in [("xtalk1", 0.10), ("xtalk2", 0.03)]:
            _xtalkParams.append(
                cms.PSet(
                    ParameterName=cms.string("%s_%s%s" % (_name, _geom, _mode)),
                    ParameterType=cms.string("double"),
                    ParameterValue=cms.double(_value),
                )
            )
process.siStripConfObjectFakeESSource = cms.ESSource(
    "SiStripConfObjectFakeESSource",
    appendToDataLabel=cms.string(""),
    Parameters=cms.VPSet(*_xtalkParams),
)

# SiStripQuality via the real producer (not the fake source): the clusterizer
# requires the quality object to carry the det cabling
process.siStripQualityESProducer = cms.ESProducer(
    "SiStripQualityESProducer",
    appendToDataLabel=cms.string(""),
    ListOfRecordToMerge=cms.VPSet(
        cms.PSet(record=cms.string("SiStripDetCablingRcd"), tag=cms.string("")),
        cms.PSet(record=cms.string("SiStripBadChannelRcd"), tag=cms.string("")),
    ),
    ReduceGranularity=cms.bool(False),
    ThresholdForReducedGranularity=cms.double(0.3),
    PrintDebugOutput=cms.bool(False),
    UseEmptyRunInfo=cms.bool(False),
)
process.load("CalibTracker.SiStripESProducers.fake.SiStripLatencyFakeESSource_cfi")
process.load("CalibTracker.SiStripESProducers.fake.SiStripBadChannelFakeESSource_cfi")

# The strip CPE reads the latency-dependent Lorentz-angle / back-plane
# records, whose producers pick the payload labeled 'peak' or 'deconvolution'
# - provide both labels from the fake sources.
from CalibTracker.SiStripESProducers.fake.SiStripLorentzAngleFakeESSource_cfi import (
    siStripLorentzAngleFakeESSource as _laFake,
)
from CalibTracker.SiStripESProducers.fake.SiStripBackPlaneCorrectionFakeESSource_cfi import (
    siStripBackPlaneCorrectionFakeESSource as _bpFake,
)
process.siStripLorentzAnglePeak = _laFake.clone(appendToDataLabel="peak")
process.siStripLorentzAngleDeco = _laFake.clone(appendToDataLabel="deconvolution")
process.siStripBackPlaneCorrectionPeak = _bpFake.clone(appendToDataLabel="peak")
process.siStripBackPlaneCorrectionDeco = _bpFake.clone(appendToDataLabel="deconvolution")
process.load("CalibTracker.SiStripESProducers.SiStripLorentzAngleDepESProducer_cfi")
process.load("CalibTracker.SiStripESProducers.SiStripBackPlaneCorrectionDepESProducer_cfi")

# SiStripGain from the fake APV gains (only the plain SiStripApvGainRcd; the
# default cfi would also merge a second record we do not provide)
process.siStripGainESProducer = cms.ESProducer(
    "SiStripGainESProducer",
    appendToDataLabel=cms.string(""),
    printDebug=cms.untracked.bool(False),
    AutomaticNormalization=cms.bool(False),
    APVGain=cms.VPSet(
        cms.PSet(
            Record=cms.string("SiStripApvGainRcd"),
            Label=cms.untracked.string(""),
            NormalizationFactor=cms.untracked.double(1.0),
        )
    ),
)

# --- fake pixel conditions
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeGainOfflineESSource_cfi")
# In 20_1 the fake Lorentz angle source cannot be used at all: its
# fillDescriptions default is a FileInPath into SLHCUpgradeSimulations, a
# data-only package that is not in this build, and the FileInPath constructor
# runs when the *description* is built - during validation, whatever this
# configuration sets. The payload is written instead by
# python/write_pixel_la_20_1_cfg.py over the DetIds of the geometry actually
# loaded; run that first.
if _is_10_6:
    process.load("CalibTracker.SiPixelESProducers.SiPixelFakeLorentzAngleESSource_cfi")
else:
    process.load("CondCore.CondDB.CondDB_cfi")
    process.CondDB.connect = cms.string("sqlite_file:pixel_la.db")
    process.pixelConditions = cms.ESSource(
        "PoolDBESSource",
        process.CondDB,
        toGet=cms.VPSet(
            cms.PSet(
                record=cms.string("SiPixelLorentzAngleRcd"),
                tag=cms.string("SiPixelLorentzAngle_ideal"),
            ),
        ),
    )

# --- the toy digis
process.toyDigis = cms.EDProducer("ToyTrackerDigiProducer")

# --- strip clusterizer (standard three-threshold algorithm)
# New in 20_1: the strip clusteriser takes its conditions from one bundled
# record instead of reaching for SiStripGain, SiStripNoises and SiStripQuality
# individually.
if not _is_10_6:
    process.load(
        "RecoLocalTracker.SiStripClusterizer.SiStripClusterizerConditionsESProducer_cfi"
    )

process.siStripClusters = cms.EDProducer(
    "SiStripClusterizer",
    Clusterizer=cms.PSet(
        Algorithm=cms.string("ThreeThresholdAlgorithm"),
        ChannelThreshold=cms.double(2.0),
        SeedThreshold=cms.double(3.0),
        ClusterThreshold=cms.double(5.0),
        MaxSequentialHoles=cms.uint32(0),
        MaxSequentialBad=cms.uint32(1),
        MaxAdjacentBad=cms.uint32(0),
        RemoveApvShots=cms.bool(True),
        # QualityLabel in 10_6 named the SiStripQuality record to consult; in
        # 20_1 the clusteriser reads one bundled conditions record and the
        # label names that instead
        **({"QualityLabel": cms.string("")} if _is_10_6
           else {"ConditionsLabel": cms.string(""), "setDetId": cms.bool(True)}),
        clusterChargeCut=cms.PSet(value=cms.double(-1.0)),
    ),
    DigiProducersList=cms.VInputTag(cms.InputTag("toyDigis")),
)

# --- pixel clusterizer; MissCalibrate=False -> plain ADC * ElectronPerADCGain,
# no gain calibration payload involved
process.siPixelClusters = cms.EDProducer(
    "SiPixelClusterProducer",
    src=cms.InputTag("toyDigis"),
    ClusterMode=cms.string("PixelThresholdClusterizer"),
    maxNumberOfClusters=cms.int32(-1),
    payloadType=cms.string("Offline"),
    ChannelThreshold=cms.int32(1000),
    MissCalibrate=cms.bool(False),
    SplitClusters=cms.bool(False),
    VCaltoElectronGain=cms.int32(65),
    VCaltoElectronGain_L1=cms.int32(65),
    VCaltoElectronOffset=cms.int32(-414),
    VCaltoElectronOffset_L1=cms.int32(-414),
    SeedThreshold=cms.int32(1000),
    ClusterThreshold=cms.int32(4000),
    ClusterThreshold_L1=cms.int32(4000),
    ElectronPerADCGain=cms.double(135.0),
    Phase2Calibration=cms.bool(False),
    Phase2ReadoutMode=cms.int32(-1),
    Phase2DigiBaseline=cms.double(1200.0),
    Phase2KinkADC=cms.int32(8),
)

# --- strip rec hits
process.load("RecoLocalTracker.SiStripRecHitConverter.StripCPEfromTrackAngle_cfi")
process.load("RecoLocalTracker.SiStripRecHitConverter.SiStripRecHitMatcher_cfi")
process.siStripMatchedRecHits = cms.EDProducer(
    "SiStripRecHitConverter",
    ClusterProducer=cms.InputTag("siStripClusters"),
    StripCPE=cms.ESInputTag("StripCPEfromTrackAngleESProducer:StripCPEfromTrackAngle"),
    Matcher=cms.ESInputTag("SiStripRecHitMatcherESProducer:StandardMatcher"),
    siStripQualityLabel=cms.ESInputTag(""),
    useSiStripQuality=cms.bool(False),
    MaskBadAPVFibers=cms.bool(False),
    rphiRecHits=cms.string("rphiRecHit"),
    stereoRecHits=cms.string("stereoRecHit"),
    matchedRecHits=cms.string("matchedRecHit"),
    VerbosityLevel=cms.untracked.int32(1),
)

# --- pixel rec hits (generic CPE without template payloads)
# The parameter set of the generic CPE changed between the releases -
# PixelErrorParametrization and useLAAlignmentOffsets are gone in 20_1, and
# passing them is a validation error - so there the producer is cloned from
# the fragment the release generates out of its own parameter description and
# only the switches this example needs are overridden.
if not _is_10_6:
    from RecoLocalTracker.SiPixelRecHits._generic_default_cfi import _generic_default

    process.PixelCPEGenericESProducer = _generic_default.clone(
        ComponentName="PixelCPEGeneric",
        UseErrorsFromTemplates=False,
        LoadTemplatesFromDB=False,
        TruncatePixelCharge=False,
        useLAWidthFromDB=False,
        IrradiationBiasCorrection=False,
        DoCosmics=False,
        MagneticFieldRecord=cms.ESInputTag(""),
    )
else:
    process.PixelCPEGenericESProducer = cms.ESProducer(
        "PixelCPEGenericESProducer",
        ComponentName=cms.string("PixelCPEGeneric"),
        Alpha2Order=cms.bool(True),
        PixelErrorParametrization=cms.string("NOTcmsim"),
        eff_charge_cut_lowX=cms.double(0.0),
        eff_charge_cut_lowY=cms.double(0.0),
        eff_charge_cut_highX=cms.double(1.0),
        eff_charge_cut_highY=cms.double(1.0),
        size_cutX=cms.double(3.0),
        size_cutY=cms.double(3.0),
        EdgeClusterErrorX=cms.double(50.0),
        EdgeClusterErrorY=cms.double(85.0),
        inflate_errors=cms.bool(False),
        inflate_all_errors_no_trk_angle=cms.bool(False),
        UseErrorsFromTemplates=cms.bool(False),
        TruncatePixelCharge=cms.bool(False),
        IrradiationBiasCorrection=cms.bool(False),
        DoCosmics=cms.bool(False),
        LoadTemplatesFromDB=cms.bool(False),
        ClusterProbComputationFlag=cms.int32(0),
        useLAWidthFromDB=cms.bool(False),
        useLAAlignmentOffsets=cms.bool(False),
        MagneticFieldRecord=cms.ESInputTag(""),
    )
# SiPixelRecHitConverter no longer accepts VerboseLevel in 20_1.
process.siPixelRecHits = cms.EDProducer(
    "SiPixelRecHitConverter",
    src=cms.InputTag("siPixelClusters"),
    CPE=cms.string("PixelCPEGeneric"),
)
if _is_10_6:
    process.siPixelRecHits.VerboseLevel = cms.untracked.int32(0)

# --- check the outcome
process.checker = cms.EDAnalyzer(
    "TrackerLocalRecoChecker",
    stripClusters=cms.InputTag("siStripClusters"),
    pixelClusters=cms.InputTag("siPixelClusters"),
    stripHits=cms.InputTag("siStripMatchedRecHits", "rphiRecHit"),
    pixelHits=cms.InputTag("siPixelRecHits"),
)

process.p = cms.Path(
    process.toyDigis
    * process.siStripClusters
    * process.siPixelClusters
    * process.siStripMatchedRecHits
    * process.siPixelRecHits
    * process.checker
)
