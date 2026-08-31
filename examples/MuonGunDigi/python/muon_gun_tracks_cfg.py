# Tracking: rec hits -> pixel triplet seeds -> CKF pattern recognition ->
# Kalman-fitted tracks, and then the measurement that closes the chain -
# how well does the fitted momentum agree with the muon the gun fired?
#
# Everything before this validates positions. A residual of 9 um says the hit
# is in the right place; it says nothing about whether the reconstruction can
# assemble hits across nine layers into a trajectory, or whether the magnetic
# field that bent the muon during simulation is the one the fit uses to
# measure its momentum. The gun fires at a known pt, so the fitted pt is a
# number with a right answer, and it is the only number here that tests the
# field quantitatively.
#
# The chain is the standard one, and identical to examples/TrackingChain
# except that its rec hits come from a real simulation rather than from a
# hand-written ToyTrackerDigiProducer: pixel triplets seed proto-tracks, those
# become trajectory seeds, the CKF extends them through the strip detector,
# and ctfWithMaterialTracks does the final Kalman fit with material effects.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import FWCore.ParameterSet.Config as cms

process = cms.Process("TRACKS")

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
# The MeasurementTracker wants SiPixelQualityRcd as well. The fake source
# is phase-0 like the rest of them, so it marks nothing bad for the
# phase-1 modules in this job - which is exactly what is wanted here, and
# harmless in a way the Lorentz angle was not.
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeQualityESSource_cfi")
process.siPixelQualityESProducer = cms.ESProducer(
    "SiPixelQualityESProducer",
    ListOfRecordToMerge=cms.VPSet(
        cms.PSet(record=cms.string("SiPixelQualityFromDbRcd"), tag=cms.string("")),
    ),
    siPixelQualityLabel=cms.string(""),
)
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
        cms.PSet(
            # the MeasurementTracker fetches this too, so the empty map
            # written by plugins/PixelCablingMapWriter.cc is needed here as
            # well as in the digitisation job
            record=cms.string("SiPixelFedCablingMapRcd"),
            tag=cms.string("SiPixelFedCablingMap_empty"),
        ),
    ),
)

# --- clusters ---------------------------------------------------------------
# The standard three-threshold algorithm, reading the digis the mixing module
# wrote. This is the line examples/TrackerLocalReco has pointing at a
# hand-built ToyTrackerDigiProducer instead.
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

