# SIM + DIGI: fire muons into the 2018 detector, transport them with Geant4,
# then digitise the hits the way the readout electronics would.
#
# examples/MuonGunSim stops at the PSimHits - the energy Geant4 deposited in
# each sensitive volume. That is not what the detector produces. A silicon
# module produces ADC counts on numbered channels, after charge drift, Lorentz
# deflection, cross-talk, amplifier noise and zero suppression. Turning the
# one into the other is the DIGI step, and it is what makes simulated data
# readable by the same reconstruction that runs on real data - see
# examples/TrackerLocalReco, which does the next step from hand-built digis.
#
# The digitisers do not run as ordinary producers. They are accumulators owned
# by SimGeneral/MixingModule, because in a real job the same code has to see
# the signal event and the pileup events together. There is no pileup here, so
# `mix` runs with a single bunch crossing and no secondary source, but the
# step still goes through it.
#
# Needs the 10_6 dev shell (`nix develop .#cmssw_10_6_30`).
import FWCore.ParameterSet.Config as cms

process = cms.Process("SIMDIGI")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.MessageLogger.cerr.FwkReport.reportEvery = 1

process.source = cms.Source("EmptySource")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(5))

# --- geometry ---------------------------------------------------------------
# The full 2018 description, as the simulation needs it, plus the tracker
# *digi* geometry: the digitisers work in module-local coordinates and need
# the PixelGeomDetUnit / StripGeomDetUnit topologies, which the sim geometry
# alone does not build.
#
# applyAlignment=False is what keeps this cheap. The standard
# GeometryExtended2018Reco_cff pulls the alignment record producers out of
# Alignment/CommonAlignmentProducer, and that subsystem costs fifteen further
# packages (including Fireworks/Core) for records that are the identity here.
process.load("Configuration.Geometry.GeometryExtended2018_cff")
process.TrackerDigiGeometryESModule = cms.ESProducer(
    "TrackerDigiGeometryESModule",
    fromDDD=cms.bool(True),
    applyAlignment=cms.bool(False),
    alignmentsLabel=cms.string(""),
    appendToDataLabel=cms.string(""),
)
# TrackerTopologyEP builds the topology from PTrackerParametersRcd, which the
# sim geometry cff does not provide - only the reco one does, and that is the
# cff whose alignment dependency we are avoiding.
process.TrackerParametersESModule = cms.ESProducer("TrackerParametersESModule")
process.trackerTopology = cms.ESProducer("TrackerTopologyEP")

# A second TrackerGeometry, labelled idealForDigi. The digitisers ask for
# it by that label on purpose: digitisation must use the geometry the
# simulation was done in, not one that has had alignment corrections
# applied, or the strip positions move under the hits. With
# applyAlignment=False the two are the same object here, but the label
# still has to exist. Geometry/TrackerGeometryBuilder/
# idealForDigiTrackerGeometry_cff builds it from a fake alignment
# producer in Alignment/CommonAlignmentProducer and then switches
# alignment off anyway, so the import is avoidable.
process.idealForDigiTrackerGeometry = cms.ESProducer(
    "TrackerDigiGeometryESModule",
    fromDDD=cms.bool(True),
    applyAlignment=cms.bool(False),
    alignmentsLabel=cms.string(""),
    appendToDataLabel=cms.string("idealForDigi"),
)

process.load("MagneticField.Engine.volumeBasedMagneticField_160812_cfi")
process.load("SimGeneral.HepPDTESSource.pythiapdt_cfi")

# --- random numbers ---------------------------------------------------------
# `mix` needs an entry of its own: the digitisers draw their noise through the
# service under the label of the module that owns them, not their own names.
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
    mix=cms.PSet(
        initialSeed=cms.untracked.uint32(12345),
        engineName=cms.untracked.string("HepJamesRandom"),
    ),
)

