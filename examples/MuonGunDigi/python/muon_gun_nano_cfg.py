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
# vertex the configuration below is python/muon_gun_tracks_cfg.py verbatim -
# every setting there has a comment saying why it is what it is, and none of
# them changes here.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import FWCore.ParameterSet.Config as cms

process = cms.Process("NANO")

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


# --- the muon system --------------------------------------------------------
# From here on this is python/muon_gun_muons_cfg.py, again verbatim: DT digis
# -> drift-time rec hits -> 4D segments -> seeds -> a standalone track fitted
# in the return yoke. Its geometry and beam spot are already set up above; the
# two ES modules it needs on top belong to the muon side of the reconstruction
# geometry - the layer geometry spanning tracker and chambers, and the rec-hit
# builder that turns muon segments into transient hits a fit can use.
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
from RecoLocalMuon.DTRecHit.dt1DRecHits_LinearDrift_cfi import dt1DRecHits as _dt1DRecHits

process.dt1DRecHits = _dt1DRecHits.clone(dtDigiLabel=cms.InputTag("simMuonDTDigis"))
process.dt1DRecHits.recAlgoConfig.tTrigMode = cms.string("DTTTrigSyncTOFCorr")
process.dt1DRecHits.recAlgoConfig.tTrigModeConfig.tTrig = cms.double(500.0)
process.dt1DRecHits.recAlgoConfig.tTrigModeConfig.tofCorrType = cms.int32(1)

from RecoLocalMuon.DTSegment.dt4DSegments_CombPatternReco4D_LinearDrift_cfi import (
    dt4DSegments as _dt4DSegments,
)

process.dt4DSegments = _dt4DSegments.clone(recHits1DLabel=cms.InputTag("dt1DRecHits"))
for _cfg in (
    process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.recAlgoConfig,
    process.dt4DSegments.Reco4DAlgoConfig.recAlgoConfig,
):
    _cfg.tTrigMode = cms.string("DTTTrigSyncTOFCorr")
    _cfg.tTrigModeConfig.tTrig = cms.double(500.0)
    _cfg.tTrigModeConfig.tofCorrType = cms.int32(1)

# perform_delta_rejecting is required by DTSegmentUpdator and absent from
# this cfi. It belongs to the pattern-recognition algo config, not to the
# rec-hit algo config inside it. The LinearDriftFromDB variant of the same
# algorithm sets it True and the cosmic-data ones False; True is right here,
# because rejectBadHits drops hits inconsistent with the segment fit and a
# simulated collision muon really does make delta rays along its path.
# examples/MuonChain sets False - its toy digis have none.
process.dt4DSegments.Reco4DAlgoConfig.perform_delta_rejecting = cms.bool(True)
process.dt4DSegments.Reco4DAlgoConfig.Reco2DAlgoConfig.perform_delta_rejecting = (
    cms.bool(True)
)

# --- seeds and the standalone fit -------------------------------------------
# DT only: the gun fires into the barrel, so there are no CSC hits, and the RPC
# digitiser is packaged but not run here.
from RecoMuon.MuonSeedGenerator.ancientMuonSeed_cfi import ancientMuonSeed as _ancientMuonSeed

process.ancientMuonSeed = _ancientMuonSeed.clone(
    EnableCSCMeasurement=cms.bool(False),
    EnableRPCMeasurement=cms.bool(False),
)

process.load("RecoMuon.StandAloneMuonProducer.standAloneMuons_cff")
for _pset in (
    process.standAloneMuons.STATrajBuilderParameters.FilterParameters,
    process.standAloneMuons.STATrajBuilderParameters.BWFilterParameters,
):
    _pset.EnableCSCMeasurement = cms.bool(False)
    _pset.EnableRPCMeasurement = cms.bool(False)


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
