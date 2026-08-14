# Tracker local reco validation: toy digis -> clusters -> rec hits, with the
# TrackerGeometry built from the tracker-only DDD XML geometry and all
# conditions coming from the fake (from-parameters) ES sources.
import FWCore.ParameterSet.Config as cms

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

process.TrackerGeometricDetESModule = cms.ESProducer(
    "TrackerGeometricDetESModule", fromDDD=cms.bool(True)
)
process.TrackerParametersESModule = cms.ESProducer("TrackerParametersESModule")
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
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeLorentzAngleESSource_cfi")

# --- the toy digis

# --- strip clusterizer (standard three-threshold algorithm)
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
        QualityLabel=cms.string(""),
        RemoveApvShots=cms.bool(True),
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
    VerboseLevel=cms.untracked.int32(0),
)

# --- check the outcome

# =====================================================================
# toy digis on helices + the pixel-track / primary-vertex chain
# =====================================================================
process.toyDigis = cms.EDProducer(
    "ToyTrackDigiProducer",
    bField=cms.double(3.8),
    tracks=cms.VPSet(
        cms.PSet(pt=cms.double(5.0), phi=cms.double(0.3), eta=cms.double(0.15), charge=cms.int32(1)),
        cms.PSet(pt=cms.double(8.0), phi=cms.double(1.8), eta=cms.double(-0.1), charge=cms.int32(-1)),
        cms.PSet(pt=cms.double(12.0), phi=cms.double(-2.4), eta=cms.double(0.25), charge=cms.int32(1)),
    ),
)

# beam spot: fixed fake conditions at the origin + the standard producer
# (the shipped fake-conditions cfi predates the plugin's parameter set)
process.BeamSpotFakeConditions = cms.ESSource(
    "BeamSpotFakeConditions",
    getDataFromFile=cms.bool(False),
    X0=cms.double(0.0), Y0=cms.double(0.0), Z0=cms.double(0.0),
    dxdz=cms.double(0.0), dydz=cms.double(0.0),
    sigmaZ=cms.double(3.8), widthX=cms.double(0.0015), widthY=cms.double(0.0015),
    emittanceX=cms.double(0.0), emittanceY=cms.double(0.0),
    betaStar=cms.double(0.0),
    errorX0=cms.double(0.0002), errorY0=cms.double(0.0002), errorZ0=cms.double(0.02),
    errorSigmaZ=cms.double(0.01), errordxdz=cms.double(0.0001),
    errordydz=cms.double(0.0001), errorWidth=cms.double(0.0002),
)
process.offlineBeamSpot = cms.EDProducer("BeamSpotProducer")

# GeometricSearchTracker for the seeding-layer machinery
process.load("RecoTracker.GeometryESProducer.TrackerRecoGeometryESProducer_cfi")

# transient rec-hit builders (full and the pixel-only one used in seeding)
process.load("RecoTracker.TransientTrackingRecHit.TransientTrackingRecHitBuilder_cfi")
process.load("RecoTracker.TkSeedingLayers.TTRHBuilderWithoutAngle4PixelTriplets_cfi")
process.load("TrackingTools.TransientTrack.TransientTrackBuilder_cfi")

# seeding layers: the standard 2016 pixel triplet combinations (the shipped
# cfi imports a scram-generated base, so the producer is declared directly)
process.PixelLayerTriplets = cms.EDProducer(
    "SeedingLayersEDProducer",
    layerList=cms.vstring(
        "BPix1+BPix2+BPix3",
        "BPix1+BPix2+FPix1_pos",
        "BPix1+BPix2+FPix1_neg",
        "BPix1+FPix1_pos+FPix2_pos",
        "BPix1+FPix1_neg+FPix2_neg",
    ),
    BPix=cms.PSet(
        TTRHBuilder=cms.string("WithTrackAngle"),
        HitProducer=cms.string("siPixelRecHits"),
    ),
    FPix=cms.PSet(
        TTRHBuilder=cms.string("WithTrackAngle"),
        HitProducer=cms.string("siPixelRecHits"),
    ),
    MTIB=cms.PSet(), MTID=cms.PSet(), MTEC=cms.PSet(), MTOB=cms.PSet(),
    TEC=cms.PSet(), TIB=cms.PSet(), TID=cms.PSet(), TOB=cms.PSet(),
)

# tracking region around the beam spot
from RecoTracker.TkTrackingRegions.GlobalTrackingRegionFromBeamSpot_cfi import (
    RegionPsetFomBeamSpotBlock as _regionBlock,
)
process.pixelTracksTrackingRegions = cms.EDProducer(
    "GlobalTrackingRegionFromBeamSpotEDProducer",
    RegionPSet=_regionBlock.RegionPSet.clone(),
)

