"""Work out which CMSSW packages a release can actually build, and write the
build configuration for them.

Given a source tree, a base configuration (the packages that must be kept)
and a "wanted" configuration (typically the other release era's config, i.e.
the scope we would like to reach), this walks the BuildFile dependency graph
and decides, for every package, whether it can be built here:

  * a package is buildable when none of its external tools are in MISSING
    and all of its package dependencies are buildable,
  * the plugins/ directory can be dropped ("no_plugins") when only that part
    is unbuildable - but only after the with-plugins pass has converged, so
    that a dependency which is merely unresolved *yet* never causes a package
    to lose its plugin library,
  * mutually dependent packages (a plugin library that uses its own package,
    or two packages that reference each other) are accepted as a group,
  * the dependency edits that gen/prepare_sources.py applies before the build
    are modelled in PRUNED_EDGES, and the library stanzas it deletes in
    STANZA, so the picture matches what actually gets compiled.

Usage:
  python3 gen/plan_packages.py --src <cmssw source> --base gen/config.yml \
      --wanted gen/config-10_6.yml --output gen/config.yml
"""
import argparse
import os
import re
from collections import defaultdict

import yaml

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--src", required=True, help="path to the CMSSW source tree")
parser.add_argument("--base", required=True, help="configuration whose packages must be kept")
parser.add_argument("--wanted", required=True, help="configuration describing the scope to reach")
parser.add_argument("--output", required=True, help="configuration file to write")
args = parser.parse_args()
SRC = args.src

want_cfg = yaml.safe_load(open(args.wanted))
BASE = yaml.safe_load(open(args.base))
def pkgs(cfg): return {f"{s}/{p}" for s, sp in cfg["subsystems"].items() for p in sp.get("whitelist", [])}
p106, base = pkgs(want_cfg), pkgs(BASE)
want = sorted(base | {p for p in p106 if os.path.isdir(os.path.join(SRC, p))})

MISSING = {"utm","tensorflow-cc","pytorch","pytorch-cuda","xtd","libtorch",
 "oracle","oracleocci","lhapdf","pythia8","pythia6","evtgen","photospp","tauolapp","mcdb","libhepml",
 "fftw3","fftjet","gbl","frontier_client","classlib","mille","opengl","rootx11","rootgui","rooteve",
 "rootged","rootglew","rootrgl","rootguihtml","rootgeompainter","rootinteractive","davix","conifer",
 "hls4ml","triton-inference-client","grpc","cuda","cudart","xrootd","protobuf"}
# only the trees that would drag in whole unrelated subsystems; everything
# else is decided by the tool fixpoint below
EXCL_SUBS = {"DQMServices","DQMOffline","DQM","FastSimulation","GeneratorInterface","OnlineDB",
 "Alignment","SimG4Core","SimG4CMS","L1TriggerConfig","Fireworks","TBDataFormats","CalibPPS",
 "HLTrigger","Validation","HeavyIonsAnalysis","MLTools","IORawData","DPGAnalysis"}
EXCL_PKGS = {"PhysicsTools/TensorFlow","CondCore/Utilities",
 "PhysicsTools/PyTorch","PhysicsTools/PyTorchAlpaka","PhysicsTools/NanoAOD",
 "PhysicsTools/PatAlgos","PhysicsTools/PatUtils","CommonTools/TriggerUtils","RecoTauTag/HLTProducers",
 "RecoBTag/FeatureTools","FWStorage/XrdAdaptor",
 "Geometry/HGCalMapping","RecoLocalCalo/HGCalRecProducers",
 "RecoParticleFlow/PFRecHitProducer"}
ALLOW = {"Utilities/BinningTools","Utilities/General","Utilities/Xerces","Utilities/StorageFactory"}
def excluded(p):
    return p in EXCL_PKGS or (p.split("/")[0] in EXCL_SUBS and p not in ALLOW)

use_re = re.compile(r'<\s*use\s+name\s*=\s*"([^"]+)"')
STANZA = [r'<library[^>]*>(?:(?!</library>).)*DD4HEP_PLUGIN(?:(?!</library>).)*</library>\n?',
 r'<library[^>]*>(?:(?!</library>).)*name="(?:Fireworks/Core)"(?:(?!</library>).)*</library>\n?',
 r'<library[^>]*name="(?:DD4hep_|alpaka_)[^"]*"[^>]*>(?:(?!</library>).)*</library>\n?']
