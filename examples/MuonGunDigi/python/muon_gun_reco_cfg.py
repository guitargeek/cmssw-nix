# Local reconstruction on the digis the previous job made: strip digis ->
# clusters -> rec hits, and then the question that matters - are the rec hits
# where the muon actually went?
#
# This is the step that gives examples/MuonGunDigi a point. A digitiser that
# wrote plausible-looking ADC counts in the right modules would pass every
# assertion there and still be wrong about *where* in the module the charge
# landed. Only reconstructing the position and comparing it with the SimHit
# tests that, and it tests everything at once: the geometry, the drift and
# Lorentz deflection the digitiser applied, the charge sharing between
# neighbouring strips, the cluster charge weighting, and the CPE.
#
# The expected scale is the strip pitch, 80-120 um in the barrel; a one- or
# two-strip cluster localises to roughly pitch/sqrt(12), a few tens of microns.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first. The
# geometry has to be the same 2018 description the digis were made in - the
# DetIds and the module-local frames are only meaningful against it.
import os

import FWCore.ParameterSet.Config as cms

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

process = cms.Process("LOCALRECO")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1

process.source = cms.Source(
    "PoolSource",
    fileNames=cms.untracked.vstring("file:muon_gun_digi.root"),
)
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(-1))

# --- geometry: identical to the digitisation job -----------------------------
process.load("Configuration.Geometry.GeometryExtended2018_cff")
process.TrackerParametersESModule = cms.ESProducer("TrackerParametersESModule")
process.trackerTopology = cms.ESProducer("TrackerTopologyEP")
# New in 20_1: the tracker digi geometry depends on a per-det additional
# parameters record that did not exist in the 10_6 era.
if not _is_10_6:
    process.TrackerAdditionalParametersPerDetESModule = cms.ESProducer(
        "TrackerAdditionalParametersPerDetESModule"
    )
process.TrackerDigiGeometryESModule = cms.ESProducer(
    "TrackerDigiGeometryESModule",
    fromDDD=cms.bool(True),
    applyAlignment=cms.bool(False),
    alignmentsLabel=cms.string(""),
    appendToDataLabel=cms.string(""),
)

# The same field the digitiser used. The CPE corrects the cluster position for
# the Lorentz drift, so it has to see the field the drift was generated with,
# or the correction is applied against the wrong number and the residual moves.
process.load("MagneticField.Engine.volumeBasedMagneticField_160812_cfi")
# --- conditions ------------------------------------------------------------
# All fake (from-parameters) sources: there is no conditions database here,
# and the point of the example is the data flow, not the calibration values.
# The strip block is the one examples/TrackerLocalReco already uses, which is
# deliberate - the digis produced here have to be readable by that chain.
# SiStripDetInfoFileReader is a Service only in the 10_6 era. 20_1 replaced
# it with a plain class (CalibFormats/SiStripObjects' SiStripDetInfo, read
# through Geometry/TrackerNumberingBuilder/interface/utils.h), so asking
# the framework for the service there aborts with PluginNotFound.
if _is_10_6:
    process.SiStripDetInfoFileReader = cms.Service("SiStripDetInfoFileReader")

process.siStripFedCabling = cms.ESSource(
    "SiStripFedCablingFakeESSource",
    FedIdsFile=cms.FileInPath("CalibTracker/SiStripCommon/data/SiStripFedIdList.dat"),
    PopulateAllFeds=cms.bool(True),
)
process.SiStripConnectivity = cms.ESProducer("SiStripConnectivity")

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
# Written out rather than loaded from its cfi: the shipped
# SiStripPedestalsFakeESSource_cfi sets PedestalsValue, and
# SiStripPedestalsFakeESSource.cc reads PedestalValue. The cfi cannot
# configure its own ES source - loading it fails with
# "MissingParameter: Parameter 'PedestalValue' not found".
process.siStripPedestalsFakeESSource = cms.ESSource(
    "SiStripPedestalsFakeESSource",
    appendToDataLabel=cms.string(""),
    printDebug=cms.untracked.uint32(5),
    PedestalValue=cms.uint32(30),
)
process.load("CalibTracker.SiStripESProducers.fake.SiStripThresholdFakeESSource_cfi")
process.load("CalibTracker.SiStripESProducers.fake.SiStripApvGainFakeESSource_cfi")
process.load("CalibTracker.SiStripESProducers.fake.SiStripLatencyFakeESSource_cfi")
process.load("CalibTracker.SiStripESProducers.fake.SiStripBadChannelFakeESSource_cfi")

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




# The rec-hit position estimator needs three more things than the digitiser
# did. The Lorentz angle and back-plane correction are looked up through
# latency-dependent records, whose producers pick the payload labelled 'peak'
# or 'deconvolution' - supply both. And the CPE reads its strip cross-talk
# constants out of a SiStripConfObject.
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

# The reconstruction gain, from the same flat APV gains.
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