# --- generation and simulation ---------------------------------------------
# Identical to examples/MuonGunSim; see that config for why the module is
# renamed to generatorSmeared and why the forward shower libraries are off.
process.generator = cms.EDProducer(
    "FlatRandomPtGunProducer",
    PGunParameters=cms.PSet(
        # Four muons, in four independent random directions, rather than
        # one back-to-back pair. This is for the vertex: two collinear
        # tracks are a straight line through their production point, so
        # its position along that line is degenerate and the transverse
        # fit runs away - the unconstrained fit lands centimetres off the
        # beam and gets rejected by maxDistanceToBeam. Four independent
        # directions constrain it properly. examples/MuonGunSim keeps the
        # back-to-back pair, which is all it needs.
        PartID=cms.vint32(13, -13, 13, -13),
        MinPt=cms.double(10.0),
        MaxPt=cms.double(50.0),
        MinEta=cms.double(-0.8),
        MaxEta=cms.double(0.8),
        MinPhi=cms.double(-3.14159265359),
        MaxPhi=cms.double(3.14159265359),
    ),
    AddAntiParticle=cms.bool(False),
    Verbosity=cms.untracked.int32(0),
    firstRun=cms.untracked.uint32(1),
    psethack=cms.string("single mu pt 10-50"),
)

process.load("IOMC.EventVertexGenerators.VtxSmearedRealistic25ns13TeVEarly2018Collision_cfi")
process.generatorSmeared = process.VtxSmeared.clone()
del process.VtxSmeared

process.load("SimG4Core.Application.g4SimHits_cfi")
_present = cms.FileInPath("SimG4CMS/Calo/data/responsTBpim50.dat")
process.g4SimHits.HCalSD.UseShowerLibrary = cms.bool(False)
process.g4SimHits.HFShowerLibrary.FileName = _present
process.g4SimHits.CastorSD.useShowerLibrary = cms.bool(False)
process.g4SimHits.CastorShowerLibrary.FileName = _present

# --- conditions the digitisers read ----------------------------------------
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

# The simulated Lorentz angle comes from the sqlite file written by
# python/write_sim_conditions_cfg.py - run that first. No fake ES source
# serves SiStripLorentzAngleSimRcd (they all serve the reconstruction
# record instead), and in production it comes from the global tag, so a
# small local conditions database is the honest stand-in.
process.load("CondCore.CondDB.CondDB_cfi")
process.CondDB.connect = cms.string("sqlite_file:sim_conditions.db")
process.simConditions = cms.ESSource(
    "PoolDBESSource",
    process.CondDB,
    toGet=cms.VPSet(
        cms.PSet(
            record=cms.string("SiStripLorentzAngleSimRcd"),
            tag=cms.string("SiStripLorentzAngleSim_ideal"),
        ),
        cms.PSet(
            record=cms.string("SiStripApvGainSimRcd"),
            tag=cms.string("SiStripApvGainSim_ideal"),
        ),
        cms.PSet(
            record=cms.string("SiPixelFedCablingMapRcd"),
            tag=cms.string("SiPixelFedCablingMap_empty"),
        ),
    ),
)

# The simulated gain, read from the same sqlite file. Its producer is left
# at its default record (SiStripApvGainSimRcd) because SiStripGainSimRcd
# depends on that record, so an IOV for it has to exist regardless of
# where the producer is told to look.
from CalibTracker.SiStripESProducers.SiStripGainSimESProducer_cfi import (
    siStripGainSimESProducer as _simGain,
)
process.siStripGainSimESProducer = _simGain.clone()

# Pixel: flat gain, flat Lorentz angle, and a quality payload with nothing
# marked bad. The fake source delivers SiPixelQualityFromDbRcd; the
# digitiser asks for SiPixelQualityRcd, which this producer merges - only
# the one record is listed, since SiPixelDetVOffRcd (the HV-off map) has no
# fake source here.
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeGainOfflineESSource_cfi")
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeLorentzAngleESSource_cfi")
process.load("CalibTracker.SiPixelESProducers.SiPixelFakeQualityESSource_cfi")
process.siPixelQualityESProducer = cms.ESProducer(
    "SiPixelQualityESProducer",
    ListOfRecordToMerge=cms.VPSet(
        cms.PSet(record=cms.string("SiPixelQualityFromDbRcd"), tag=cms.string("")),
    ),
    siPixelQualityLabel=cms.string(""),
)

# --- the mixing module and the digitisers it owns --------------------------
from SimGeneral.MixingModule.mixObjects_cfi import theMixObjects
from SimGeneral.MixingModule.pixelDigitizer_cfi import pixelDigitizer
from SimGeneral.MixingModule.stripDigitizer_cfi import stripDigitizer

