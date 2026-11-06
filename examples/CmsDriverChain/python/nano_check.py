"""Read the chain's NanoAOD with plain ROOT and match the reconstructed muons
to the generated ones (the gun fires a muon pair, pt 10 GeV, per event)."""
import math
import sys

import ROOT

f = ROOT.TFile.Open(sys.argv[1] if len(sys.argv) > 1 else "step4.root")
events = f.Get("Events")
print(f"{events.GetEntries()} events, {len(events.GetListOfBranches())} branches")

generated = matched = 0
resolution = []
for ev in events:
    for i in range(ev.nGenPart):
        if abs(ev.GenPart_pdgId[i]) != 13 or ev.GenPart_status[i] != 1:
            continue
        generated += 1
        best = None
        for j in range(ev.nMuon):
            dphi = (ev.Muon_phi[j] - ev.GenPart_phi[i] + math.pi) % (2 * math.pi) - math.pi
            dr = math.hypot(ev.Muon_eta[j] - ev.GenPart_eta[i], dphi)
            if dr < 0.1 and (best is None or dr < best[0]):
                best = (dr, ev.Muon_pt[j])
        if best:
            matched += 1
            resolution.append(abs(best[1] - ev.GenPart_pt[i]) / ev.GenPart_pt[i])

resolution.sort()
median = resolution[len(resolution) // 2] if resolution else float("nan")
print(f"{matched}/{generated} generated muons reconstructed, median |dpt|/pt = {100 * median:.2f}%")
if generated == 0 or matched < 0.8 * generated:
    sys.exit("too few muons reconstructed")
