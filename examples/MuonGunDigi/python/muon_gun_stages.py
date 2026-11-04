# The reconstruction stages the three MuonGunDigi jobs share.
# muon_gun_tracks_cfg.py (tracker fit), muon_gun_muons_cfg.py (standalone
# muon fit) and muon_gun_nano_cfg.py (global fit + NanoAOD) run the same
# rec-hit -> tracking -> vertexing chain; the nano job is the other two in
# one process because the global fit needs both outputs in the same event.
import FWCore.ParameterSet.Config as cms


def add_tracking_reco(process, _is_10_6):
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
    )
    # 20_1 renamed this parameter: siPixelQualityLabel -> siPixelQualityFromDbLabel.
    # Same meaning - the label of the SiPixelQualityFromDbRcd tag a global tag
    # would normally supply - and empty is right either way here.
    if _is_10_6:
        process.siPixelQualityESProducer.siPixelQualityLabel = cms.string("")
    else:
        process.siPixelQualityESProducer.siPixelQualityFromDbLabel = cms.string("")
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

    # 20_1 only: SiPixelQualityESProducer consumes SiPixelDetVOffRcd
    # whether or not its ListOfRecordToMerge asks for it, and nothing in this
    # build produces that record - see plugins/PixelDetVOffWriter.cc, which
    # writes an empty one. Gated because the tag is only in the sqlite file
    # when that writer ran, which is also only on 20_1.
    if not _is_10_6:
        process.pixelConditions.toGet.append(
            cms.PSet(
                record=cms.string("SiPixelDetVOffRcd"),
                tag=cms.string("SiPixelDetVOff_empty"),
            )
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
    # New in 20_1: the hit-pair generator asks for the multiple-scattering
    # parametrisation through an EventSetup record of its own.
    if not _is_10_6:
        process.load(
            "RecoTracker.TkMSParametrization."
            "multipleScatteringParametrisationMakerESProducer_cfi"
        )

    process.trackerClusterCheck = cms.EDProducer(
        "ClusterCheckerEDProducer",
        doClusterCheck=cms.bool(False),
        # MaxNumberOfCosmicClusters was renamed MaxNumberOfStripClusters in 20_1
        **({"MaxNumberOfCosmicClusters": cms.uint32(400000)} if _is_10_6
           else {"MaxNumberOfStripClusters": cms.uint32(400000)}),
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
    # useLAAlignmentOffsets does not exist in 20_1 - see the CPE block above.
    if _is_10_6:
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

def add_muon_reco(process, _is_10_6):
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

def add_detinfo_fixups(process, _is_10_6):
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


def add_l1_muon_emulation(process):
    """The Run 3 barrel muon trigger on the simulated DT digis, up to the
    uGMT: python/muon_gun_l1_cfg.py measures it, python/muon_gun_hlt_cfg.py
    builds the HLT on it. Returns the emulation as a sequence."""
    # TwinMux maps RPC hits onto DT sectors through the RPC geometry
    process.load("Geometry.RPCGeometryBuilder.rpcGeometry_cfi")

    # --- DT trigger primitives ----------------------------------------------------
    # The chamber trigger electronics, configured from python: BTI, TRACO and
    # sector collector settings, and the TRACO lookup tables computed from the
    # geometry rather than read from the database.
    process.load("L1TriggerConfig.DTTPGConfigProducers.L1DTTPGConfig_cff")
    from L1Trigger.DTTrigger.dtTriggerPrimitiveDigis_cfi import dtTriggerPrimitiveDigis
    process.simDtTriggerPrimitiveDigis = dtTriggerPrimitiveDigis.clone(digiTag="simMuonDTDigis")

    # --- TwinMux ------------------------------------------------------------------
    # No RPC digis are simulated here (plugins/EmptyL1MuonInputs.cc), so TwinMux
    # passes the DT primitives through.
    process.load("L1Trigger.L1TTwinMux.fakeTwinMuxParams_cff")
    process.simMuonRPCDigis = cms.EDProducer("EmptyRPCDigiProducer")
    from L1Trigger.L1TTwinMux.simTwinMuxDigis_cfi import simTwinMuxDigis
    process.simTwinMuxDigis = simTwinMuxDigis.clone()

    # --- the barrel track finder ----------------------------------------------------
    # The stub producer reads the BMTF masks; the Kalman filter's own constants
    # are in its configuration and a lookup table file.
    process.load("L1Trigger.L1TMuonBarrel.fakeBmtfParams_cff")
    from L1Trigger.L1TMuonBarrel.simKBmtfStubs_cfi import simKBmtfStubs
    from L1Trigger.L1TMuonBarrel.simKBmtfDigis_cfi import simKBmtfDigis
    process.simKBmtfStubs = simKBmtfStubs.clone()
    process.simKBmtfDigis = simKBmtfDigis.clone()

    # --- the global muon trigger ----------------------------------------------------
    # The overlap and endcap track finders and the calorimeter tower sums get
    # empty inputs: the gun fires into the barrel (plugins/EmptyL1MuonInputs.cc).
    # The uGMT cfi also defines a conditions source reading its prototype
    # parameters from Frontier; only the producer is taken from it.
    process.load("L1Trigger.L1TMuon.fakeGmtParams_cff")
    process.emptyOverlapTF = cms.EDProducer("EmptyRegionalMuonCandProducer")
    process.emptyEndcapTF = cms.EDProducer("EmptyRegionalMuonCandProducer")
    process.emptyCaloTowers = cms.EDProducer("EmptyMuonCaloSumProducer")
    from L1Trigger.L1TMuon.simGmtStage2Digis_cfi import simGmtStage2Digis
    process.simGmtStage2Digis = simGmtStage2Digis.clone(
        overlapTFInput=cms.InputTag("emptyOverlapTF"),
        forwardTFInput=cms.InputTag("emptyEndcapTF"),
        triggerTowerInput=cms.InputTag("emptyCaloTowers"),
    )

    return cms.Sequence(
        process.simMuonRPCDigis
        * process.simDtTriggerPrimitiveDigis
        * process.simTwinMuxDigis
        * process.simKBmtfStubs
        * process.simKBmtfDigis
        * process.emptyOverlapTF
        * process.emptyEndcapTF
        * process.emptyCaloTowers
        * process.simGmtStage2Digis
    )
