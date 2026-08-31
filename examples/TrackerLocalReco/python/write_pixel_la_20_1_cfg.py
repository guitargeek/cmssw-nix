# Write the pixel Lorentz angle the 20_1 local reconstruction needs.
#
# See plugins/PixelLorentzAngleWriter.cc: CMSSW_20_1's only producer of
# SiPixelLorentzAngleRcd resolves a FileInPath default into a data-only
# package that is not in this build, during validation, whatever the
# configuration says. The payload is a flat tan(theta_L) per module, so it is
# easier to write one over the geometry actually loaded than to obtain that
# file.
#
# Run this before tracker_localreco_20_1_cfg.py. examples/ConditionsSqlite is
# the same machinery demonstrated on its own.
import os

import FWCore.ParameterSet.Config as cms

if os.path.exists("pixel_la.db"):
    os.remove("pixel_la.db")

process = cms.Process("WRITEPIXELLA")

process.load("FWCore.MessageService.MessageLogger_cfi")
process.maxEvents = cms.untracked.PSet(input=cms.untracked.int32(1))
process.source = cms.Source("EmptySource", firstRun=cms.untracked.uint32(1))

# The same 2016 tracker description the reconstruction job uses: the payload
# has to cover exactly the DetIds that job will ask about.
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
    "TrackerGeometricDetESModule", fromDDD=cms.bool(True), fromDD4hep=cms.bool(False)
)
process.TrackerParametersESModule = cms.ESProducer(
    "TrackerParametersESModule", fromDD4hep=cms.bool(False)
)
# New in 20_1: the tracker digi geometry depends on a per-det additional
# parameters record that did not exist in the 10_6 era.
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

process.load("CondCore.CondDB.CondDB_cfi")
process.CondDB.connect = cms.string("sqlite_file:pixel_la.db")
process.PoolDBOutputService = cms.Service(
    "PoolDBOutputService",
    process.CondDB,
    timetype=cms.untracked.string("runnumber"),
    toPut=cms.VPSet(
        cms.PSet(
            record=cms.string("SiPixelLorentzAngleRcd"),
            tag=cms.string("SiPixelLorentzAngle_ideal"),
        ),
    ),
)

process.writer = cms.EDAnalyzer(
    "PixelLorentzAngleWriter",
    record=cms.string("SiPixelLorentzAngleRcd"),
    # the value the fake source would have used
    tanLorentzAnglePerTesla=cms.double(0.106),
)

process.p = cms.Path(process.writer)
