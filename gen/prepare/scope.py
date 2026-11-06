"""What this build leaves out, and the source and BuildFile edits that go with
it.

CMSSW's BuildFiles declare dependencies on externals this build does not
package (TensorFlow without --with-tensorflow, the Triton client, PyTorch,
conifer, Hector, MPI, the Fortran generators, the GPU backends), on packages
outside its scope, and some that are stale or that scram only resolved
transitively. Where a library is otherwise in scope, the few files that need
the missing piece are pruned (or stubbed, so that a configuration asking for
them fails with a clear message) instead of losing the whole library.
"""
from common import *  # noqa: F401,F403

# --- only the plain cmsRun (all versions) ------------------------------------

path = "cmssw/FWCore/Framework/bin/BuildFile.xml"
with open(path) as f:
    xml = f.read()

# 10_6-era BuildFiles write <bin   name=...> with multiple spaces
bins = re.findall(r'<bin\s+name="[^"]*".*?</bin>', xml, flags=re.DOTALL)
keep = [b for b in bins if re.search(r'<bin\s+name="cmsRun"', b)]
if len(keep) == 1:  # already trimmed on a rerun -> keep as is
    with open(path, "w") as f:
        f.write(keep[0] + "\n")

# --- no CondorStatusService / XrdAdaptor dependency (all versions) ----------
# The file locations moved between 10_6 (FWCore/Services, Utilities/XrdAdaptor)
# and 20_1 (both in FWStorage).

for condor in [
    "cmssw/FWStorage/Services/plugins/CondorStatusService.cc",
    "cmssw/FWCore/Services/plugins/CondorStatusUpdater.cc",
]:
    if os.path.exists(condor):
        os.remove(condor)

for path in [
    "cmssw/FWStorage/Services/plugins/BuildFile.xml",
    "cmssw/FWCore/Services/plugins/BuildFile.xml",
]:
    if os.path.exists(path):
        # (each release declares it in one of the two)
        edit(path, required=False, editor=lambda xml: xml.replace('<use   name="Utilities/XrdAdaptor"/>\n', "").replace(
            '<use name="FWStorage/XrdAdaptor"/>\n', ""))

# ... and don't load the pruned plugins as default cmsRun services
path = "cmssw/FWCore/Framework/src/defaultCmsRunServices.cc"


def drop_default_services(src):
    for service in ["CondorStatusService", "XrdAdaptor::XrdStatisticsService", "XrdStatisticsService"]:
        src = re.sub(r',\s*"' + re.escape(service) + r'"', "", src)
        src = re.sub(r'"' + re.escape(service) + r'"\s*,', "", src)
    return src


edit(path, drop_default_services)

# --- CondCore without boost_python (all versions) ----------------------------
# The python wrapper module and the payload-inspector plugins need
# boost_python (and for the inspectors, CondCore/Utilities); both are out of
# scope - drop them, keeping the authentication-service plugins.
path = "cmssw/CondCore/CondDB/plugins/BuildFile.xml"
if os.path.exists(path):
    edit(path, lambda xml: re.sub(
        r'<library\s+file="CondDBPy[^"]*"[^>]*>.*?</library>\n', "", xml, flags=re.DOTALL))

for inspector in ["cmssw/CondCore/BeamSpotPlugins/plugins/BuildFile.xml"]:
    if os.path.exists(inspector):
        os.remove(inspector)

# The CondCore/<Sub>Plugins packages are not all payload inspectors:
# plugins/plugin.cc is the REGISTER_PLUGIN list that gives PoolDBESSource
# its record proxies for that subsystem's payloads. Without it, reading any
# such record out of a conditions database fails with
#   Unable to find plugin 'SiStripLorentzAngleSimRcd@NewProxy'
# which is what the strip digitiser needs (examples/MuonGunDigi), and the
# same for the pixel payloads in 20_1 (examples/TrackerLocalReco).
#
# So keep that one library and drop the inspectors beside it. They are the
# web display tool and they need python headers - boost_python in the 10_6
# era, pybind11 in 20_1, neither of which this build provides. Dropping
# them also removes the only reason to want CommonTools/TrackerMap and
# CalibTracker/StandaloneTrackerTopology.
for _sub in ("SiStripPlugins", "SiPixelPlugins"):
    path = "cmssw/CondCore/%s/plugins/BuildFile.xml" % _sub
    if not os.path.exists(path):
        continue
    edit(path, lambda xml: re.sub(
        r'<library\s+file="[^"]*_PayloadInspector\.cc"[^>]*>.*?</library>\n?',
        "", xml, flags=re.DOTALL))
    d = os.path.dirname(path)
    for f in os.listdir(d):
        if f.endswith("_PayloadInspector.cc"):
            os.remove(os.path.join(d, f))

# --- tracker local reco without DQM / dd4hep (all versions) ------------------
# CalibTracker/SiStripESProducers declares DQMServices/Core (+classlib) in its
# library BuildFile, but nothing in src/ or interface/ references DQM - the
# dependency is stale. Drop it instead of pulling the DQM subsystem in.
path = "cmssw/CalibTracker/SiStripESProducers/BuildFile.xml"
if os.path.exists(path):
    # (gone upstream by 20_1)
    edit(path, required=release_cycle < (11, 0), editor=lambda xml: re.sub(
        r'<use\s+name="(?:DQMServices/Core|classlib)"\s*/>\n?', "", xml))

# ... except for one plugin, which really does read bad modules from a DQM
# file - drop it.
path = "cmssw/CalibTracker/SiStripESProducers/plugins/real/SiStripBadModuleFedErrESSource.cc"
if os.path.exists(path):
    os.remove(path)

# CalibTracker/SiStripCommon's plugins mix things the local reco needs (the
# SiStripDetInfoFileReader service, TkDetMap, the DCS/BField filters) with
# the Shallow* calibration-ntuple producers, which would pull in the whole
# SimTracker truth-matching / track-fitting chain. Drop the Shallow half.
pdir = "cmssw/CalibTracker/SiStripCommon/plugins"
if os.path.isdir(pdir):
    for f in glob.glob(pdir + "/Shallow*"):
        os.remove(f)
    edit(pdir + "/SealModules.cc", lambda src: "\n".join(
        line for line in src.split("\n") if "Shallow" not in line))
    edit(pdir + "/BuildFile.xml", lambda xml: re.sub(
        r'<use\s+name="(?:SimTracker/[^"]*|TrackingTools/TrackFitters)"\s*/>\n?',
        "", xml))

