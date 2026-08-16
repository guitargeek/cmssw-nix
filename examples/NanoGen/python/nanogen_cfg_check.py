# Readback validation of the NanoGen output: opens nanogen.root like an
# analysis would (plain ROOT, no CMSSW involved) and checks the flat-table
# content - the Events tree with GenPart/GenJet branches, a genWeight, and a
# dimuon mass peak at the Z.
import math
import sys

import ROOT

f = ROOT.TFile.Open("nanogen.root")
assert f and not f.IsZombie(), "nanogen.root missing or unreadable"
events = f.Get("Events")
assert events, "no Events tree"
n = events.GetEntries()
assert n > 0, "empty Events tree"

for branch in ["nGenPart", "GenPart_pt", "GenPart_eta", "GenPart_phi",
               "GenPart_mass", "GenPart_pdgId", "GenPart_status",
               "GenPart_genPartIdxMother", "nGenJet", "GenJet_pt",
               "genWeight", "Generator_id1", "Generator_x1"]:
    assert events.GetBranch(branch), f"missing branch {branch}"

nZ = 0
for event in events:
    mus = [i for i in range(event.nGenPart)
           if abs(event.GenPart_pdgId[i]) == 13 and event.GenPart_status[i] == 1]
    plus = [i for i in mus if event.GenPart_pdgId[i] == -13]
    minus = [i for i in mus if event.GenPart_pdgId[i] == 13]
    if not plus or not minus:
        continue
    vecs = []
    for idx in (max(plus, key=lambda i: event.GenPart_pt[i]),
                max(minus, key=lambda i: event.GenPart_pt[i])):
        v = ROOT.TLorentzVector()
        v.SetPtEtaPhiM(event.GenPart_pt[idx], event.GenPart_eta[idx],
                       event.GenPart_phi[idx], 0.10566)
        vecs.append(v)
    if abs((vecs[0] + vecs[1]).M() - 91.19) < 15.0:
        nZ += 1

frac = nZ / n
print(f"nanogen.root: {n} events, {nZ} with a dimuon mass at the Z ({frac:.0%})")
if frac < 0.8:
    print("FAILED: too few Z -> mumu events in the nanoAOD output")
    sys.exit(1)
print("nanoAOD readback OK")