# No conditions database, so the features that read one are off: the dynamic
# inefficiency map and the list of bad FED channels are both payloads we have
# no fake source for, and neither changes what this example demonstrates.
# The APV saturation probabilities are a heavy-ion thing:
# SiStripDigitizerAlgorithm opens the file only when APVSaturationFromHIP
# is set, and it is off by default. But APVProbaList.txt is not in the
# release - it is one of the separately distributed data files - and
# edm::FileInPath resolves when the configuration is translated, before
# any module exists, so an unresolvable path aborts the job whether or
# not anything would read it. Point it at a file that does ship.
stripDigitizer.APVProbabilityFile = cms.FileInPath(
    "SimTracker/SiStripDigitizer/data/APVShapeDeco_default.txt"
)

# The pixel digitiser, with everything that needs a conditions database
# switched off. AddPixelInefficiency wants a dynamic-inefficiency map and
# KillBadFEDChannels a list of bad FED channels; neither has a fake source.
# LorentzAngle_DB is off because nothing in the release produces
# SiPixelLorentzAngleSimRcd - only the record class exists - and the
# digitiser carries a configured fallback for exactly that case
# (TanLorentzAnglePerTesla_BPix/FPix = 0.106). SiPixelSimParameters_cfi
# even ships `#digitizer.LorentzAngle_DB = False` as a comment.
pixelDigitizer.AddPixelInefficiency = cms.bool(False)
pixelDigitizer.KillBadFEDChannels = cms.bool(False)
pixelDigitizer.LorentzAngle_DB = cms.bool(False)

process.mix = cms.EDProducer(
    "MixingModule",
    digitizers=cms.PSet(
        pixel=cms.PSet(pixelDigitizer),
        strip=cms.PSet(stripDigitizer),
    ),
    LabelPlayback=cms.string(""),
    # a single bunch crossing: no pileup to mix in
    minBunch=cms.int32(0),
    maxBunch=cms.int32(0),
    bunchspace=cms.int32(25),
    mixProdStep1=cms.bool(False),
    mixProdStep2=cms.bool(False),
    playback=cms.untracked.bool(False),
    useCurrentProcessOnly=cms.bool(False),
    mixObjects=cms.PSet(theMixObjects),
)

# The digis come out of `mix` and are given their familiar names by the same
# aliases the standard configuration uses, so that anything downstream sees
# exactly what it would see in a production job.
from SimGeneral.MixingModule.aliases_cfi import simSiPixelDigis, simSiStripDigis

process.simSiPixelDigis = simSiPixelDigis

process.simSiStripDigis = simSiStripDigis

# --- what has to be there afterwards ---------------------------------------
process.digis = cms.EDAnalyzer(
    "DigiCounter",
    pixelDigis=cms.InputTag("simSiPixelDigis"),
    # the instance name matters: the mixing module writes the zero-suppressed
    # digis - the ones the detector actually reads out - alongside several
    # raw-digi flavours, and the EDAlias keeps mix's instance names
    stripDigis=cms.InputTag("simSiStripDigis", "ZeroSuppressed"),
    pixelSimHits=cms.VInputTag(
        cms.InputTag("g4SimHits", "TrackerHitsPixelBarrelLowTof"),
    ),
    stripSimHits=cms.VInputTag(
        cms.InputTag("g4SimHits", "TrackerHitsTIBLowTof"),
        cms.InputTag("g4SimHits", "TrackerHitsTOBLowTof"),
    ),
    # A muon crossing a silicon sensor deposits far more than any threshold,
    # so essentially every hit module should digitise. The margin is for the
    # few hits that clip a module edge and share their charge outside it.
    minMatchFraction=cms.double(0.8),
)

process.out = cms.OutputModule(
    "PoolOutputModule",
    fileName=cms.untracked.string("muon_gun_digi.root"),
    outputCommands=cms.untracked.vstring(
        "drop *",
        "keep *_simSiPixelDigis_*_*",
        "keep *_simSiStripDigis_*_*",
        "keep *_g4SimHits_*_*",
        "keep *_generator_*_*",
    ),
)

process.p = cms.Path(
    process.generator * process.generatorSmeared * process.g4SimHits
    * process.mix * process.digis
)
process.e = cms.EndPath(process.out)
