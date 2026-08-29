# Write the simulated-Lorentz-angle payload the strip digitiser needs.
#
# SiStripDigitizerAlgorithm reads SiStripLorentzAngleSimRcd - the *simulated*
# Lorentz angle, a different record from the SiStripLorentzAngleRcd that
# reconstruction uses. Every fake (from-parameters) ES source in
# CalibTracker/SiStripESProducers serves the reconstruction record only:
#
#   SiStripLorentzAngleFakeESSource.cc:112   findingRecord<SiStripLorentzAngleRcd>();
#
# and nothing in the release produces the Sim record at all. In production it
# comes from the global tag, which is why this is never noticed. So it has to
# come from a database here too, and this job makes one: take the ideal
# Lorentz angle out of the fake source and write it to a local sqlite file
# under the record name the digitiser will ask for. The writer is CMS's own
# DummyCondDBWriter - it copies an EventSetup object into the conditions
# output service, and the output service decides what record it is filed as.
#
# Run this before muon_gun_digi_cfg.py. examples/ConditionsSqlite is the same
# machinery demonstrated on its own.
import os

import FWCore.ParameterSet.Config as cms

# A fresh database every time: PoolDBOutputService appends to an existing tag,
# and a leftover file would hide a writer that had stopped working.
if os.path.exists("sim_conditions.db"):
    os.remove("sim_conditions.db")

process = cms.Process("WRITESIMCOND")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))
process.source = cms.Source("EmptySource", firstRun=cms.untracked.uint32(1))

# The fake source builds the ideal Lorentz angle per module, so it needs the
# tracker geometry and topology to know what the modules are.
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
process.SiStripDetInfoFileReader = cms.Service("SiStripDetInfoFileReader")

process.load("CalibTracker.SiStripESProducers.fake.SiStripLorentzAngleFakeESSource_cfi")
process.load("CalibTracker.SiStripESProducers.fake.SiStripApvGainFakeESSource_cfi")

process.load("CondCore.CondDB.CondDB_cfi")
process.CondDB.connect = cms.string("sqlite_file:sim_conditions.db")

# The record written is SiStripLorentzAngleSimRcd even though the object was
# read from SiStripLorentzAngleRcd: same C++ payload type, different record,
# which is exactly the gap being bridged.
process.PoolDBOutputService = cms.Service(
    "PoolDBOutputService",
    process.CondDB,
    timetype=cms.untracked.string("runnumber"),
    toPut=cms.VPSet(
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
        cms.PSet(
            record=cms.string("SiPixelLorentzAngleRcd"),
            tag=cms.string("SiPixelLorentzAngle_ideal"),
        ),
    ),
)

process.writer = cms.EDAnalyzer(
    "SiStripLorentzAngleDummyDBWriter",
    OpenIovAt=cms.untracked.string("beginOfTime"),
    OpenIovAtTime=cms.untracked.uint32(1),
    # the record to write as; the record it reads is fixed by the module's
    # template arguments (SiStripLorentzAngleRcd)
    record=cms.string("SiStripLorentzAngleSimRcd"),
)

# The simulated gain has the same problem as the Lorentz angle, and one
# more twist: SiStripGainSimRcd is a *dependent* record -
#   class SiStripGainSimRcd : DependentRecordImplementation<..., SiStripApvGainSimRcd>
# so pointing SiStripGainSimESProducer at the reconstruction gain is not
# enough. The framework still wants an IOV for SiStripApvGainSimRcd
# itself, and fails with "no valid IOV for the synchronization value".
process.gainWriter = cms.EDAnalyzer(
    "SiStripApvGainDummyDBWriter",
    OpenIovAt=cms.untracked.string("beginOfTime"),
    OpenIovAtTime=cms.untracked.uint32(1),
    record=cms.string("SiStripApvGainSimRcd"),
)

# See plugins/PixelCablingMapWriter.cc: the pixel digitiser fetches this
# record unconditionally and only dereferences it behind guards that are
# off here, and no phase-1 cabling description ships with the release.
process.pixelCablingWriter = cms.EDAnalyzer(
    "PixelCablingMapWriter",
    record=cms.string("SiPixelFedCablingMapRcd"),
    version=cms.string("empty - see PixelCablingMapWriter.cc"),
)

# See plugins/PixelLorentzAngleWriter.cc: the fake ES source covers the
# phase-0 pixel detector, so against a 2018 geometry it supplies nothing
# and reconstruction silently applies no Lorentz correction.
process.pixelLorentzAngleWriter = cms.EDAnalyzer(
    "PixelLorentzAngleWriter",
    record=cms.string("SiPixelLorentzAngleRcd"),
    # the same value the fake source would have used, and the same one the
    # digitiser drifts the charge with
    tanLorentzAnglePerTesla=cms.double(0.106),
)

process.p = cms.Path(
    process.writer
    * process.gainWriter
    * process.pixelCablingWriter
    * process.pixelLorentzAngleWriter
)