# dependencies that gen/prepare_sources.py removes before the build
PRUNED_EDGES = {
 ("FWCore/Services", "Utilities/XrdAdaptor"), ("FWCore/Services", "FWStorage/XrdAdaptor"),
 ("FWStorage/Services", "FWStorage/XrdAdaptor"),
 ("CalibTracker/SiStripESProducers", "DQMServices/Core"),
 ("CalibTracker/SiStripCommon", "SimTracker/TrackAssociation"),
 ("CalibTracker/SiStripCommon", "SimTracker/Records"),
 ("CalibTracker/SiStripCommon", "TrackingTools/TrackFitters"),
 ("CalibCalorimetry/EcalTPGTools", "SimCalorimetry/EcalSimAlgos"),
 ("CalibCalorimetry/EcalTrivialCondModules", "CondTools/Ecal"),
 ("CalibCalorimetry/EcalTrivialCondModules", "SimG4CMS/Calo"),
 ("RecoLocalCalo/HcalRecAlgos", "RecoMET/METAlgorithms"),
 ("RecoLocalMuon/RPCRecHit", "TrackingTools/TrackRefitter"),
 ("RecoMET/METPUSubtraction", "PhysicsTools/TensorFlow"),
 ("RecoTauTag/RecoTau", "PhysicsTools/TensorFlow"),
 ("RecoTracker/TrackProducer", "Alignment/TwoBodyDecay"),
 ("RecoTracker/TrackProducer", "Alignment/ReferenceTrajectories"),
 ("RecoTracker/DeDx", "HLTrigger/HLTcore"),
 ("CondCore/BeamSpotPlugins", "CondCore/Utilities"),
 # TensorFlow / Triton consumers pruned at prepare time
 ("RecoEcal/EgammaCoreTools", "PhysicsTools/TensorFlow"),
 ("RecoEcal/EgammaClusterAlgos", "HeterogeneousCore/SonicTriton"),
 ("RecoEcal/EgammaClusterAlgos", "HeterogeneousCore/SonicCore"),
 ("RecoEcal/EgammaClusterProducers", "HeterogeneousCore/SonicTriton"),
 ("RecoEcal/EgammaClusterProducers", "HeterogeneousCore/SonicCore"),
 ("RecoEgamma/EgammaTools", "HeterogeneousCore/SonicTriton"),
 ("RecoEgamma/EgammaTools", "HeterogeneousCore/SonicCore"),
 ("RecoTauTag/RecoTau", "HeterogeneousCore/SonicTriton"),
 ("RecoTauTag/RecoTau", "HeterogeneousCore/SonicCore"),
 ("RecoMuon/TrackerSeedGenerator", "PhysicsTools/TensorFlow"),
 ("RecoMuon/TrackerSeedGenerator", "SimTracker/TrackTriggerAssociation"),
}
def deps_of(p, drop_plugins=False):
    P, T = set(), set()
    for sub in ["", "src", "bin"] + ([] if drop_plugins else ["plugins"]):
        bf = os.path.join(SRC, p, sub, "BuildFile.xml") if sub else os.path.join(SRC, p, "BuildFile.xml")
        if not os.path.isfile(bf): continue
        txt = re.sub(r"<!--.*?-->", "", open(bf, encoding="latin-1").read(), flags=re.DOTALL)
        for pat in STANZA: txt = re.sub(pat, "", txt, flags=re.DOTALL)
        for n in use_re.findall(txt):
            if (p, n) in PRUNED_EDGES: continue
            (P if "/" in n else T).add(n)
    return P, T
universe, todo = set(x for x in want if not excluded(x)), [x for x in want if not excluded(x)]
while todo:
    p = todo.pop()
    for x in deps_of(p)[0]:
        if os.path.isdir(os.path.join(SRC, x)) and not excluded(x) and x not in universe:
            universe.add(x); todo.append(x)