# ... and, in the 20_1 era, four more that produce nanoAOD flat tables for
# tracker calibration (SiStripGainCalib, SiStripPositionCorrections,
# SiStripLorentzAngleRunInfo, TkInstLumi). They pull PhysicsTools/NanoAOD,
# which is not in the 20_1 package set, and taking the whole plugin library
# out instead would lose the SiStripDetInfoFileReader service that the strip
# digitiser needs. Nothing here writes a calibration ntuple.
if os.path.isdir(pdir):
    dropped = []
    for name in ("SiStripGainCalibTableProducer", "SiStripPositionCorrectionsTableProducer",
                 "SiStripLorentzAngleRunInfoTableProducer", "TkInstLumiTableProducer"):
        for f in glob.glob(pdir + "/" + name + ".*"):
            os.remove(f)
            dropped.append(name)
    if dropped:
        edit(pdir + "/BuildFile.xml", lambda xml: re.sub(
            r'<use\s+name="PhysicsTools/NanoAOD"\s*/>\n?', "", xml))

# --- calo local reco without RecoMET / Oracle / Geant4 (all versions) --------
# RecoLocalCalo/HcalRecAlgos declares RecoMET/METAlgorithms, but the only
# thing it actually links from that direction is EcalSeverityLevelAlgo
# (through the transitive closure) - depend on RecoLocalCalo/EcalRecAlgos
# directly instead of dragging in the muon/JetMET reco chains. The
# CalibCalorimetry/EcalTPGTools library declares the Ecal digitizer but
# does not use it.
path = "cmssw/RecoLocalCalo/HcalRecAlgos/BuildFile.xml"
if os.path.exists(path):
    # (10_6: 20_1 no longer declares RecoMET)
    edit(path, required=release_cycle < (11, 0), editor=lambda xml: xml.replace(
        '<use   name="RecoMET/METAlgorithms"/>',
        '<use   name="RecoLocalCalo/EcalRecAlgos"/>\n'
        '<use   name="DataFormats/TrackReco"/>'))

# The Ecal uncalibrated-rec-hit workers use the EB/EE pulse shapes from
# SimCalorimetry/EcalSimAlgos; scram got that library transitively through
# the EcalTPGTools dependency pruned above - declare it directly.
path = "cmssw/RecoLocalCalo/EcalRecProducers/plugins/BuildFile.xml"
if os.path.exists(path):
    # (10_6: in 20_1 neither of the two is declared)
    edit(path, required=release_cycle < (11, 0), editor=lambda xml: xml.replace(
        '<use   name="CalibCalorimetry/EcalTPGTools"/>',
        '<use   name="CalibCalorimetry/EcalTPGTools"/>\n'
        '<use   name="SimCalorimetry/EcalSimAlgos"/>'))
path = "cmssw/CalibCalorimetry/EcalTPGTools/BuildFile.xml"
if os.path.exists(path):
    edit(path, required=release_cycle < (11, 0), editor=lambda xml: re.sub(
        r'<use\s+name="SimCalorimetry/EcalSimAlgos"\s*/>\n?', "", xml))

# EcalTrivialConditionRetriever (the from-parameters source for all Ecal
# conditions) has two heavyweight dependencies for niche features: reading
# intercalib constants from XML files (CondTools/Ecal, which drags in Oracle)
# and the luminosity-ageing model (SimG4CMS/Calo, which drags in Geant4).
# The ageing class is fully self-contained -> vendor it into the package;
# the XML readers become a runtime error.
etcm = "cmssw/CalibCalorimetry/EcalTrivialCondModules"
if os.path.isdir(etcm) and os.path.exists("cmssw/SimG4CMS/Calo/interface/EnergyResolutionVsLumi.h"):
    for cls in ["EnergyResolutionVsLumi", "EvolutionECAL"]:
        shutil.copy("cmssw/SimG4CMS/Calo/interface/%s.h" % cls,
                    etcm + "/src/%s.h" % cls)
        with open("cmssw/SimG4CMS/Calo/src/%s.cc" % cls) as f:
            cc = f.read()
        with open(etcm + "/src/%s.cc" % cls, "w") as f:
            f.write(re.sub(r'#include "SimG4CMS/Calo/interface/(\w+\.h)"',
                           r'#include "\1"', cc))

    def fix_trivial_retriever(src):
        src = src.replace(
            '#include "SimG4CMS/Calo/interface/EnergyResolutionVsLumi.h"',
            '#include "EnergyResolutionVsLumi.h"')
        src = re.sub(r'#include "CondTools/Ecal/[^"]*"\n', "", src)
        src = re.sub(
            r'Ecal\w*XMLTranslator::readXML\([^;]*\);',
            'throw cms::Exception("Unsupported") << "reading intercalib '
            'constants from XML files is not supported in this build";',
            src)
        # the header object was only ever passed to the removed readXML calls
        src = re.sub(r'\n\s*EcalCondHeader h;', "", src)
        return src
    edit(etcm + "/src/EcalTrivialConditionRetriever.cc", fix_trivial_retriever)
    edit(etcm + "/BuildFile.xml", lambda xml: re.sub(
        r'<use\s+name="(?:CondTools/Ecal|SimG4CMS/Calo)"\s*/>\n?', "", xml))

# The DD-algorithm plugin BuildFiles (Geometry/*CommonData) build a second
# plugin library against dd4hep for the DD4hep-based geometry variant; only
# the classic DDD one is in scope.
for root, dirs, files in os.walk("cmssw/Geometry"):
    if "BuildFile.xml" in files and root.endswith("plugins"):
        edit(os.path.join(root, "BuildFile.xml"), required=False, editor=lambda xml: re.sub(
            r'<library[^>]*>(?:(?!</library>).)*DD4HEP_PLUGIN(?:(?!</library>).)*</library>\n?',
            "", xml, flags=re.DOTALL))

# --- muon local reco without Fireworks / dd4hep / track extrapolation ------
# The muon geometry builders ship extra plugin libraries for the Fireworks
# geometry validation and the DD4hep geometry variant (in stanzas flagged
# EDM_PLUGIN, so the DD4HEP_PLUGIN prune above does not catch them), and
# Geometry/MuonNumbering carries the DD4hep numbering classes in its main
# library. Drop them.
for root, dirs, files in os.walk("cmssw/Geometry"):
    if "BuildFile.xml" in files and root.endswith("plugins"):
        # only the Fireworks geometry-validation plugins: the DD4hep code
        # paths are pruned by name/flag below, and where dd4hep is available
        # (20_1) the regular ES-producer stanzas that use it must be kept
        edit(os.path.join(root, "BuildFile.xml"), required=False, editor=lambda xml: re.sub(
            r'<library[^>]*>(?:(?!</library>).)*name="Fireworks/Core"'
            r'(?:(?!</library>).)*</library>\n?',
            "", xml, flags=re.DOTALL))
        # ... and the DD4hep test plugins, which use the DDCMS classes
        # without declaring the dependency
        edit(os.path.join(root, "BuildFile.xml"), required=False, editor=lambda xml: re.sub(
            r'<library[^>]*name="DD4hep_[^"]*"[^>]*>(?:(?!</library>).)*</library>\n?',
            "", xml, flags=re.DOTALL))
