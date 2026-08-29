# Reopen the DIGI file the way an analysis would - FWLite, no cmsRun - and
# confirm the digis survived being written and read back.
#
# The point is not to repeat the assertions DigiCounter already made inside
# the job. It is that the digi collections are ordinary EDM products: they
# stream to ROOT and come back as themselves, which is what every later step
# (local reco, RAW packing) relies on.
import sys

import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gSystem.Load("libFWCoreFWLite")
ROOT.FWLiteEnabler.enable()

from DataFormats.FWLite import Events, Handle

events = Events("muon_gun_digi.root")
handle = Handle("edm::DetSetVector<SiStripDigi>")
label = ("simSiStripDigis", "ZeroSuppressed")

n_events = 0
n_digis = 0
n_modules = 0
adc_sum = 0
for event in events:
    n_events += 1
    event.getByLabel(label, handle)
    if not handle.isValid():
        sys.exit("event %d: no SiStripDigi collection in the file" % n_events)
    dsv = handle.product()
    for detset in dsv:
        n_modules += 1
        for digi in detset:
            n_digis += 1
            adc_sum += digi.adc()

print("muon_gun_digi.root: %d events" % n_events)
print("  strip digis: %d in %d module-instances" % (n_digis, n_modules))
print("  mean ADC: %.2f" % (adc_sum / n_digis if n_digis else 0.0))

if n_events == 0:
    sys.exit("the file has no events")
if n_digis == 0:
    sys.exit("the digis did not survive being written and read back")
# A strip digi is 8 bits: anything outside that means the readback is
# misinterpreting the payload rather than merely finding it.
if not 0 < adc_sum / n_digis < 256:
    sys.exit("mean ADC %.2f is not a plausible 8-bit strip amplitude"
             % (adc_sum / n_digis))

print("digi output OK")
