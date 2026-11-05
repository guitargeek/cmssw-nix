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

_is_10_6 = os.environ.get("CMSSW_VERSION", "").startswith("CMSSW_10_")

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
# New in 20_1: the tracker digi geometry depends on a per-det additional
# parameters record that did not exist in the 10_6 era.
if not _is_10_6:
    process.TrackerAdditionalParametersPerDetESModule = cms.ESProducer(
        "TrackerAdditionalParametersPerDetESModule"
    )
# SiStripDetInfoFileReader is a Service only in the 10_6 era; the strip fake
# ES sources ask the framework for it by name. 20_1 replaced it with a plain
# class (CalibFormats/SiStripObjects' SiStripDetInfo, read through
# Geometry/TrackerNumberingBuilder/interface/utils.h), so there is no
# service to declare and asking for one aborts with PluginNotFound.
if _is_10_6:
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
        cms.PSet(
            # 20_1 only - see plugins/PixelDetVOffWriter.cc
            record=cms.string("SiPixelDetVOffRcd"),
            tag=cms.string("SiPixelDetVOff_empty"),
        ),
        cms.PSet(
            # 20_1 only - the pixel templates, see below
            record=cms.string("SiPixelTemplateDBObjectRcd"),
            tag=cms.string("SiPixelTemplateDBObject_38T_2021"),
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

# See ../common/plugins/PixelLorentzAngleWriter.cc: the fake ES source covers the
# phase-0 pixel detector, so against a 2018 geometry it supplies nothing
# and reconstruction silently applies no Lorentz correction.
process.pixelLorentzAngleWriter = cms.EDAnalyzer(
    "PixelLorentzAngleWriter",
    record=cms.string("SiPixelLorentzAngleRcd"),
    # the same value the fake source would have used, and the same one the
    # digitiser drifts the charge with
    tanLorentzAnglePerTesla=cms.double(0.106),
)

# See plugins/PixelDetVOffWriter.cc: 20_1's SiPixelQualityESProducer consumes
# SiPixelDetVOffRcd whether or not its ListOfRecordToMerge asks for it, and
# nothing in this build produces that record.
if not _is_10_6:
    process.pixelDetVOffWriter = cms.EDAnalyzer(
        "PixelDetVOffWriter",
        record=cms.string("SiPixelDetVOffRcd"),
    )

# The pixel templates for python/muon_gun_fastsim_cfg.py: the fast
# simulation smears each pixel hit with the cluster shapes of the template
# its module is mapped to, and reads them from SiPixelTemplateDBObjectRcd
# whether or not it would use them. CMS's uploader packs template files and
# a module-to-template map into the payload. The map is one template for
# the whole barrel (1009, unirradiated, as the digitiser simulates the
# sensors) and one for the forward disks (1016, the least irradiated of the
# forward ones): a production map assigns them per layer and per run period.
if not _is_10_6:
    _templates = "CalibTracker/SiPixelESProducers/data/templates_38T_2021_IOV0/template_summary_zp%d.out"
    # every phase-1 module, as layer_ladder_module and disk_blade_side_panel
    _barrel = ["%d_%d_%d" % (layer, ladder, module)
               for layer, ladders in enumerate((12, 28, 44, 64), start=1)
               for ladder in range(1, ladders + 1)
               for module in range(1, 9)]
    _endcap = ["%d_%d_%d_%d" % (disk, blade, side, panel)
               for disk in (1, 2, 3)
               for blade in range(1, 57)
               for side in (1, 2)
               for panel in (1, 2)]
    process.pixelTemplateWriter = cms.EDAnalyzer(
        "SiPixelTemplateDBObjectUploader",
        siPixelTemplateCalibrations=cms.vstring(_templates % 1009, _templates % 1016),
        theTemplateBaseString=cms.string("template_summary_zp"),
        Version=cms.double(1.0),
        # in tenths of a tesla, only compared with the files' headers
        MagField=cms.double(38.0),
        barrelLocations=cms.vstring(*_barrel),
        endcapLocations=cms.vstring(*_endcap),
        barrelTemplateIds=cms.vuint32(*[1009] * len(_barrel)),
        endcapTemplateIds=cms.vuint32(*[1016] * len(_endcap)),
    )

process.p = cms.Path(
    process.writer
    * process.gainWriter
    * process.pixelCablingWriter
    * process.pixelLorentzAngleWriter
)
if not _is_10_6:
    process.p *= process.pixelDetVOffWriter * process.pixelTemplateWriter