# (only where dd4hep is unavailable: in the 20_1 era these files carry the
# real cms::MuonNumbering implementation, not an optional second path)
if release_cycle < (11, 0):
    for f in glob.glob("cmssw/Geometry/MuonNumbering/src/DD4hep_*.cc"):
        os.remove(f)

# RecoLocalMuon/RPCRecHit mixes the rec-hit producer with the RPC-efficiency
# extrapolation tools (RPCPointProducer and the track/segment-to-RPC
# propagators), whose TrackRefitter dependency would pull in the whole
# muon/tracker DetLayers chain. Drop the extrapolation half.
rdir = "cmssw/RecoLocalMuon/RPCRecHit"
if os.path.isdir(rdir):
    for name in ["TracktoRPC", "DTSegtoRPC", "CSCSegtoRPC", "RPCPointProducer"]:
        for f in glob.glob("%s/src/%s.*" % (rdir, name)) + glob.glob(
                "%s/interface/%s.*" % (rdir, name)):
            os.remove(f)
    if os.path.exists(rdir + "/src/SealModule.cc"):
        edit(rdir + "/src/SealModule.cc", lambda src: "\n".join(
            line for line in src.split("\n") if "RPCPointProducer" not in line))
    if os.path.exists(rdir + "/BuildFile.xml"):
        edit(rdir + "/BuildFile.xml", lambda xml: re.sub(
            r'<use\s+name="TrackingTools/TrackRefitter"\s*/>\n?', "", xml))

# --- full reco chain without TensorFlow / alignment refit / HLT ------------
# The DNN-based producers need the TensorFlow C++ external: without it, drop
# them (DeepMET, DeepTau/DPFIsolation) together with the TensorFlow
# dependency declarations.
path = "cmssw/RecoMET/METPUSubtraction/plugins"
if os.path.isdir(path) and not with_tensorflow:
    for f in glob.glob(path + "/DeepMETProducer.*"):
        os.remove(f)
    edit(path + "/BuildFile.xml", lambda xml: re.sub(
        r'<use\s+name="PhysicsTools/TensorFlow"\s*/>\n?', "", xml))
rtau = "cmssw/RecoTauTag/RecoTau"
if os.path.isdir(rtau) and not with_tensorflow:
    for f in (glob.glob(rtau + "/src/DeepTauBase.cc")
              + glob.glob(rtau + "/interface/DeepTauBase.h")
              + glob.glob(rtau + "/plugins/DeepTauId.cc")
              + glob.glob(rtau + "/plugins/DPFIsolation.cc")):
        os.remove(f)
    for bf in [rtau + "/BuildFile.xml", rtau + "/plugins/BuildFile.xml"]:
        if os.path.exists(bf):
            edit(bf, lambda xml: re.sub(
                r'<use\s+name="PhysicsTools/TensorFlow"\s*/>\n?', "", xml))

# DeepCore is the jet-core seeding DNN, and it is the only TensorFlow user in
# RecoTracker/TkSeedGenerator/plugins - a library of fifteen other seeding
# producers, including the one that turns pixel proto-tracks into trajectory
# seeds. Without TensorFlow and without this prune the whole library is
# unbuildable and the CKF seeding chain has no seed producer at all.
path = "cmssw/RecoTracker/TkSeedGenerator/plugins"
if os.path.isdir(path) and not with_tensorflow:
    for f in glob.glob(path + "/DeepCoreSeedGenerator.*"):
        os.remove(f)
    # (10_6 has no DeepCore)
    edit(path + "/BuildFile.xml", required=release_cycle >= (11, 0), editor=lambda xml: re.sub(
        r'<use\s+name="PhysicsTools/TensorFlow"\s*/>\n?', "", xml))

# The two-body-decay constrained-refit producers are alignment tools that
# would pull in the Alignment subsystem.
path = "cmssw/RecoTracker/TrackProducer/plugins"
if os.path.isdir(path):
    for f in glob.glob(path + "/TwoBodyDecay*"):
        os.remove(f)
    edit(path + "/BuildFile.xml", lambda xml: re.sub(
        r'<use\s+name="Alignment/[^"]*"\s*/>\n?', "", xml))

# RecoTracker/DeDx: the only HLTrigger/HLTcore user is the HLT filter
# plugin - drop it and the dependency.
for path in ["cmssw/RecoTracker/DeDx/BuildFile.xml",
             "cmssw/RecoTracker/DeDx/plugins/BuildFile.xml"]:
    if os.path.exists(path):
        # (one of the two declares it)
        edit(path, required=False, editor=lambda xml: re.sub(
            r'<use\s+name="HLTrigger/HLTcore"\s*/>\n?', "", xml))
for f in glob.glob("cmssw/RecoTracker/DeDx/plugins/HLTDeDxFilter.*"):
    os.remove(f)

# Several libraries reference edm::HepMCProduct's type info (through the
# GenParticle/GenJet template helpers) without declaring the library that
# defines it; scram resolved it transitively.
for pkg in ["PhysicsTools/UtilAlgos", "RecoJets/JetProducers",
            "RecoTracker/DeDx", "JetMETCorrections/Modules",
            "RecoBTag/Combined", "RecoEgamma/EgammaHLTProducers"]:
    path = "cmssw/%s/BuildFile.xml" % pkg
    if os.path.exists(path):
        # (where it is not declared already)
        edit(path, required=False, editor=lambda xml:
             xml if "GeneratorProducts" in xml
             else '<use   name="SimDataFormats/GeneratorProducts"/>\n' + xml)
path = "cmssw/RecoEgamma/EgammaHLTProducers/BuildFile.xml"
if os.path.exists(path):
    edit(path, lambda xml:
         xml if "TrackingTools/TransientTrack" in xml
         else '<use   name="TrackingTools/TransientTrack"/>\n' + xml)

# the trivial Ecal conditions source writes IOVs through cond::Iov_t but
# (in the 20_1 layout) does not declare the CondCore dependency
path = "cmssw/CalibCalorimetry/EcalTrivialCondModules/BuildFile.xml"
if os.path.exists(path):
    edit(path, lambda xml:
         xml if "CondCore/CondDB" in xml
         else ('<use   name="CondCore/CondDB"/>\n'
               '<use   name="CondCore/DBOutputService"/>\n'
               '<use   name="CondFormats/Alignment"/>\n' + xml))