# Pixel conditions for reconstruction: flat gain and a flat Lorentz angle.
# The clusteriser fetches SiPixelGainCalibrationOfflineRcd even with
# MissCalibrate=False, and the CPE reads the (reconstruction) Lorentz
# angle to undo the drift the digitiser applied.
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeGainOfflineESSource_cfi")
# NOT the fake Lorentz angle source: it covers phase-0 DetIds only, so
# against this geometry it supplies nothing and the CPE applies no drift
# correction. Read the phase-1 payload written by
# python/write_sim_conditions_cfg.py instead.
process.load("CondCore.CondDB.CondDB_cfi")
process.CondDB.connect = cms.string("sqlite_file:sim_conditions.db")
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

# --- clusters ---------------------------------------------------------------
# The standard three-threshold algorithm, reading the digis the mixing module
# wrote. This is the line examples/TrackerLocalReco has pointing at a
# hand-built ToyTrackerDigiProducer instead.
# New in 20_1: the strip clusteriser takes its conditions from one bundled
# record instead of reaching for SiStripGain, SiStripNoises and
# SiStripQuality individually. Same as examples/TrackingChain.
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
        # QualityLabel in 10_6 named the SiStripQuality record to consult;
        # in 20_1 the clusteriser reads one bundled conditions record and
        # the label names that instead. Same as examples/TrackingChain.
        **({"QualityLabel": cms.string("")} if _is_10_6
           else {"ConditionsLabel": cms.string(""), "setDetId": cms.bool(True)}),
        RemoveApvShots=cms.bool(True),
        clusterChargeCut=cms.PSet(value=cms.double(-1.0)),
    ),
    DigiProducersList=cms.VInputTag(
        cms.InputTag("simSiStripDigis", "ZeroSuppressed"),
    ),
)

# --- pixel clusters and rec hits -------------------------------------------
# MissCalibrate=False means plain ADC * ElectronPerADCGain, so no gain
# calibration payload is involved; PixelCPEGeneric is the position
# estimator that does not need the template or GenError payloads, neither
# of which ships with the release.
process.siPixelClusters = cms.EDProducer(
    "SiPixelClusterProducer",
    src=cms.InputTag("simSiPixelDigis"),
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

# --- rec hits ---------------------------------------------------------------
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
    VerbosityLevel=cms.untracked.int32(0),
)

# The parameter set of the generic CPE changed between the releases -
# PixelErrorParametrization and useLAAlignmentOffsets are gone in 20_1 and
# passing them is a validation error - so there the producer is cloned from
# the fragment the release generates out of its own parameter description,
# and only the switches this example needs are overridden. Same treatment as
# examples/TrackingChain.
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
process.siPixelRecHits = cms.EDProducer(
    "SiPixelRecHitConverter",
    src=cms.InputTag("siPixelClusters"),
    CPE=cms.string("PixelCPEGeneric"),
)
# SiPixelRecHitConverter no longer accepts VerboseLevel in 20_1.
if _is_10_6:
    process.siPixelRecHits.VerboseLevel = cms.untracked.int32(0)

# --- the measurement --------------------------------------------------------
process.residuals = cms.EDAnalyzer(
    "RecHitResidual",
    # rphiRecHit is the single-sided measurement: local x is the coordinate the
    # strips actually measure.
    # both single-sided collections: TIB layers 1-2 and TOB layers 1-2 are
    # double-sided, and the stereo sensor of a double-sided module is a
    # separate DetId whose rec hits land in stereoRecHit. Reading only
    # rphiRecHit would leave every stereo SimHit permanently unmatched.
    stripRecHits=cms.VInputTag(
        cms.InputTag("siStripMatchedRecHits", "rphiRecHit"),
        cms.InputTag("siStripMatchedRecHits", "stereoRecHit"),
    ),
    stripSimHits=cms.VInputTag(
        cms.InputTag("g4SimHits", "TrackerHitsTIBLowTof"),
        cms.InputTag("g4SimHits", "TrackerHitsTOBLowTof"),
    ),
    # Beyond 500 um a rec hit in the same module is a different particle or a
    # noise cluster, not a mis-measurement of this hit.
    matchWindow=cms.double(0.05),
    # The number that matters. Strip pitch is 80-120 um in the barrel, so a
    # working chain lands well inside 100 um; a geometry or Lorentz-drift
    # mismatch would put it far outside.
    pixelRecHits=cms.VInputTag(cms.InputTag("siPixelRecHits")),
    pixelSimHits=cms.VInputTag(
        cms.InputTag("g4SimHits", "TrackerHitsPixelBarrelLowTof"),
    ),
    # Strips measure one coordinate: 80 um pitch in the TIB, so a one- or
    # two-strip cluster lands near pitch/sqrt(12). Measured: 19 um.
    maxStripMedianResidual=cms.double(0.005),
    # Pixels do better: charge sharing interpolates inside a 100 x 150 um
    # cell. Measured: 9 um. This bound is the one that matters - it is
    # tight enough to catch the Lorentz drift going uncorrected, which
    # put this at 51 um until the phase-1 payload was written (see
    # plugins/PixelLorentzAngleWriter.cc).
    maxPixelMedianResidual=cms.double(0.003),
    # every SimHit in the barrel strips is reconstructed in practice; the
    # margin is for the occasional low-energy secondary that leaves a hit too
    # small to cluster above threshold
    minEfficiency=cms.double(0.9),
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
    process.siStripClusters
    * process.siPixelClusters
    * process.siStripMatchedRecHits
    * process.siPixelRecHits
    * process.residuals
)
