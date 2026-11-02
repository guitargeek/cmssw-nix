# Raw data, the second half: read the streamer file back and unpack it.
#
# This is how reconstruction of detector data begins - a streamer file from
# the HLT, a FEDRawDataCollection per event, and the unpackers turning FED
# buffers back into digis. The HCAL unpacker here runs exactly as it does on
# collision data; the only difference is where the buffers came from
# (python/muon_gun_raw_cfg.py packed them from simulated digis).
#
# The streamer file also carries those simulated digis, so the check is
# exact: plugins/HcalDigiRoundTrip.cc requires every channel to come back
# with the same samples, ADC count for ADC count.
#
# 20_1 only, like python/muon_gun_raw_cfg.py, which has to run first.
import os
import sys

import FWCore.ParameterSet.Config as cms

# the calorimeter job, for its geometry and the HCAL conditions
sys.path.insert(0, globals().get("__file__") and os.path.dirname(os.path.abspath(__file__))
                or os.path.join(os.getcwd(), "python"))
from muon_gun_calo_cfg import process

process.setName_("UNPACK")

process.source = cms.Source(
    "NewEventStreamFileReader",
    fileNames=cms.untracked.vstring("file:muon_gun_raw.dat"),
)

# No digitisation here: the digis come from the file. The calorimeter job's
# alias would point the original digis at a mixing module of this process.
del process.mix
del process.simEcalUnsuppressedDigis
del process.simHcalUnsuppressedDigis

# --- the electronics map ----------------------------------------------------
# The packer and the unpacker need real readout addresses, which the
# hardcoded map does not have; see plugins/HcalSyntheticVMEMap.cc.
process.es_hardcode.toGet.remove("ElectronicsMap")
process.hcalVMEMap = cms.ESProducer("HcalSyntheticVMEMap")

# --- unpacking --------------------------------------------------------------
process.load("EventFilter.HcalRawToDigi.HcalRawToDigi_cfi")

process.roundTrip = cms.EDAnalyzer(
    "HcalDigiRoundTrip",
    original=cms.InputTag("mix", "", "RAW"),
    unpacked=cms.InputTag("hcalDigis"),
    # the electronics map covers every HB, HE and HO channel the digitiser
    # fills; allow for nothing to be lost
    maxMissingFraction=cms.double(0.0),
)

process.p = cms.Path(process.hcalDigis * process.roundTrip)
process.schedule = cms.Schedule(process.p)