# --- L1 trigger menu payloads without the utm external (10_6) --------------
# CondFormats/L1TObjects carries the L1TUtm* trigger-menu classes, which wrap
# the CMS utm library. Nothing in the 10_6 reconstruction reads them, and
# they are self-contained (their EventSetup records live in their own files),
# so drop them together with the dependency there. The 20_1 build has utm
# (pkgs/utm.nix): L1Trigger/L1TGlobal and HLTrigger/HLTcore need them.
l1t = "cmssw/CondFormats/L1TObjects"
if release_cycle < (11, 0) and os.path.exists(l1t + "/BuildFile.xml"):
    with open(l1t + "/BuildFile.xml", encoding="latin-1") as f:
        if "utm" in f.read():
            for pat in [l1t + "/interface/*L1TUtm*", l1t + "/src/*L1TUtm*",
                        "cmssw/CondFormats/DataRecord/interface/*L1TUtm*",
                        "cmssw/CondFormats/DataRecord/src/*L1TUtm*"]:
                for f2 in glob.glob(pat):
                    os.remove(f2)
            edit(l1t + "/BuildFile.xml", lambda xml: re.sub(
                r'<use\s+name="utm"\s*/>\n?', "", xml))
            # drop their dictionary entries and headers
            for base, names in [(l1t + "/src", ["classes.h", "classes_def.xml"])]:
                for n in names:
                    p = os.path.join(base, n)
                    if not os.path.exists(p):
                        continue
                    if n.endswith(".xml"):
                        edit(p, lambda xml: re.sub(
                            r'[ \t]*<class[^>]*name\s*=\s*"[^"]*L1TUtm[^"]*"'
                            r'(?:[^>]*/>|[^>]*>.*?</class>)\n?', "", xml, flags=re.DOTALL))
                    else:
                        edit(p, lambda src: "\n".join(
                            l for l in src.split("\n") if "L1TUtm" not in l))

# --- e/gamma & tau without TensorFlow / Triton (all versions) ---------------
# ONNXRuntime and XGBoost are packaged, but the TensorFlow C++ API and the
# Triton inference client are not. Their consumers are a handful of isolated
# files: the DeepSC supercluster clustering, the DeepTau discriminators, the
# DNN muon seeder, and the SONIC (remote-inference) producers.


# the DeepSC clustering: its graph classes live in EgammaCoreTools and are
# used from one method of the supercluster algorithm
ecore = "cmssw/RecoEcal/EgammaCoreTools"
if os.path.exists(ecore + "/interface/EcalClustersGraph.h") and not with_tensorflow:
    for pat in ["/interface/EcalClustersGraph.*", "/src/EcalClustersGraph.*",
                "/interface/DeepSCGraphEvaluation.*", "/src/DeepSCGraphEvaluation.*"]:
        for f in glob.glob(ecore + pat):
            os.remove(f)
    drop_tool_deps(ecore + "/BuildFile.xml", TF_TRITON_DEPS)

    # the producer cache holds the DeepSC graph evaluator; keep its interface
    # (the supercluster producer uses it as its GlobalCache) but refuse the
    # DeepSC clustering mode instead of pulling in TensorFlow
    with open(ecore + "/interface/SCProducerCache.h", "w") as f:
        f.write("""#ifndef RecoEcal_EgammaCoreTools_SCProducerCache_h
#define RecoEcal_EgammaCoreTools_SCProducerCache_h

#include "FWCore/ParameterSet/interface/ParameterSet.h"
#include "FWCore/Utilities/interface/Exception.h"

#include <string>

namespace reco {

  // The DeepSC clustering needs the TensorFlow C++ API, which is not part of
  // this build. The cache type is kept (the supercluster producer declares it
  // as its GlobalCache) but the DeepSC mode is refused.
  class SCProducerCache {
  public:
    SCProducerCache(const edm::ParameterSet& conf) {
      if (conf.getParameter<std::string>("ClusteringType") == "DeepSC")
        throw cms::Exception("Unsupported")
            << "the DeepSC clustering needs the TensorFlow C++ API, "
            << "which is not part of this build";
    }
  };

}  // namespace reco

#endif
""")

    path = "cmssw/RecoEcal/EgammaClusterAlgos/interface/PFECALSuperClusterAlgo.h"
    if os.path.exists(path):
        edit(path, lambda src: "\n".join(
            l for l in src.split("\n")
            if "EcalClustersGraph.h" not in l and "buildAllSuperClustersDeepSC" not in l))
    path = "cmssw/RecoEcal/EgammaClusterAlgos/src/PFECALSuperClusterAlgo.cc"
    if os.path.exists(path):
        def fix_pfecal(src):
            src = src.replace(
                '#include "RecoEcal/EgammaCoreTools/interface/EcalClustersGraph.h"\n', "")
            # the DeepSC branch of the clustering entry point
            src = re.sub(r'\n\s*else if \(_clustype == PFECALSuperClusterAlgo::kDeepSC\)\n'
                         r'\s*buildAllSuperClustersDeepSC\([^;]*\);',
                         '\n  else if (_clustype == PFECALSuperClusterAlgo::kDeepSC)\n'
                         '    throw cms::Exception("Unsupported")\n'
                         '        << "the DeepSC clustering needs the TensorFlow C++ API, '
                         'which is not part of this build";', src)
            # ... and its implementation
            src = re.sub(r'void PFECALSuperClusterAlgo::buildAllSuperClustersDeepSC\(.*?\n\}\n',
                         "", src, flags=re.DOTALL)
            return src
        edit(path, fix_pfecal)

# SONIC (Triton) producers and the DNN-based tau/muon modules. The DNN muon
# seeder goes either way: it also needs the phase-2 track-trigger
# associations (below).
for path, patterns in [
    ("cmssw/RecoEcal/EgammaClusterAlgos", ["/interface/SCEnergyCorrectorDRN.*",
                                           "/src/SCEnergyCorrectorDRN.*"]),
    ("cmssw/RecoEcal/EgammaClusterProducers", ["/src/SCEnergyCorrectorDRNProducer.*"]),
    ("cmssw/RecoEgamma/EgammaTools", ["/plugins/DRNCorrectionProducerT.*"]),
    ("cmssw/RecoTauTag/RecoTau", ["/plugins/DeepTauIdSONIC.cc"] if with_tensorflow else
                                 ["/plugins/DeepTauId*.cc", "/interface/DeepTauId*.h",
                                  "/interface/DeepTauScaling.h"]),
    ("cmssw/RecoMET/METPUSubtraction", ["/plugins/DeepMETSonicProducer.cc"]),
    ("cmssw/RecoMuon/TrackerSeedGenerator", ["/plugins/TSGForOIDNN.*"]),
]:
    if not os.path.isdir(path):
        continue
    for pat in patterns:
        for f in glob.glob(path + pat):
            os.remove(f)
    for bf in [path + "/BuildFile.xml", path + "/plugins/BuildFile.xml"]:
        drop_tool_deps(bf, PRUNED_DEPS)
