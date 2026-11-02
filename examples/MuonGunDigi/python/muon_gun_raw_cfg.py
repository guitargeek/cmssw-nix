# Raw data, the first half: pack the HCAL digis into the format the detector
# reads out, and write it to a streamer file.
#
# Every job so far has handed digis from one module to the next as C++
# objects. The detector does not: its front ends write FED buffers, the DAQ
# assembles one FEDRawDataCollection per event, and the high-level trigger
# farm writes those into streamer files. Reconstruction of real data starts
# by unpacking them. This job runs the HCAL packer on the digis that
# python/muon_gun_calo_cfg.py digitises, collects the FED buffers the way the
# DAQ does, and writes the event in the streamer format - the HLT's output
# format, not a ROOT file. python/muon_gun_unpack_cfg.py reads it back.
#
# HCAL, because its digis are already here (the calorimeter job makes them)
# and the one thing its packer needs besides them, the electronics map -
# which channel sits on which fiber of which FED - can be built from the
# topology (plugins/HcalSyntheticVMEMap.cc). The tracker and muon packers
# need cabling maps that only exist in the conditions database.
#
# 20_1 only: the 10_6 configuration does not build the raw data packages.
#
# Reads muon_gun_digi.root, so run python/muon_gun_digi_cfg.py first.
import os
import sys

import FWCore.ParameterSet.Config as cms

# the calorimeter job, for its geometry, conditions and digitisation; cmsRun
# does not put the config's directory on sys.path
sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_calo_cfg import process

process.setName_("RAW")

# --- the electronics map ----------------------------------------------------
# The packer and the unpacker need real readout addresses, which the
# hardcoded map does not have; see plugins/HcalSyntheticVMEMap.cc.
process.es_hardcode.toGet.remove("ElectronicsMap")
process.hcalVMEMap = cms.ESProducer("HcalSyntheticVMEMap")

# --- packing ----------------------------------------------------------------
# The VME-era HCAL packer: the QIE8 digis of the barrel, endcap and outer
# calorimeter that the digitiser produces without a run era. (Run 3 HB/HE
# would go through the uTCA packer, hcalDigiToRawuHTR.) No trigger
# primitives are packed; the emulator is not part of this job.
process.hcalRawData = cms.EDProducer(
    "HcalDigiToRaw",
    HBHE=cms.untracked.InputTag("simHcalUnsuppressedDigis"),
    HF=cms.untracked.InputTag(""),
    HO=cms.untracked.InputTag("simHcalUnsuppressedDigis"),
    ZDC=cms.untracked.InputTag(""),
    TRIG=cms.untracked.InputTag(""),
)

# The event builder: one FEDRawDataCollection out of the per-subdetector
# ones, as the DAQ assembles it.
process.load("EventFilter.RawDataCollector.rawDataCollectorByLabel_cfi")
process.rawDataCollector.RawCollectionList = [cms.InputTag("hcalRawData")]

process.p = cms.Path(process.mix * process.hcalRawData * process.rawDataCollector)

# --- the streamer file ------------------------------------------------------
# The raw data, and the simulated digis next to it so the unpacking job can
# compare against them.
process.out = cms.OutputModule(
    "EventStreamFileWriter",
    fileName=cms.untracked.string("muon_gun_raw.dat"),
    compression_algorithm=cms.untracked.string("ZSTD"),
    compression_level=cms.untracked.int32(3),
    outputCommands=cms.untracked.vstring(
        "drop *",
        "keep FEDRawDataCollection_rawDataCollector_*_*",
        "keep *_mix_*_*",
    ),
)
process.e = cms.EndPath(process.out)
process.schedule = cms.Schedule(process.p, process.e)
