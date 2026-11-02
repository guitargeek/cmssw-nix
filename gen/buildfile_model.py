"""What gen/prepare_sources.py does to the BuildFile dependency graph, for
the scripts that reason about it (plan_packages.py, rank_blockers.py).

deps_of() reads a package's BuildFile.xml files and returns the package and
external-tool ("scram tool") dependencies, minus the edges prepare_sources.py
prunes (PRUNED_EDGES), the library stanzas it deletes (STANZA) and, like
gen/cmssw_cmake.py, the <iftool> blocks.
"""
import os
import re

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
 ("SimG4Core/CustomPhysics", "GeneratorInterface/Pythia8Interface"),
 ("PhysicsTools/PatAlgos", "PhysicsTools/TensorFlow"),
 ("RecoBTag/ONNXRuntime", "HeterogeneousCore/SonicTriton"),
 ("L1Trigger/L1TMuonEndCap", "PhysicsTools/TensorFlow"),
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

def strip_iftool(xml):
    """Drop the <iftool> blocks, line by line as gen/cmssw_cmake.py does."""
    out, depth = [], 0
    for line in xml.split("\n"):
        if "<iftool" in line and "/>" not in line:
            depth += 1
        elif "</iftool" in line:
            depth = max(0, depth - 1)
        elif "<iftool" in line:
            pass
        elif depth == 0:
            out.append(line)
    return "\n".join(out)

def deps_of(src, p, parts=("", "src", "bin", "plugins")):
    """(package deps, tool deps) of package p, from the BuildFiles of parts."""
    P, T = set(), set()
    for sub in parts:
        bf = os.path.join(src, p, sub, "BuildFile.xml") if sub else os.path.join(src, p, "BuildFile.xml")
        if not os.path.isfile(bf): continue
        txt = re.sub(r"<!--.*?-->", "", open(bf, encoding="latin-1").read(), flags=re.DOTALL)
        txt = strip_iftool(txt)
        for pat in STANZA: txt = re.sub(pat, "", txt, flags=re.DOTALL)
        for n in use_re.findall(txt):
            if (p, n) in PRUNED_EDGES: continue
            (P if "/" in n else T).add(n)
    return P, T