# the DNN muon seeder was the only user of the phase-2 track-trigger
# associations (which need the conifer external)
drop_tool_deps("cmssw/RecoMuon/TrackerSeedGenerator/BuildFile.xml",
               ["SimTracker/TrackTriggerAssociation"])
drop_tool_deps("cmssw/RecoMuon/TrackerSeedGenerator/plugins/BuildFile.xml",
               ["SimTracker/TrackTriggerAssociation"])

# --- only the serial alpaka backend (all versions) --------------------------
# Libraries flagged ALPAKA_BACKENDS are built once per accelerator backend by
# scram, each with its own ALPAKA_ACC_* defines and namespace. Of the
# backends this build has the serial one, the CPU (gen/cmssw_cmake.py
# builds it, as <library>SerialSync); drop the stanzas that are for the GPU
# backends only (ALPAKA_BACKENDS="cuda", "!serial", ...).
def serial_backend(value):
    value = value.strip()
    if value == "1":
        return True
    if value.startswith("!"):
        return "serial" not in value[1:].split()
    return "serial" in value.split()


def drop_gpu_only_stanza(m):
    flag = re.search(r'ALPAKA_BACKENDS\s*=\s*"([^"]*)"', m.group(0))
    return m.group(0) if serial_backend(flag.group(1)) else ""


for root, dirs, files in os.walk("cmssw"):
    if "BuildFile.xml" not in files:
        continue
    path = os.path.join(root, "BuildFile.xml")
    with open(path, encoding="latin-1") as f:
        xml = f.read()
    if "ALPAKA_BACKENDS" not in xml:
        continue
    edit(path, required=False, editor=lambda x: re.sub(
        r'<library[^>]*>(?:(?!</library>).)*ALPAKA_BACKENDS(?:(?!</library>).)*</library>\n?',
        drop_gpu_only_stanza, x, flags=re.DOTALL))

# The alpaka track classifier of the final track selection evaluates its
# network with PyTorch, which is not packaged (20_1).
path = "cmssw/RecoTracker/FinalTrackSelectors/plugins/BuildFile.xml"
if os.path.exists(path):
    edit(path, required=release_cycle >= (11, 0), editor=lambda x: re.sub(
        r'<library[^>]*name="RecoTrackerFinalTrackSelectorsAlpakaPlugins"[^>]*>(?:(?!</library>).)*</library>\n?',
        "", x, flags=re.DOTALL))

# A couple of plugins BuildFiles (DetectorDescription/Core, Geometry/
# EcalCommonData) place the EDM_PLUGIN flag *outside* the <library> element;
# scram applies it file-wide, our generator per-library. Move it inside so
# the DD algorithms register as plugins.
for root, dirs, files in os.walk("cmssw"):
    if os.path.basename(root) != "plugins" or "BuildFile.xml" not in files:
        continue
    path = os.path.join(root, "BuildFile.xml")
    with open(path, encoding="latin-1") as f:
        xml = f.read()
    if "</library>" not in xml:
        continue
    tail = xml.rsplit("</library>", 1)[-1]
    if not re.search(r"<flags\s+EDM_PLUGIN", tail):
        continue
    xml = xml[: len(xml) - len(tail)] + re.sub(
        r'<flags\s+EDM_PLUGIN="1"\s*/>\n?', "", tail)
    xml = xml.replace("</library>", '  <flags   EDM_PLUGIN="1"/>\n</library>')
    with open(path, "w", encoding="latin-1") as f:
        f.write(xml)

# --- 10_6: dictionaries and dependencies beyond the scope ----------------
if release_cycle < (11, 0):
    # DataFormats/RecoCandidate declares a dependency on
    # SimDataFormats/GeneratorProducts (and through it HepMC) that its library
    # sources don't use; only the dictionary for the sim-truth <-> reco track
    # association maps reaches TrackingParticle (and through it HepMC). Those
    # maps are MC-truth-matching machinery outside the scope of this subset,
    # so drop them instead of dragging in the SimDataFormats/HepMC chain.
    edit(
        "cmssw/DataFormats/RecoCandidate/BuildFile.xml",
        lambda xml: xml.replace('<use   name="SimDataFormats/GeneratorProducts"/>\n', ""),
    )
    edit(
        "cmssw/DataFormats/RecoCandidate/src/classes.h",
        lambda src: src.replace('#include "DataFormats/RecoCandidate/interface/TrackAssociation.h"\n', ""),
    )

    def drop_tracking_particle_dicts(xml):
        lines = [l for l in xml.split("\n") if "TrackingParticle" not in l]
        return "\n".join(lines)

    edit("cmssw/DataFormats/RecoCandidate/src/classes_def.xml", drop_tracking_particle_dicts)

    # TauReco's dictionary header includes two pat:: headers, but none of its
    # classes_def entries use pat types; drop them instead of pulling the
    # whole PatCandidates package (and its CondFormats chain) into the build.
    edit(
        "cmssw/DataFormats/TauReco/src/classes_3.h",
        lambda src: src.replace('#include "DataFormats/PatCandidates/interface/Jet.h"\n', "").replace(
            '#include "DataFormats/PatCandidates/interface/PackedCandidate.h"\n', ""),
    )

    # FeaturesTagInfo only uses edm::RefToBase<reco::Jet>; its pat::Jet
    # include is unused (later CMSSW versions dropped it too) and would pull
    # PatCandidates headers into the dictionary parse at runtime.
    edit(
        "cmssw/DataFormats/BTauReco/interface/FeaturesTagInfo.h",
        lambda src: src.replace(
            '#include "DataFormats/PatCandidates/interface/Jet.h"',
            '#include "DataFormats/JetReco/interface/Jet.h"',
        ),
    )