# cluster multiplicity sanity check (off for the toy)
process.trackerClusterCheck = cms.EDProducer(
    "ClusterCheckerEDProducer",
    doClusterCheck=cms.bool(False),
    MaxNumberOfCosmicClusters=cms.uint32(400000),
    ClusterCollectionLabel=cms.InputTag("siStripClusters"),
    MaxNumberOfPixelClusters=cms.uint32(40000),
    PixelClusterCollectionLabel=cms.InputTag("siPixelClusters"),
    cut=cms.string(""),
    silentClusterCheck=cms.untracked.bool(True),
)

# hit doublets -> HLT-style pixel triplets
process.pixelTracksHitDoublets = cms.EDProducer(
    "HitPairEDProducer",
    seedingLayers=cms.InputTag("PixelLayerTriplets"),
    trackingRegions=cms.InputTag("pixelTracksTrackingRegions"),
    trackingRegionsSeedingLayers=cms.InputTag(""),
    clusterCheck=cms.InputTag("trackerClusterCheck"),
    produceSeedingHitSets=cms.bool(False),
    produceIntermediateHitDoublets=cms.bool(True),
    maxElement=cms.uint32(1000000),
    maxElementTotal=cms.uint32(50000000),
    layerPairs=cms.vuint32(0),
)
process.pixelTracksHitTriplets = cms.EDProducer(
    "PixelTripletHLTEDProducer",
    doublets=cms.InputTag("pixelTracksHitDoublets"),
    extraHitRPhitolerance=cms.double(0.06),
    extraHitRZtolerance=cms.double(0.06),
    useMultScattering=cms.bool(True),
    useBending=cms.bool(True),
    useFixedPreFiltering=cms.bool(False),
    phiPreFiltering=cms.double(0.3),
    maxElement=cms.uint32(1000000),
    produceSeedingHitSets=cms.bool(True),
    produceIntermediateHitTriplets=cms.bool(False),
    SeedComparitorPSet=cms.PSet(ComponentName=cms.string("none")),
)

# fit + filter + cleaner + the track producer
process.pixelFitterByHelixProjections = cms.EDProducer(
    "PixelFitterByHelixProjectionsProducer",
    scaleErrorsForBPix1=cms.bool(False),
    scaleFactor=cms.double(0.65),
)
process.pixelTrackFilterByKinematics = cms.EDProducer(
    "PixelTrackFilterByKinematicsProducer",
    ptMin=cms.double(0.9),
    nSigmaInvPtTolerance=cms.double(0.0),
    tipMax=cms.double(1.0),
    nSigmaTipMaxTolerance=cms.double(0.0),
    chi2=cms.double(1000.0),
)
process.pixelTrackCleanerBySharedHits = cms.ESProducer(
    "PixelTrackCleanerBySharedHitsESProducer",
    ComponentName=cms.string("pixelTrackCleanerBySharedHits"),
    useQuadrupletAlgo=cms.bool(False),
)
process.pixelTracks = cms.EDProducer(
    "PixelTrackProducer",
    passLabel=cms.string("pixelTracks"),
    SeedingHitSets=cms.InputTag("pixelTracksHitTriplets"),
    Fitter=cms.InputTag("pixelFitterByHelixProjections"),
    Filter=cms.InputTag("pixelTrackFilterByKinematics"),
    Cleaner=cms.string("pixelTrackCleanerBySharedHits"),
)

# primary vertices from the pixel tracks
from RecoVertex.PrimaryVertexProducer.OfflinePrimaryVertices_cfi import (
    offlinePrimaryVertices as _offlinePrimaryVertices,
)
process.pixelVertices = _offlinePrimaryVertices.clone(
    TrackLabel=cms.InputTag("pixelTracks"),
)
# pixel tracks have three layers by construction
process.pixelVertices.TkFilterParameters.minSiliconLayersWithHits = cms.int32(3)
process.pixelVertices.TkFilterParameters.maxD0Significance = cms.double(100.0)

process.checker = cms.EDAnalyzer(
    "TrackingChainChecker",
    tracks=cms.InputTag("pixelTracks"),
    vertices=cms.InputTag("pixelVertices"),
    minTracks=cms.uint32(3),
)

process.p = cms.Path(
    process.toyDigis
    * process.siStripClusters
    * process.siPixelClusters
    * process.siStripMatchedRecHits
    * process.siPixelRecHits
    * process.offlineBeamSpot
    * process.PixelLayerTriplets
    * process.pixelTracksTrackingRegions
    * process.trackerClusterCheck
    * process.pixelTracksHitDoublets
    * process.pixelTracksHitTriplets
    * process.pixelFitterByHelixProjections
    * process.pixelTrackFilterByKinematics
    * process.pixelTracks
    * process.pixelVertices
    * process.checker
)
process.GlobalTrackingGeometryESProducer = cms.ESProducer("GlobalTrackingGeometryESProducer")