# Beam spot: the same one the simulation smeared its vertices over.
#
# This has to match, and not approximately. The primary-vertex producer
# cuts tracks on their impact-parameter significance with respect to the
# beam spot, and the 2018 beam spot sits 417 um off the origin in y. Track
# d0 errors here are tens of microns, so a beam spot at (0,0,0) makes every
# track look wildly displaced and the vertex producer throws them all away.
# The values are Realistic25ns13TeVEarly2018CollisionVtxSmearingParameters
# from IOMC/EventVertexGenerators, which is what the digitisation job used;
# the transverse width is sqrt(emittance * betaStar) = 7 um.
#
# The shipped fake-conditions cfi predates the plugin's parameter set, so
# the ESSource is written out longhand (as examples/TrackingChain does).
process.BeamSpotFakeConditions = cms.ESSource(
    "BeamSpotFakeConditions",
    getDataFromFile=cms.bool(False),
    X0=cms.double(0.0107682), Y0=cms.double(0.041722), Z0=cms.double(0.035748),
    dxdz=cms.double(0.0), dydz=cms.double(0.0),
    sigmaZ=cms.double(3.5), widthX=cms.double(0.0007), widthY=cms.double(0.0007),
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

process.GlobalTrackingGeometryESProducer = cms.ESProducer("GlobalTrackingGeometryESProducer")

# --- CKF: seeds from the pixel tracks, pattern recognition through the strip
# detector, then the final Kalman fit with material effects ------------------
process.load("RecoTracker.TkSeedGenerator.SeedGeneratorFromProtoTracksEDProducer_cff")
process.pixelTrackSeeds = process.SeedGeneratorFromProtoTracksEDProducer.clone(
    InputCollection=cms.InputTag("pixelTracks"),
)

process.load("RecoTracker.MeasurementDet.MeasurementTrackerESProducer_cff")
process.load("RecoTracker.MeasurementDet.MeasurementTrackerEventProducer_cfi")

# The Kalman fitter reaches the muon system: GlobalDetLayerGeometry spans
# tracker and muon layers, so MuonRecoGeometryRecord has to exist even for
# a tracker-only fit. The 2018 geometry already carries the muon XML; these
# are the ES producers that turn it into layers.
process.load("Geometry.MuonNumbering.muonNumberingInitialization_cfi")
process.load("Geometry.DTGeometryBuilder.dtGeometry_cfi")
process.DTGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.CSCGeometryBuilder.cscGeometry_cfi")
process.CSCGeometryESModule.applyAlignment = cms.bool(False)
process.load("Geometry.RPCGeometryBuilder.rpcGeometry_cfi")
process.load("RecoMuon.DetLayers.muonDetLayerGeometry_cfi")

# MeasurementTrackerESProducer_cff reloads the standard pixel CPE, which
# undoes the settings this job needs - including reading Lorentz-angle
# widths and alignment offsets from payloads that do not exist here. Put
# them back, after the load rather than before it.
process.PixelCPEGenericESProducer.UseErrorsFromTemplates = cms.bool(False)
process.PixelCPEGenericESProducer.TruncatePixelCharge = cms.bool(False)
process.PixelCPEGenericESProducer.IrradiationBiasCorrection = cms.bool(False)
process.PixelCPEGenericESProducer.DoCosmics = cms.bool(False)
process.PixelCPEGenericESProducer.LoadTemplatesFromDB = cms.bool(False)
process.PixelCPEGenericESProducer.useLAWidthFromDB = cms.bool(False)
process.PixelCPEGenericESProducer.useLAAlignmentOffsets = cms.bool(False)

process.load("RecoTracker.TkNavigation.NavigationSchoolESProducer_cfi")
process.load("TrackingTools.KalmanUpdators.KFUpdatorESProducer_cfi")
process.load("TrackingTools.KalmanUpdators.Chi2MeasurementEstimator_cfi")
process.load("TrackingTools.MaterialEffects.MaterialPropagator_cfi")
process.load("TrackingTools.MaterialEffects.OppositeMaterialPropagator_cfi")
process.load("TrackingTools.TrackFitters.TrackFitters_cff")
process.load("TrackingTools.GeomPropagators.AnalyticalPropagator_cfi")

process.load("RecoTracker.CkfPattern.CkfTrackCandidates_cff")
process.ckfTrackCandidates.src = cms.InputTag("pixelTrackSeeds")

process.load("RecoTracker.TrackProducer.CTFFinalFitWithMaterial_cff")
process.generalTracks = process.ctfWithMaterialTracks.clone(
    src=cms.InputTag("ckfTrackCandidates"),
)
# No pixel template payloads without a conditions database, so the generic
# CPE is used in the fit as well as in the rec-hit producer.
process.generalTracks.TTRHBuilder = cms.string("WithTrackAngle")
process.TTRHBuilderAngleAndTemplate.PixelCPE = cms.string("PixelCPEGeneric")

# --- primary vertex ---------------------------------------------------------
# The standard producer, fitting the reconstructed tracks back to a common
# origin. minSiliconLayersWithHits is left at its default: these tracks
# cross the whole tracker, so they easily pass it.
from RecoVertex.PrimaryVertexProducer.OfflinePrimaryVertices_cfi import (
    offlinePrimaryVertices as _offlinePrimaryVertices,
)

process.offlinePrimaryVertices = _offlinePrimaryVertices.clone(

    TkFilterParameters=_offlinePrimaryVertices.TkFilterParameters.clone(
        minSiliconLayersWithHits=cms.int32(0),
        minPixelLayersWithHits=cms.int32(0),
        maxD0Significance=cms.double(1e9),
        maxNormalizedChi2=cms.double(1e9),
    ),
    TrackLabel=cms.InputTag("generalTracks"),
)

# --- the measurement --------------------------------------------------------
process.tracks = cms.EDAnalyzer(
    "TrackResolution",
    tracks=cms.InputTag("generalTracks"),
    # the SimTracks carry what Geant4 was handed; genpartIndex() >= 0 picks the
    # generator muons out from the secondaries the shower produced
    simTracks=cms.InputTag("g4SimHits"),
    minPt=cms.double(1.0),
    # the gun fires two muons per event into opposite hemispheres, so a
    # generous cone still cannot match the wrong one
    maxDeltaR=cms.double(0.1),
    # Measured: 0.69%, which is what CMS achieves for muons of this
    # momentum. The bound is 2%: loose enough for ten muons of
    # statistics, tight enough that a magnetic field disagreeing with the
    # one used in simulation cannot pass - which is the whole reason to
    # measure momentum rather than position.
    maxMedianPtResolution=cms.double(0.02),
    minEfficiency=cms.double(0.8),
    # 0.8% momentum resolution leaves no ambiguity in the sign of the
    # curvature, so every charge must be right
    minChargeAgreement=cms.double(1.0),
    # A tracker fit that describes its own hits. Measured: 1.0.
    maxMedianChi2=cms.double(2.0),
)

process.vertex = cms.EDAnalyzer(
    "VertexResolution",
    vertices=cms.InputTag("offlinePrimaryVertices"),
    # the gun's production vertex: the SimVertex with no parent track
    simVertices=cms.InputTag("g4SimHits"),
    # Measured: 8.8 um transverse, 11.5 um along the beam, from four tracks.
    # The bounds keep an order of magnitude of headroom, which five events
    # of statistics warrants, and still catch a vertex that has run away
    # from the production point.
    maxMedianTransverse=cms.double(0.01),
    maxMedianLongitudinal=cms.double(0.02),
    minEfficiency=cms.double(0.8),
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
    * process.tracks
    * process.vertex
)
