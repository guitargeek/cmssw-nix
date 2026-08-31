# The end of the chain, read the way an analysis would read it: plain ROOT on
# a flat TTree, no CMSSW, no dictionaries, no plugins. Nothing in this file
# knows that the numbers in it came from a Geant4 simulation of the CMS
# tracker and muon chambers.
#
# What it checks is the whole chain at once: for every muon the gun fired
# (GenPart), is there a reconstructed muon (Muon) in the same direction, and
# does its momentum agree with the generated one? A failure anywhere from the
# vertex smearing to the flat-table writer shows up here as a muon that is
# missing or has the wrong pt.
import sys

import ROOT

f = ROOT.TFile.Open("muon_gun_nano.root")
assert f and not f.IsZombie(), "muon_gun_nano.root missing or unreadable"
events = f.Get("Events")
assert events, "no Events tree"
n = events.GetEntries()
assert n > 0, "empty Events tree"

for branch in ["nMuon", "Muon_pt", "Muon_eta", "Muon_phi", "Muon_charge",
               "Muon_isGlobal", "Muon_isStandalone",
               "nGenPart", "GenPart_pt", "GenPart_eta", "GenPart_phi",
               "GenPart_pdgId", "GenPart_status"]:
    assert events.GetBranch(branch), "missing branch %s" % branch


def delta_r(eta1, phi1, eta2, phi2):
    d_phi = abs(phi1 - phi2)
    if d_phi > ROOT.TMath.Pi():
        d_phi = 2 * ROOT.TMath.Pi() - d_phi
    return ROOT.TMath.Sqrt((eta1 - eta2) ** 2 + d_phi ** 2)


n_gen = 0
n_matched = 0
n_global = 0
n_charge = 0
residuals = []

for event in events:
    gen = [i for i in range(event.nGenPart)
           if abs(event.GenPart_pdgId[i]) == 13 and event.GenPart_status[i] == 1]
    for g in gen:
        n_gen += 1
        best, best_dr = None, 0.1
        for m in range(event.nMuon):
            dr = delta_r(event.GenPart_eta[g], event.GenPart_phi[g],
                         event.Muon_eta[m], event.Muon_phi[m])
            if dr < best_dr:
                best, best_dr = m, dr
        if best is None:
            continue
        n_matched += 1
        if event.Muon_isGlobal[best]:
            n_global += 1
        # the generated charge is the sign of the pdgId, backwards: mu- is 13
        if event.Muon_charge[best] == (-1 if event.GenPart_pdgId[g] == 13 else 1):
            n_charge += 1
        residuals.append(abs(event.Muon_pt[best] - event.GenPart_pt[g])
                         / event.GenPart_pt[g])

residuals.sort()
median = residuals[len(residuals) // 2] if residuals else float("inf")
efficiency = n_matched / n_gen if n_gen else 0.0

print("muon_gun_nano.root: %d events, %d generated muons" % (n, n_gen))
print("  reconstructed %d (%.0f%%), %d of them global"
      % (n_matched, 100 * efficiency, n_global))
print("  median |dpt|/pt = %.3f%%, correct charge %d/%d"
      % (100 * median, n_charge, n_matched))

failures = []
if efficiency < 0.5:
    failures.append("only %.0f%% of the generated muons were reconstructed"
                    % (100 * efficiency))
if n_global < 0.5 * n_matched:
    failures.append("%d of %d matched muons are global - the tracker and the "
                    "muon system are not being combined" % (n_global, n_matched))
if median > 0.02:
    failures.append("median momentum residual %.1f%% is too large" % (100 * median))
if n_charge < n_matched:
    failures.append("%d of %d reconstructed muons have the generated charge"
                    % (n_charge, n_matched))

if failures:
    for message in failures:
        print("FAILED: " + message)
    sys.exit(1)
print("nanoAOD readback OK: the muons in the flat table are the muons the gun fired")