status, mode = {}, {}
# Phase 1: converge with plugins included, so no_plugins is only ever used
# when the plugin library genuinely cannot build (a dep that is merely not
# resolved *yet* must not lock a package into no_plugins).
for phase_modes in ([False], [False, True]):
    for _ in range(80):
        ch = False
        for p in sorted(universe):
            if status.get(p): continue
            for dp in phase_modes:
                P, T = deps_of(p, dp)
                if p == "CondFormats/L1TObjects": T = T - {"utm"}
                if {t for t in T if t in MISSING}: continue
                if {x for x in P if x != p and os.path.isdir(os.path.join(SRC,x)) and (excluded(x) or not status.get(x))}: continue
                status[p] = True; mode[p] = "no_plugins" if dp else "full"; ch = True; break
        if not ch: break
# cycle-optimistic
for _ in range(6):
    for p in sorted(universe):
        if status.get(p): continue
        P, T = deps_of(p)
        if p == "CondFormats/L1TObjects": T = T - {"utm"}
        if {t for t in T if t in MISSING}: continue
        unmet = {x for x in P if x != p and os.path.isdir(os.path.join(SRC,x)) and not status.get(x)}
        if unmet and not any(excluded(u) for u in unmet):
            grp = unmet | {p}
            if all(not {t for t in deps_of(g)[1] if t in MISSING} and
                   all(y in grp or status.get(y) for y in deps_of(g)[0]
                       if os.path.isdir(os.path.join(SRC,y)) and y != g) for g in grp):
                for g in grp: status[g] = True; mode.setdefault(g, "full")
# Final upgrade pass: a package may have been accepted with no_plugins while
# one of its plugin dependencies was still unresolved. Now that the buildable
# set is known, give the plugin library back to everything whose plugin
# dependencies are all buildable after all.
ok = {p for p in universe if status.get(p)}
for _ in range(10):
    changed = False
    for p in sorted(ok):
        if mode.get(p) != "no_plugins":
            continue
        P, T = deps_of(p, drop_plugins=False)
        if p == "CondFormats/L1TObjects":
            T = T - {"utm"}
        if {t for t in T if t in MISSING}:
            continue
        if {x for x in P if x != p and os.path.isdir(os.path.join(SRC, x)) and x not in ok}:
            continue
        mode[p] = "full"
        changed = True
    if not changed:
        break
npl = {p for p in ok if mode.get(p) == "no_plugins"}
print("buildable:", len(ok), " no_plugins:", len(npl), " blocked wanted:", len([p for p in want if p not in ok]))
for p in [p for p in want if p not in ok]: print("   blocked:", p)
bysub = defaultdict(list)
for p in sorted(ok): bysub[p.split("/")[0]].append(p.split("/",1)[1])
# Subsystem-wide no_plugins settings are deliberate configuration (the alpaka
# accelerator modules in DataFormats/ and HeterogeneousCore/) and are carried
# over; per-package entries are decided by the fixpoint above, so a stale one
# from the base configuration must not survive a regeneration.
old_np = {s for s, sp in BASE["subsystems"].items() if sp.get("no_plugins") is True}
hdr = open(args.base).read().split("bins:")[0].rstrip("\n")
SCOPE_NOTE = [
 "#",
 "# Extended to the scope of the 10_6 configuration: the full local and",
 "# high-level reconstruction chain. Left out are the 20_1-era packages that",
 "# need inference externals we do not build (TensorFlow, PyTorch, Triton,",
 "# hls4ml) and the trigger/simulation subsystems.",
]
# keep the note out of the header when regenerating from a previous output
L = [hdr] + ([] if "Extended to the scope" in hdr else SCOPE_NOTE) + ["bins:"]
for b in ["FWCore/Framework","FWCore/PluginManager","FWCore/ParameterSet","IOPool/Common"]:
    if b in ok: L.append(f"  - {b}")
L.append("subsystems:")
for s in sorted(bysub):
    L.append(f"    {s}:")
    here = sorted(n for n in bysub[s] if f"{s}/{n}" in npl)
    if s in old_np: L.append("        no_plugins: true")
    elif here:
        L.append("        no_plugins:")
        for n in here: L.append(f"          - {n}")
    L.append("        whitelist:")
    for n in sorted(bysub[s]): L.append(f"          - {n}")
open(args.output,"w").write("\n".join(L)+"\n")
print("wrote config.yml with", len(ok), "packages")