# --- event generation: Pythia8 without the DIRE/VINCIA/EvtGen externals ------
#
# The 10_6 Pythia8Interface hard-includes the DIRE and VINCIA shower plugins
# (separate externals in the 8.2 era; merged into Pythia in 8.3) and pythia's
# EvtGen adapter. None of the three externals are packaged. The call sites are
# scattered over the whole hadronizer, so instead of pruning them the includes
# are replaced with minimal stubs whose constructors throw: a configuration
# that requests VinciaPlugin/DirePlugin/useEvtGen fails with a clear runtime
# error, everything else runs untouched.
p8i = "cmssw/GeneratorInterface/Pythia8Interface"
if os.path.exists(p8i):
    STUB_COMMON = (
        "#include <map>\n"
        "#include <stdexcept>\n"
        "#include <string>\n"
    )
    EVTGEN_STUB = STUB_COMMON + (
        "// stub for the EvtGen adapter (external not built): fails at\n"
        "// construction, i.e. when a configuration sets useEvtGen\n"
        "class EvtGenDecays {\n"
        "public:\n"
        "  EvtGenDecays(Pythia8::Pythia*, const std::string&, const std::string&) {\n"
        "    throw std::runtime_error(\"EvtGen is not available in this CMSSW build\");\n"
        "  }\n"
        "  void readDecayFile(const std::string&) {}\n"
        "  void decay() {}\n"
        "};\n"
    )
    SHOWER_STUB = STUB_COMMON + (
        "// stubs for the DIRE and VINCIA shower plugins (externals not\n"
        "// built): they fail at construction, i.e. when a configuration\n"
        "// sets DirePlugin/VinciaPlugin\n"
        "namespace Vincia {\n"
        "  struct VinciaPlugin {\n"
        "    VinciaPlugin(Pythia8::Pythia*) {\n"
        "      throw std::runtime_error(\"VINCIA is not available in this CMSSW build\");\n"
        "    }\n"
        "    void init() {}\n"
        "    int nWeights() const { return 0; }\n"
        "    double weight(int) const { return 1.; }\n"
        "    std::string weightLabel(int) const { return std::string(); }\n"
        "  };\n"
        "}\n"
        "namespace Pythia8 {\n"
        "  struct DireStubWeights {\n"
        "    void setup() {}\n"
        "    void calcWeight(double) {}\n"
        "    void reset() {}\n"
        "    double getShowerWeight(const std::string&) { return 1.; }\n"
        "    std::map<std::string, double>* getShowerWeights() { return nullptr; }\n"
        "  };\n"
        "  struct Dire {\n"
        "    Dire() { throw std::runtime_error(\"DIRE is not available in this CMSSW build\"); }\n"
        "    void initSettings(Pythia&) {}\n"
        "    void initShowersAndWeights(Pythia&, void*, void*) {}\n"
        "    void setup(Pythia&) {}\n"
        "    DireStubWeights* weightsPtr = nullptr;\n"
        "  };\n"
        "}\n"
    )

    # the header includes Dire without using any of its types
    edit(p8i + "/interface/Py8InterfaceBase.h",
         lambda src: src.replace("#include <Dire/Dire.h>\n", ""))

    # From 11_x on the interface declares the adapter as Pythia8::EvtGenDecays
    # (where Pythia 8.3 puts it) and includes it from more files.
    if release_cycle >= (11, 0):
        EVTGEN_STUB = (STUB_COMMON + "namespace Pythia8 {\n"
                       + EVTGEN_STUB[len(STUB_COMMON):] + "}\n")
    for root, _, files in os.walk(p8i):
        for name in files:
            if name.endswith(".cc"):
                # at the start of a line: some files carry it commented out
                edit(os.path.join(root, name), required=False,
                     editor=lambda src: re.sub(r'^#include "Pythia8Plugins/EvtGen.h"\n',
                                        lambda m: EVTGEN_STUB, src, flags=re.M))

    def _stub_hadronizer(src):
        src = src.replace('#include "Vincia/Vincia.h"\n#include "Dire/Dire.h"\n',
                          SHOWER_STUB)
        return src
    # (10_6: Pythia 8.3 has VINCIA built in, and 20_1 no DIRE)
    edit(p8i + "/plugins/Pythia8Hadronizer.cc", _stub_hadronizer, required=release_cycle < (11, 0))

    for bf in [p8i + "/BuildFile.xml", p8i + "/plugins/BuildFile.xml"]:
        drop_tool_deps(bf, ["evtgen", "dire", "vincia"])

    # the LHE reader's mcdb:// support and the HepML metadata need externals
    # that are not packaged; the deps are only used by those code paths
    lhe = "cmssw/GeneratorInterface/LHEInterface"
    for bf in [lhe + "/BuildFile.xml", lhe + "/plugins/BuildFile.xml"]:
        drop_tool_deps(bf, ["mcdb", "libhepml"])

    # base-classes-only decay interfaces (the concrete implementations in
    # plugins/ link the externals; no_plugins in the configuration). Tauola++
    # is there when the build has it (--with-tauolapp).
    drop_tool_deps("cmssw/GeneratorInterface/EvtGenInterface/BuildFile.xml", ["evtgen"])
    if not with_tauolapp:
        drop_tool_deps("cmssw/GeneratorInterface/TauolaInterface/BuildFile.xml", ["tauolapp"])

    # LHAPDF 6.4 no longer carries the PDFLIB-era pdfset_ glue symbol this
    # linker-bait references (it exists only to force the archive lhapdf
    # library in; ours is shared)
    edit("cmssw/GeneratorInterface/Core/src/FortranInstance.cc",
         lambda src: src.replace(
             'extern "C" void pdfset_(void);\n'
             '__attribute__((visibility("hidden"))) void dummy()\n'
             '{\n'
             '  pdfset_();\n'
             '}\n', "").replace(
             'extern "C" void pdfset_(void);\n'
             '__attribute__((visibility("hidden"))) void dummy() { pdfset_(); }\n', ""))

    # PhysicsTools/NanoAOD: the flat-table producers (NanoGen and nanoAOD
    # production). In 10_6, two plugins are pruned: the nano DQM module (the
    # DQM subsystem is not built there) and the b-jet energy-regression MVA
    # (its base template lives in PhysicsTools/PatAlgos, not built there).
    # The TensorFlow dependency of the plugins BuildFile is stale in 10_6 -
    # nothing in the package includes it.
    nano = "cmssw/PhysicsTools/NanoAOD"
    if os.path.exists(nano) and release_cycle < (11, 0):
        for f in ["/plugins/NanoAODDQM.cc", "/plugins/BJetEnergyRegressionMVA.cc"]:
            if os.path.exists(nano + f):
                os.remove(nano + f)
        drop_tool_deps(nano + "/plugins/BuildFile.xml",
                       ["DQMServices/Core", "PhysicsTools/TensorFlow"])

    # GeneratorInterface/PartonShowerVeto: keep only the fastjet-based MLM
    # matching (JetMatchingMGFastJet, the production scheme for
    # Madgraph+Pythia8). The classic Madgraph/Alpgen matchers drive fortran
    # code (ME2pythia.f, alpg_match.F) and the pythia6/alpgen externals.
    psv = "cmssw/GeneratorInterface/PartonShowerVeto"
    if os.path.exists(psv):
        for f in ["/src/JetMatchingMadgraph.cc", "/src/JetMatchingAlpgen.cc"]:
            if os.path.exists(psv + f):
                os.remove(psv + f)
        drop_tool_deps(psv + "/BuildFile.xml",
                       ["GeneratorInterface/Pythia6Interface",
                        "GeneratorInterface/AlpgenInterface", "f77compiler", "pythia6"])

        def _prune_matchers(src):
            # the base-class header used to come in through the matcher headers
            src = src.replace(
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatchingMadgraph.h"\n',
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatching.h"\n')
            src = src.replace(
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatchingAlpgen.h"\n', "")
            for new in ["matching.reset(new JetMatchingMadgraph(params));",
                        "matching = std::make_unique<JetMatchingMadgraph>(params);"]:
                src = src.replace(new, "matching.reset(new JetMatchingMadgraph(params));")
            for new in ["matching.reset(new JetMatchingAlpgen(params));",
                        "matching = std::make_unique<JetMatchingAlpgen>(params);"]:
                src = src.replace(new, "matching.reset(new JetMatchingAlpgen(params));")
            src = src.replace(
                "matching.reset(new JetMatchingMadgraph(params));",
                'throw cms::Exception("InvalidJetMatching")\n'
                '            << "The fortran-based Madgraph matching is not available in this build";')
            src = src.replace(
                "matching.reset(new JetMatchingAlpgen(params));",
                'throw cms::Exception("InvalidJetMatching")\n'
                '            << "Alpgen matching is not available in this build";')
            return src
        edit(psv + "/src/JetMatching.cc", _prune_matchers)

        def _prune_hook(src):
            src = src.replace(
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatchingMadgraph.h"\n', "")
            src = src.replace(
                "fJetMatching = new JetMatchingMadgraph(ps);",
                'throw cms::Exception("InvalidJetMatching")\n'
                '         << "The fortran-based Madgraph matching is not available in this build; "\n'
                '         << "use scheme = MadgraphFastJet";')
            return src
        edit("cmssw/GeneratorInterface/Pythia8Interface/plugins/JetMatchingHook.cc", _prune_hook)


    # JetMatchingMGFastJet declares the MEMAIN/UPPRIV/OUTTREE fortran common
    # blocks extern; their definitions lived in the fortran files we do not
    # compile. The fortran side is gone, so define them here instead.
    edit(psv + "/src/JetMatchingMGFastJet.cc",
         lambda src: src.replace("extern struct", "struct"))

    # The HEPEVT fortran common block, used through HepMC's HEPEVT_Wrapper by
    # the legacy jet-matching input converter (Py8toJetInput). In a scram
    # build the fortran generator objects allocate it; this build compiles no
    # fortran, so define the symbol here. The size must match the
    # HEPEVT_EntriesAllocation (200000) that HepMC itself was compiled with.
    with open(p8i + "/src/HepevtCommonBlock.cc", "w") as f:
        f.write(
            "// see gen/prepare: the HEPEVT/HEPRUP/HEPEUP fortran common\n"
            "// blocks, normally allocated by fortran generator objects that this\n"
            "// build does not have\n"
            "#include <cstddef>\n"
            "#include \"SimDataFormats/GeneratorProducts/interface/LHECommonBlocks.h\"\n"
            "namespace {\n"
            "  constexpr std::size_t kEntries = 200000;  // HepMC's HEPEVT_EntriesAllocation\n"
            "}\n"
            "extern \"C\" {\n"
            "  alignas(16) char hepevt_[sizeof(long int) * (2 + 6 * kEntries) +\n"
            "                           sizeof(double) * (9 * kEntries)];\n"
            "  HEPRUP_ heprup_;\n"
            "  HEPEUP_ hepeup_;\n"
            "}\n")

    # ... and the fio half of HepMC 2 is linked only here, where the fortran
    # commons it references are defined (see the hepmcfio tool note in
    # gen/CMakeLists.txt)
    edit(p8i + "/plugins/BuildFile.xml",
         lambda xml: xml if "hepmcfio" in xml else xml.replace(
             '<use   name="GeneratorInterface/Pythia8Interface"/>',
             '<use   name="GeneratorInterface/Pythia8Interface"/>\n<use   name="hepmcfio"/>'))

    # the nanoAOD plugins use GenEventInfoProduct but the BuildFile misses
    # the link dependency (scram resolved it transitively)
    # (10_6: 20_1 declares it)
    edit(nano + "/plugins/BuildFile.xml", required=release_cycle < (11, 0),
         editor=lambda xml: xml if "SimDataFormats/GeneratorProducts" in xml else xml.replace(
             '<use   name="FWCore/Framework"/>',
             '<use   name="FWCore/Framework"/>\n<use   name="SimDataFormats/GeneratorProducts"/>'))

# --- the PAT MVA producers without TensorFlow (20_1) ------------------------
# BaseMVAValueMapProducer, the template behind the PAT and NanoAOD MVA value
# maps, evaluates with TMVA, ONNXRuntime or TensorFlow. The TensorFlow C++
# API is not packaged: drop that backend, so a configuration asking for it
# fails when the module is constructed, and keep the other two.
path = "cmssw/PhysicsTools/PatAlgos/interface/BaseMVAValueMapProducer.h"
if os.path.exists(path) and not with_tensorflow:
    def no_tensorflow(src):
        src = src.replace('#include "PhysicsTools/TensorFlow/interface/TensorFlow.h"\n',
                          '#include "FWCore/Utilities/interface/Exception.h"\n')
        src = src.replace(
            "      graph_.reset(tensorflow::loadGraphDef(model_path));\n"
            "      tf_session_ = tensorflow::createSession(graph_.get());\n",
            '      throw cms::Exception("Configuration")\n'
            '          << "the TF backend needs the TensorFlow C++ API, which is not part of this build";\n')
        src = src.replace("  ~BaseMVACache() { tensorflow::closeSession(tf_session_); }\n", "")
        src = src.replace("  tensorflow::Session* getTFSession() const { return tf_session_; }\n", "")
        src = src.replace("  std::shared_ptr<tensorflow::GraphDef> graph_;\n", "")
        src = src.replace("  tensorflow::Session* tf_session_ = nullptr;\n", "")
        # the evaluation branches: "if (tf_) {...} else if (onnx_) {" twice
        src, n = re.subn(r"if \(tf_\) \{.*?\} else if \(onnx_\) \{", "if (onnx_) {", src,
                         flags=re.DOTALL)
        if n != 2 or "tensorflow::" in src:
            raise SystemExit("BaseMVAValueMapProducer.h: TensorFlow code not where expected")
        return src
    edit(path, no_tensorflow)
    drop_tool_deps("cmssw/PhysicsTools/PatAlgos/BuildFile.xml", ["PhysicsTools/TensorFlow"])

# --- NanoAOD without TauSpinner and the displaced-tau DNN (all versions) ---
# The tau-spin weight table producer drives the Tauola++ TauSpinner library
# (the only Tauola++ user in the package), and the displaced-tau tagger
# evaluates a TensorFlow graph: unless the build has the externals
# (--with-tauolapp, --with-tensorflow).
nano = "cmssw/PhysicsTools/NanoAOD"
if os.path.exists(nano + "/plugins/TauSpinnerTableProducer.cc") and not with_tauolapp:
    os.remove(nano + "/plugins/TauSpinnerTableProducer.cc")
    drop_tool_deps(nano + "/plugins/BuildFile.xml", ["tauolapp"])
if os.path.exists(nano + "/plugins/DisTauTag.cc") and not with_tensorflow:
    os.remove(nano + "/plugins/DisTauTag.cc")

# --- b-tagging DNNs without the Triton client (20_1) ------------------------
# RecoBTag/ONNXRuntime evaluates the ParticleNet / ParticleTransformer
# taggers in process with ONNXRuntime; its *Sonic* producers are the same
# taggers offloaded to a Triton inference server, whose client is not
# packaged.
path = "cmssw/RecoBTag/ONNXRuntime/plugins"
if glob.glob(path + "/*Sonic*.cc"):
    for f in glob.glob(path + "/*Sonic*.cc"):
        os.remove(f)
    drop_tool_deps(path + "/BuildFile.xml", PRUNED_DEPS)

# --- the EMTF emulator library without TensorFlow (20_1) --------------------
# L1Trigger/L1TMuonEndCap lists PhysicsTools/TensorFlow among its
# dependencies, but none of its code uses it. EventFilter/L1TRawToDigi's
# EMTF unpacker needs the library (the track and hit helpers).
drop_tool_deps("cmssw/L1Trigger/L1TMuonEndCap/BuildFile.xml", ["PhysicsTools/TensorFlow"])

# --- packages kept as configuration only -----------------------------------

# The MPI accelerator (20_1): Configuration/StandardSequences/python/
# Accelerators_cff.py, which every unpacker configuration with an alpaka
# variant imports, defines the MPI process accelerator next to the CUDA, ROCm
# and alpaka ones. Its python only sets an environment variable when an
# MPIService is configured; the service itself needs an MPI implementation,
# which is not packaged.
python_only("HeterogeneousCore/MPIServices")
# The legacy CSC track finder (20_1): L1Trigger/L1TMuon/python/simDigis_cff.py,
# where the Stage-2 muon emulators are defined, imports its cfis for the
# pre-2016 trigger. The library needs the CSCTrackFinderEmulation external,
# which is not packaged. RecoMET's CSC halo code uses one of its headers
# (inline lookup tables), which is why python_only keeps them.
python_only("L1Trigger/CSCTrackFinder")
# The L1 ntuples link it for their CSCTF tree; the standard sequences only
# import their configuration (DQMOffline/L1Trigger's jet and sum monitor).
python_only("L1Trigger/L1TNtuples")
# Its two monitors in DQM/L1TMonitor, of that trigger and of its emulation,
# use its lookup tables' code: without them.
l1tmon = "cmssw/DQM/L1TMonitor"
if os.path.exists(l1tmon + "/src/L1TCSCTF.cc"):
    for name in ("L1TCSCTF", "L1TdeCSCTF"):
        os.remove(f"{l1tmon}/src/{name}.cc")
        os.remove(f"{l1tmon}/interface/{name}.h")
        edit(l1tmon + "/plugins/SealModule.cc", lambda src: src.replace(
            f'#include "DQM/L1TMonitor/interface/{name}.h"\n', "").replace(
            f"DEFINE_FWK_MODULE({name});\n", ""))
    drop_tool_deps(l1tmon + "/BuildFile.xml", ["L1Trigger/CSCTrackFinder"])
# The legacy HLT muon L1 filter decodes one field of the CSCTF pt LUT address
# through its data types, whose decoding is out of line in the library:
# decode the 4 bits inline and the link goes.
hltl1 = "cmssw/HLTrigger/Muon/plugins/HLTMuonL1Filter"
if os.path.exists(hltl1 + ".cc"):
    edit(hltl1 + ".h", lambda src: src.replace(
        '#include "L1Trigger/CSCTrackFinder/interface/CSCTrackFinderDataTypes.h"\n', ""))
    edit(hltl1 + ".cc", lambda src: src.replace(
        "      ptadd thePtAddress(trk->first.ptLUTAddress());\n"
        "      csctfMode = thePtAddress.track_mode;\n",
        "      // the track mode: bits 16-19 of the pt LUT address (pt_address)\n"
        "      csctfMode = (trk->first.ptLUTAddress() >> 16) & 0xf;\n"))
drop_tool_deps("cmssw/HLTrigger/Muon/plugins/BuildFile.xml", ["L1Trigger/CSCTrackFinder"])
# The Phase-2 L1 particle-flow trigger and track matching, and the L1 DQM
# that monitors them (20_1): the standard sequences import their
# configuration under the Phase-2 modifiers; their code needs the conifer
# BDT external. SONIC's Triton client (the producers' remote-inference
# variants, behind process modifiers) likewise.
for pkg in ("L1Trigger/Phase2L1ParticleFlow", "L1Trigger/L1TTrackMatch",
            "DQMOffline/L1Trigger", "HeterogeneousCore/SonicTriton"):
    python_only(pkg)

# --- the PPS proton transport without Hector (20_1) ------------------------
# Every GEN-SIM step since 2016 schedules LHCTransport, which carries the
# protons to the PPS stations. It has three methods; Run 3 (ctpps_2022) uses
# the optical functions, only the 2016-2018 eras Hector, an external that is
# not packaged. Without it, asking for Hector is a configuration error. (So
# is Utilities/PPS's library, whose one function only Hector's transport
# calls; the unit conversions the others use are a header.)
ppst = "cmssw/SimTransport/PPSProtonTransport"
if os.path.exists(ppst + "/src/HectorTransport.cc"):
    os.remove(ppst + "/src/HectorTransport.cc")
    os.remove(ppst + "/interface/HectorTransport.h")
    # (10_6 builds no proton transport, and its transport is written differently)
    edit(ppst + "/src/ProtonTransport.cc", required=release_cycle >= (11, 0), editor=lambda src: src.replace(
        '#include "SimTransport/PPSProtonTransport/interface/HectorTransport.h"\n', "").replace(
        "    instance_ = std::make_unique<HectorTransport>(iConfig, iC);\n",
        '    throw cms::Exception("ProtonTransport") << "This build has no Hector: use the optical functions";\n'))
    for bf in (ppst + "/BuildFile.xml", "cmssw/SimPPS/PPSSimTrackProducer/plugins/BuildFile.xml"):
        drop_tool_deps(bf, ["hector", "Utilities/PPS"])

# --- the FastSim decayer without Pythia 6 (20_1) ----------------------------
# FastSimulation/ParticleDecay decays with Pythia 8 alone since Pythia 6 left
# the release, but its BuildFile still asks for Pythia 6's particle data
# (pydata) and the Fortran compiler that came with it.
path = "cmssw/FastSimulation/ParticleDecay"
if os.path.exists(path + "/src/PythiaDecays.cc") and "pydata" not in open(path + "/src/PythiaDecays.cc").read():
    drop_tool_deps(path + "/BuildFile.xml", ["pydata", "f77compiler"])
