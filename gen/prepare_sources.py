"""Small source-tree adjustments before generating the CMake files.

Run from the directory that contains the cmssw/ source tree, with the CMSSW
version string as argument (e.g. CMSSW_10_6_30). Common to all versions:

* Reduce FWCore/Framework/bin/BuildFile.xml to just the plain cmsRun binary
  (upstream also defines cmsRunTC, cmsRunJE, ... linked against different
  allocators/profilers).
* Drop the CondorStatusService plugin: it is only useful on HTCondor grid
  nodes and is the sole reason the services plugin library depends on the
  xrootd-based XrdAdaptor, which we don't build.

plus a few version-specific fixups, see below.
"""
import glob
import os
import re
import shutil
import sys

version = sys.argv[1] if len(sys.argv) > 1 else "CMSSW_20_1_0"
release_cycle = tuple(int(x) for x in version.split("_")[1:3])


def edit(path, editor):
    with open(path) as f:
        content = f.read()
    content = editor(content)
    with open(path, "w") as f:
        f.write(content)


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
        edit(path, lambda xml: xml.replace('<use   name="Utilities/XrdAdaptor"/>\n', "").replace(
            '<use name="FWStorage/XrdAdaptor"/>\n', ""))

# ... and don't load the pruned plugins as default cmsRun services
path = "cmssw/FWCore/Framework/src/defaultCmsRunServices.cc"


def drop_default_services(src):
    for service in ["CondorStatusService", "XrdAdaptor::XrdStatisticsService", "XrdStatisticsService"]:
        src = re.sub(r',\s*"' + re.escape(service) + r'"', "", src)
        src = re.sub(r'"' + re.escape(service) + r'"\s*,', "", src)
    return src


edit(path, drop_default_services)

# --- eos portable archive vs modern boost (all versions) --------------------
# CondFormats/Serialization's bundled eos portable archive selects boost
# spirit's private endian/fpclassify headers for boost >= 1.48, but those
# were removed in boost 1.69. Map the usage onto the modern boost.endian /
# boost.math equivalents. The files are CRLF + latin-1 encoded, so they
# get their own editor.
endian_shim = "\r\n".join([
    "#ifndef EOS_ENDIAN_COMPAT_SHIM",
    "#define EOS_ENDIAN_COMPAT_SHIM",
    "namespace eos_endian_compat {",
    "  template <typename T, std::size_t N>",
    "  inline T load_little_endian(const void* bytes) {",
    "    T t;",
    "    std::memcpy(&t, bytes, sizeof(T));",
    "    return boost::endian::little_to_native(t);",
    "  }",
    "  template <typename T, std::size_t N>",
    "  inline void store_little_endian(void* bytes, T t) {",
    "    t = boost::endian::native_to_little(t);",
    "    std::memcpy(bytes, &t, sizeof(T));",
    "  }",
    "}",
    "#endif",
    "",
    "",
])

# the subset of Johan Rade's fp_utilities (the spirit copy of which the
# archives used) that they actually need: the IEEE754 bit masks and
# raw-bit access, plus isfinite/fpclassify
fp_shim = "\r\n".join([
    "#ifndef EOS_FP_COMPAT_SHIM",
    "#define EOS_FP_COMPAT_SHIM",
    "namespace eos_fp_compat {",
    "  template <typename T> inline bool isfinite(T t) { return std::isfinite(t); }",
    "  template <typename T> inline int fpclassify(T t) { return std::fpclassify(t); }",
    "  namespace detail {",
    "    template <typename T> struct fp_traits_compat;",
    "    template <> struct fp_traits_compat<float> {",
    "      typedef std::uint32_t bits;",
    "      static constexpr bits sign     = 0x80000000u;",
    "      static constexpr bits exponent = 0x7f800000u;",
    "      static constexpr bits mantissa = 0x007fffffu;",
    "      static void get_bits(float x, bits& b) { std::memcpy(&b, &x, sizeof(b)); }",
    "      static void set_bits(float& x, bits b) { std::memcpy(&x, &b, sizeof(b)); }",
    "    };",
    "    template <> struct fp_traits_compat<double> {",
    "      typedef std::uint64_t bits;",
    "      static constexpr bits sign     = 0x8000000000000000ull;",
    "      static constexpr bits exponent = 0x7ff0000000000000ull;",
    "      static constexpr bits mantissa = 0x000fffffffffffffull;",
    "      static void get_bits(double x, bits& b) { std::memcpy(&b, &x, sizeof(b)); }",
    "      static void set_bits(double& x, bits b) { std::memcpy(&x, &b, sizeof(b)); }",
    "    };",
    "    template <typename T> struct fp_traits { typedef fp_traits_compat<T> type; };",
    "  }",
    "}",
    "#endif",
    "",
    "",
])

def fix_eos_portable_archive(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="latin-1", newline="") as f:
        src = f.read()
    orig = src

    # 10_6-era copies still select boost spirit's private endian/fpclassify
    # headers (removed in boost 1.69); the 20_1-era copies were already ported
    # upstream and don't have this marker.
    if "boost/spirit/home/support/detail/endian" in src:
        src = src.replace(
            "#include <boost/spirit/home/support/detail/endian/endian.hpp>",
            "#include <boost/endian/conversion.hpp>\r\n#include <cstring>",
        )
        # both branches of the version ladder; only the >= 1.48 one is active
        src = src.replace(
            "#include <boost/spirit/home/support/detail/math/fpclassify.hpp>",
            "#include <cmath>\r\n#include <cstdint>",
        )
        src = src.replace(
            "namespace fp = boost::spirit::math;",
            fp_shim + "namespace fp = eos_fp_compat;",
        )
        src = src.replace(
            "namespace endian = boost::spirit::detail;",
            endian_shim + "namespace endian = eos_endian_compat;",
        )

    # boost >= 1.89 made the strong typedefs' base_type private (all copies
    # of the iarchive still use it for loading); mirror what the save() side
    # has always done and go through an unsigned integer of the same size,
    # using the public conversion operator and constructor.
    if "static_cast<T::base_type" in src or "boost::uint_t" in src:
        if "#include <boost/integer.hpp>" not in src:
            src = src.replace(
                "#include <boost/version.hpp>",
                "#include <boost/version.hpp>\r\n#include <boost/integer.hpp>\r\n#include <climits>",
                1,
            )
        src = src.replace(
            "      load(static_cast<T::base_type&>(t));",
            "      typename boost::uint_t<sizeof(T) * CHAR_BIT>::least v = 0;\r\n"
            "      load(v);\r\n"
            "      t = T(v);",
        )

    if src != orig:
        with open(path, "w", encoding="latin-1", newline="") as f:
            f.write(src)

fix_eos_portable_archive("cmssw/CondFormats/Serialization/interface/eos/portable_iarchive.hpp")
fix_eos_portable_archive("cmssw/CondFormats/Serialization/interface/eos/portable_oarchive.hpp")


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
    edit(path, lambda xml: re.sub(
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
    edit(path, lambda xml: xml.replace(
        '<use   name="RecoMET/METAlgorithms"/>',
        '<use   name="RecoLocalCalo/EcalRecAlgos"/>\n'
        '<use   name="DataFormats/TrackReco"/>'))

# The Ecal uncalibrated-rec-hit workers use the EB/EE pulse shapes from
# SimCalorimetry/EcalSimAlgos; scram got that library transitively through
# the EcalTPGTools dependency pruned above - declare it directly.
path = "cmssw/RecoLocalCalo/EcalRecProducers/plugins/BuildFile.xml"
if os.path.exists(path):
    edit(path, lambda xml: xml.replace(
        '<use   name="CalibCalorimetry/EcalTPGTools"/>',
        '<use   name="CalibCalorimetry/EcalTPGTools"/>\n'
        '<use   name="SimCalorimetry/EcalSimAlgos"/>'))
path = "cmssw/CalibCalorimetry/EcalTPGTools/BuildFile.xml"
if os.path.exists(path):
    edit(path, lambda xml: re.sub(
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

# The method-2 HBHE pulse fit (HybridMinimizer) uses the MnPrint logging API
# that ROOT dropped in 6.24: the MN_* message macros become no-ops (they are
# minimizer debug prints) and the static level setter got renamed.
path = "cmssw/RecoLocalCalo/HcalRecAlgos/src/HybridMinimizer.cc"
if os.path.exists(path):
    def fix_mnprint(src):
        if "MN_INFO_MSG" not in src:
            return src
        shim = ("\n// compatibility with the ROOT >= 6.24 MnPrint API\n"
                "#define MN_INFO_MSG(str)\n"
                "#define MN_ERROR_MSG(str)\n"
                "#define MN_INFO_MSG2(loc, str)\n"
                "#define MN_ERROR_MSG2(loc, str)\n"
                "#define MN_INFO_VAL2(loc, x)\n"
                "#define MN_ERROR_VAL2(loc, x)\n")
        src = src.replace('#include "Minuit2/MnPrint.h"',
                          '#include "Minuit2/MnPrint.h"' + shim)
        src = src.replace("MnPrint::SetLevel(", "MnPrint::SetGlobalLevel(")
        return src
    edit(path, fix_mnprint)

# The DD-algorithm plugin BuildFiles (Geometry/*CommonData) build a second
# plugin library against dd4hep for the DD4hep-based geometry variant; only
# the classic DDD one is in scope.
for root, dirs, files in os.walk("cmssw/Geometry"):
    if "BuildFile.xml" in files and root.endswith("plugins"):
        edit(os.path.join(root, "BuildFile.xml"), lambda xml: re.sub(
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
        edit(os.path.join(root, "BuildFile.xml"), lambda xml: re.sub(
            r'<library[^>]*>(?:(?!</library>).)*name="Fireworks/Core"'
            r'(?:(?!</library>).)*</library>\n?',
            "", xml, flags=re.DOTALL))
        # ... and the DD4hep test plugins, which use the DDCMS classes
        # without declaring the dependency
        edit(os.path.join(root, "BuildFile.xml"), lambda xml: re.sub(
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
# The DNN-based producers need the TensorFlow C++ external, which we do not
# build: drop them (DeepMET, DeepTau/DPFIsolation) together with the
# TensorFlow dependency declarations.
path = "cmssw/RecoMET/METPUSubtraction/plugins"
if os.path.isdir(path):
    for f in glob.glob(path + "/DeepMETProducer.*"):
        os.remove(f)
    edit(path + "/BuildFile.xml", lambda xml: re.sub(
        r'<use\s+name="PhysicsTools/TensorFlow"\s*/>\n?', "", xml))
rtau = "cmssw/RecoTauTag/RecoTau"
if os.path.isdir(rtau):
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
# seeds. Without this prune the whole library is unbuildable and the CKF
# seeding chain has no seed producer at all.
path = "cmssw/RecoTracker/TkSeedGenerator/plugins"
if os.path.isdir(path):
    for f in glob.glob(path + "/DeepCoreSeedGenerator.*"):
        os.remove(f)
    edit(path + "/BuildFile.xml", lambda xml: re.sub(
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
        edit(path, lambda xml: re.sub(
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
        edit(path, lambda xml:
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

# SiPixelQualityESProducer dereferences the DetVOff payload even when the
# SiPixelDetVOffRcd is not in its merge list (running without a conditions
# DB there is nothing to provide it from).
path = "cmssw/CalibTracker/SiPixelESProducers/plugins/SiPixelQualityESProducer.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace(
        "dbptr->add(Voff.product());",
        "if (Voff.isValid())\n    dbptr->add(Voff.product());"))

# --- e/gamma & tau without TensorFlow / Triton (all versions) ---------------
# ONNXRuntime and XGBoost are packaged, but the TensorFlow C++ API and the
# Triton inference client are not. Their consumers are a handful of isolated
# files: the DeepSC supercluster clustering, the DeepTau discriminators, the
# DNN muon seeder, and the SONIC (remote-inference) producers.
def drop_tool_deps(path, deps):
    if not os.path.exists(path):
        return
    edit(path, lambda xml: re.sub(
        r'<use\s+name="(?:' + "|".join(re.escape(d) for d in deps) + r')"\s*/>\n?',
        "", xml))


TF_TRITON_DEPS = ["PhysicsTools/TensorFlow", "HeterogeneousCore/SonicTriton",
                  "HeterogeneousCore/SonicCore", "tensorflow-cc",
                  "triton-inference-client"]

# the DeepSC clustering: its graph classes live in EgammaCoreTools and are
# used from one method of the supercluster algorithm
ecore = "cmssw/RecoEcal/EgammaCoreTools"
if os.path.exists(ecore + "/interface/EcalClustersGraph.h"):
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

# SONIC (Triton) producers and the DNN-based tau/muon modules
for path, patterns in [
    ("cmssw/RecoEcal/EgammaClusterAlgos", ["/interface/SCEnergyCorrectorDRN.*",
                                           "/src/SCEnergyCorrectorDRN.*"]),
    ("cmssw/RecoEcal/EgammaClusterProducers", ["/src/SCEnergyCorrectorDRNProducer.*"]),
    ("cmssw/RecoEgamma/EgammaTools", ["/plugins/DRNCorrectionProducerT.*"]),
    ("cmssw/RecoTauTag/RecoTau", ["/plugins/DeepTauId*.cc", "/interface/DeepTauId*.h",
                                  "/interface/DeepTauScaling.h"]),
    ("cmssw/RecoMuon/TrackerSeedGenerator", ["/plugins/TSGForOIDNN.*"]),
]:
    if not os.path.isdir(path):
        continue
    for pat in patterns:
        for f in glob.glob(path + pat):
            os.remove(f)
    for bf in [path + "/BuildFile.xml", path + "/plugins/BuildFile.xml"]:
        drop_tool_deps(bf, TF_TRITON_DEPS)
# the DNN muon seeder was the only user of the phase-2 track-trigger
# associations (which need the conifer external)
drop_tool_deps("cmssw/RecoMuon/TrackerSeedGenerator/BuildFile.xml",
               ["SimTracker/TrackTriggerAssociation"])
drop_tool_deps("cmssw/RecoMuon/TrackerSeedGenerator/plugins/BuildFile.xml",
               ["SimTracker/TrackTriggerAssociation"])

# --- no alpaka backend variants (all versions) ------------------------------
# Libraries flagged ALPAKA_BACKENDS are built once per accelerator backend by
# scram, each with its own ALPAKA_ACC_* defines and namespace. We build the
# host code only, so drop those stanzas (their sources live in alpaka/
# subdirectories, which the generator already keeps out of the plain globs).
for root, dirs, files in os.walk("cmssw"):
    if "BuildFile.xml" not in files:
        continue
    path = os.path.join(root, "BuildFile.xml")
    with open(path, encoding="latin-1") as f:
        xml = f.read()
    if "ALPAKA_BACKENDS" not in xml:
        continue
    edit(path, lambda x: re.sub(
        r'<library[^>]*>(?:(?!</library>).)*ALPAKA_BACKENDS(?:(?!</library>).)*</library>\n?',
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

# The serialization generator crashes under python 3 when no -v is given
# (None < 1 comparison), and it insists on scram's $CMSSW_BASE/src/... layout;
# our tree calls the source directory "cmssw" instead of "src".
path = "cmssw/CondFormats/Serialization/python/condformats_serialization_generate.py"
if os.path.exists(path):
    def fix_serialization_generator(src):
        # the layout relaxation is needed for every version of the script ...
        src = src.replace("if self.split_path[0] != 'src':",
                          "if self.split_path[0] not in ('src', 'cmssw'):")
        # ... while the python-3 fixes below were applied upstream at some
        # point (the 20_1 copy has them, the 10_6 one does not) - gate each on
        # its marker so both versions come out right
        if "default=0" not in src:
            src = src.replace("action='count', help=", "action='count', default=0, help=")
        if ".decode(" not in src:
            src = src.replace("subprocess.check_output(command, shell=True)",
                              "subprocess.check_output(command, shell=True, universal_newlines=True)")
        src = src.replace("with open(filename, 'wb') as fd:", "with open(filename, 'w') as fd:")
        if "fd.read().decode" not in src:
            # latin-1 is byte-preserving, so clang's byte offsets stay valid
            src = src.replace("        source = fd.read()",
                              "        source = fd.read().decode('latin-1')")
        return src

    edit(path, fix_serialization_generator)

if release_cycle >= (20, 0):
    # --- ROOT 6.40 compatibility ---------------------------------------------

    # With ROOT 6.40 (CMSSW_20_1_0_pre2 targets 6.36), TTree::SetCacheSizeAux
    # emits a benign "Not setting up an automatically sized TTreeCache" error
    # when PoolSource opens a file; keep InitRootHandlers from making it fatal.
    def whitelist_ttreecache_message(src):
        assert "const, 12> in_message{" in src
        src = src.replace("const, 12> in_message{", "const, 13> in_message{")
        src = src.replace(
            '{"no dictionary for class",',
            '{"Not setting up an automatically sized TTreeCache",\n       "no dictionary for class",',
        )
        return src

    edit("cmssw/FWCore/Services/plugins/InitRootHandlers.cc", whitelist_ttreecache_message)

    # --- ECAL component shapes only when component digis are asked for -------
    # EcalDigiProducer builds its ComponentShapeCollection through the
    # ComponentShapeCollection(iC) delegate, which hard-codes useDBShape=true,
    # and accumulate() calls setEventSetup on it for every event in which the
    # barrel is digitised. Both happen regardless of componentSeparateDigi -
    # the parameter that decides whether the component shapes are used at all.
    #
    # They are not used otherwise. EBHitResponseImpl reaches shapes() only in
    # the else of `if (!m_isComponentShapeBased)` (EBHitResponse.icc:139), and
    # of the three responses EcalDigiProducer builds, only m_ComponentResponse
    # passes doComponent=true - and it is a nullptr unless componentSeparateDigi
    # is set, which nothing but the ecal_component era modifiers do.
    #
    # So in the default configuration the collection is filled from
    # EcalSimComponentShapeRcd and then never read. That is fatal here: the
    # only producer of that record in this build is
    # EcalTrivialConditionRetriever (producedEcalSimComponentShape defaults to
    # true), and its EBSimComponentShapeFiles list is empty, because the 23
    # per-depth shape files are in no cms-data package and the conditions
    # database is not reachable from here. It therefore delivers a payload
    # with no shapes in it and ComponentShape::fillShape dies on
    # barrel_shapes.at(0), which is what keeps examples/MuonGunDigi's
    # calorimeter job 10_6-only.
    #
    # Tie the DB lookup to the switch that decides whether its result is read.
    # With componentSeparateDigi off, ComponentShape takes its useDB=false
    # branch - which upstream provides for exactly this case ("fill with dummy
    # values, since this code is only reached before the actual digi
    # simulation") and which no response object ever looks at. With it on,
    # nothing changes.
    def component_shapes_follow_switch(src):
        assert src.count("      m_ComponentShapes(iC),\n") == 1
        return src.replace(
            "      m_ComponentShapes(iC),\n",
            '      m_ComponentShapes(params.getParameter<bool>("componentSeparateDigi"), iC),\n',
        )

    edit("cmssw/SimCalorimetry/EcalSimProducers/src/EcalDigiProducer.cc",
         component_shapes_follow_switch)

if release_cycle < (11, 0):
    # --- 10_6-era fixups -----------------------------------------------------

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

    # Missing standard includes that the era's gcc 7 pulled in transitively
    # but gcc 11 does not, and a TLeaf usage that ROOT headers no longer
    # forward-declare completely.
    def insert_after(marker, insert):
        def do(src):
            if insert in src:  # already applied on a rerun
                return src
            assert marker in src
            return src.replace(marker, marker + "\n" + insert, 1)

        return do

    edit(
        "cmssw/FWCore/Utilities/interface/ESIndices.h",
        insert_after("#define FWCore_Utilities_ESIndices_h", "#include <limits>"),
    )
    edit(
        "cmssw/FWCore/ServiceRegistry/interface/ActivityRegistry.h",
        insert_after("#define FWCore_ServiceRegistry_ActivityRegistry_h", "#include <string>"),
    )
    edit(
        "cmssw/IOPool/Output/src/RootOutputTree.h",
        insert_after("#include <memory>", "#include <set>"),
    )
    edit(
        "cmssw/IOPool/Input/src/RootTree.cc",
        insert_after('#include "TTree.h"', '#include "TLeaf.h"'),
    )
    for indexer in ["CSCIndexerPostls1", "CSCIndexerStartup"]:
        path = "cmssw/CalibMuon/CSCCalibration/src/%s.cc" % indexer
        if os.path.exists(path):
            edit(path, insert_after(
                "#include <CalibMuon/CSCCalibration/interface/%s.h>" % indexer,
                "#include <algorithm>"))
    path = "cmssw/CondFormats/CTPPSReadoutObjects/src/PPSTimingCalibration.cc"
    if os.path.exists(path):
        edit(path, insert_after(
            '#include "CondFormats/CTPPSReadoutObjects/interface/PPSTimingCalibration.h"',
            "#include <ostream>"))
    path = "cmssw/RecoEgamma/EgammaTools/interface/EGEnergySysIndex.h"
    if os.path.exists(path):
        edit(path, insert_after("#include <array>",
                                "#include <cstddef>\n#include <string>"))
    path = "cmssw/RecoTauTag/RecoTau/plugins/PFRecoTauDiscriminationAgainstElectron2.cc"
    if os.path.exists(path):
        edit(path, insert_after(
            '#include "FWCore/Utilities/interface/Exception.h"',
            '#include <string>\n#include "TObjString.h"'))
    path = "cmssw/RecoBTag/Combined/plugins/DeepCMVATagInfoProducer.cc"
    if os.path.exists(path):
        edit(path, lambda src: src.replace("(isinf(", "(std::isinf("))
    # newer fastjet-contrib dropped the bool argument
    path = "cmssw/RecoJets/JetProducers/plugins/CSJetProducer.cc"
    if os.path.exists(path):
        edit(path, lambda src: src.replace(
            "set_do_mass_subtraction(true)", "set_do_mass_subtraction()"))

    # TauReco's dictionary header includes two pat:: headers, but none of its
    # classes_def entries use pat types; drop them instead of pulling the
    # whole PatCandidates package (and its CondFormats chain) into the build.
    edit(
        "cmssw/DataFormats/TauReco/src/classes_3.h",
        lambda src: src.replace('#include "DataFormats/PatCandidates/interface/Jet.h"\n', "").replace(
            '#include "DataFormats/PatCandidates/interface/PackedCandidate.h"\n', ""),
    )


    # The FWCore/PythonUtilities scripts (edmDumpEventContent & friends) are
    # still python 2 in this release; upstream only ported them for 11_X.
    # lib2to3 does the same port here. The scripts have no .py extension, so
    # they must be listed explicitly (a directory argument would skip them).
    import lib2to3.main

    scripts_dir = "cmssw/FWCore/PythonUtilities/scripts"
    scripts = [os.path.join(scripts_dir, f) for f in sorted(os.listdir(scripts_dir))]
    lib2to3.main.main("lib2to3.fixes", ["--write", "--nobackups", "--no-diffs"] + scripts)

    # ... plus two py2 leftovers that 2to3 does not rewrite
    edit(
        "cmssw/FWCore/PythonUtilities/scripts/edmDumpEventContent",
        lambda src: src.replace("newStderr = file ( '/dev/null', 'w')",
                                "newStderr = open('/dev/null', 'w')"),
    )
    edit(
        "cmssw/PhysicsTools/PythonAnalysis/python/cmstools.py",
        lambda src: src.replace("import exceptions\n", "").replace(
            "exceptions.Exception", "Exception"),
    )

    # GBRForestTools uses tinyxml2's QueryStringAttribute, which only exists
    # from tinyxml2 7 on (nixos-22.05 ships 6.0). The return value is ignored
    # anyway, so plain Attribute() is a drop-in.
    edit(
        "cmssw/CommonTools/MVAUtils/src/GBRForestTools.cc",
        lambda src: re.sub(
            r'(\w+)->QueryStringAttribute\("([^"]+)", &(\w+)\);',
            r'\3 = \1->Attribute("\2");',
            src,
        ),
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
                edit(os.path.join(root, name),
                     lambda src: re.sub(r'^#include "Pythia8Plugins/EvtGen.h"\n',
                                        lambda m: EVTGEN_STUB, src, flags=re.M))

    def _stub_hadronizer(src):
        src = src.replace('#include "Vincia/Vincia.h"\n#include "Dire/Dire.h"\n',
                          SHOWER_STUB)
        return src
    edit(p8i + "/plugins/Pythia8Hadronizer.cc", _stub_hadronizer)

    for bf in [p8i + "/BuildFile.xml", p8i + "/plugins/BuildFile.xml"]:
        drop_tool_deps(bf, ["evtgen", "dire", "vincia"])

    # the LHE reader's mcdb:// support and the HepML metadata need externals
    # that are not packaged; the deps are only used by those code paths
    lhe = "cmssw/GeneratorInterface/LHEInterface"
    for bf in [lhe + "/BuildFile.xml", lhe + "/plugins/BuildFile.xml"]:
        drop_tool_deps(bf, ["mcdb", "libhepml"])

    # base-classes-only decay interfaces (the concrete implementations in
    # plugins/ link the externals; no_plugins in the configuration)
    drop_tool_deps("cmssw/GeneratorInterface/EvtGenInterface/BuildFile.xml", ["evtgen"])
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

    # boost >= 1.75 no longer includes the date_time posix_time headers
    # transitively from boost/interprocess; FWCore/SharedMemory uses
    # boost::posix_time without including them itself
    edit("cmssw/FWCore/SharedMemory/interface/ControllerChannel.h",
         lambda src: src.replace(
             '#include "boost/interprocess/managed_shared_memory.hpp"',
             '#include "boost/date_time/posix_time/posix_time_types.hpp"\n'
             '#include "boost/interprocess/managed_shared_memory.hpp"'))

    # gcc 11's libstdc++ does not provide std::optional transitively here
    edit("cmssw/GeneratorInterface/Core/plugins/ExternalGeneratorFilter.cc",
         lambda src: src.replace(
             '#include "FWCore/Framework/interface/global/EDFilter.h"',
             '#include <optional>\n'
             '#include "FWCore/Framework/interface/global/EDFilter.h"'))

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
            "// see prepare_sources.py: the HEPEVT/HEPRUP/HEPEUP fortran common\n"
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
    edit(nano + "/plugins/BuildFile.xml",
         lambda xml: xml if "SimDataFormats/GeneratorProducts" in xml else xml.replace(
             '<use   name="FWCore/Framework"/>',
             '<use   name="FWCore/Framework"/>\n<use   name="SimDataFormats/GeneratorProducts"/>'))

# CastorSD deletes a pointer it never initialised.
#
# CastorShowerLibrary* showerLibrary is a raw member that the constructor
# assigns only inside `if (useShowerLibrary)`, and that the initialiser list -
# which does cover numberingScheme, lvC3EF, lvC3HF, lvC4EF, lvC4HF and lvCAST -
# leaves out. ~CastorSD then runs `delete showerLibrary` unconditionally, so a
# job that switches the library off deletes an indeterminate pointer and
# segfaults on the way out, after every event has been written.
#
# Production never sees it because production always has the Castor shower
# library. We cannot: the file is distributed separately and the download stub
# points at a host that is now behind CERN SSO (see examples/MuonGunSim). So
# switching it off is the only option here, and that path has to work.
#
# Both releases have it - 10_6_30 on one line, 20_1_0_pre2 clang-formatted
# onto several - so the anchor is the last initialiser rather than the run
# of them, and a miss is a hard failure: the fix silently not applying
# would only show up as a segfault at the end of a job that otherwise
# looks perfect.
path = "cmssw/SimG4CMS/Forward/src/CastorSD.cc"
if os.path.exists(path):
    def fix_castor_shower_library(src):
        if "lvCAST(nullptr), showerLibrary(nullptr)" in src:
            return src
        anchor = "lvCAST(nullptr) {"
        if anchor not in src:
            raise SystemExit(
                "CastorSD.cc: initialiser list not where expected - the"
                " uninitialised showerLibrary fix needs rechecking")
        return src.replace(
            "lvCAST(nullptr) {",
            "lvCAST(nullptr), showerLibrary(nullptr) {")
    edit(path, fix_castor_shower_library)

# --- one plugin search path variable on every platform (all versions) ------
# The plugin manager builds its search path from LD_LIBRARY_PATH, except on
# macOS, where it reads DYLD_FALLBACK_LIBRARY_PATH instead. Everything else
# here speaks LD_LIBRARY_PATH: the setup hook, the example checks and
# run_all.sh, and ROOT, which reads it next to DYLD_LIBRARY_PATH on macOS to
# resolve the libraries the rootmaps name. A DYLD_* variable would also have
# to survive System Integrity Protection, which strips them whenever a
# protected binary (/bin/sh, /usr/bin/env) is in the exec chain, and it
# would replace dyld's own fallback path for every program in the
# environment. Nothing on macOS links through LD_LIBRARY_PATH (the
# libraries carry rpaths), so reading it here only tells the plugin manager
# which directories to index.
path = "cmssw/FWCore/PluginManager/src/standard.cc"


def plugin_path_from_ld_library_path(src):
    src, n = re.subn(
        r'#ifdef __APPLE__\n\s*const char\* path = (?:std::)?getenv\("DYLD_FALLBACK_LIBRARY_PATH"\);\n'
        r'#else\n(\s*const char\* path = (?:std::)?getenv\("LD_LIBRARY_PATH"\);\n)#endif\n',
        r"\1", src)
    if n != 1 and "DYLD_FALLBACK_LIBRARY_PATH" in src:
        raise SystemExit("standard.cc: plugin search path code not where expected")
    return src


edit(path, plugin_path_from_ld_library_path)

# --- the async pool's thread name on macOS (20_1) ---------------------------
# pthread_setname_np(thread, name) is the glibc form. macOS has only
# pthread_setname_np(name), which names the calling thread, so it cannot be
# done from the constructor that spawns the thread. The name is cosmetic (it
# is what a debugger or top shows), so on macOS the thread goes unnamed.
path = "cmssw/FWCore/Concurrency/src/WaitingThreadPool.cc"
if os.path.exists(path):
    def name_thread_on_linux_only(src):
        call = "[[maybe_unused]] int err = pthread_setname_np(thread_.native_handle(), poolName);"
        if "#ifdef __APPLE__" in src:
            return src
        if call not in src:
            raise SystemExit("WaitingThreadPool.cc: pthread_setname_np call not where expected")
        return src.replace("    " + call, "#ifdef __APPLE__\n    [[maybe_unused]] int err = 0;\n#else\n    "
                           + call + "\n#endif")
    edit(path, name_thread_on_linux_only)

# --- libstdc++ extensions under libc++ (all versions) -----------------------
# On macOS the release is compiled against libc++, and CMSSW has only ever
# been built against libstdc++ - its clang builds included. What is left of
# the GNU extensions in the packages built here:
#
# * includes of <ext/alloc_traits.h> and <ext/pool_allocator.h> that nothing
#   uses any more (the pool allocator typedef they were for is commented out
#   in every header that includes it), and of <ext/functional> in files that
#   no longer touch __gnu_cxx;
# * __gnu_cxx::is_sorted from <ext/algorithm>, which is std::is_sorted since
#   C++11.
#
# Both are plain cleanups that mean the same with either library, so they
# are applied everywhere rather than behind a platform test.
ext_dead_includes = ["#include <ext/alloc_traits.h>\n", "#include <ext/pool_allocator.h>\n"]
for root, dirs, files in os.walk("cmssw"):
    for name in files:
        if not name.endswith((".h", ".cc", ".icc", ".cpp")):
            continue
        p = os.path.join(root, name)
        with open(p, errors="surrogateescape") as f:
            src = f.read()
        if "<ext/" not in src:
            continue
        new = src
        for inc in ext_dead_includes:
            new = new.replace(inc, "")
        if "#include <ext/functional>" in new and "__gnu_cxx::" not in new:
            new = new.replace("#include <ext/functional>\n", "")
        if "#include <ext/algorithm>" in new:
            new = new.replace("#include <ext/algorithm>", "#include <algorithm>")
            new = new.replace("__gnu_cxx::is_sorted", "std::is_sorted")
        if new != src:
            with open(p, "w", errors="surrogateescape") as f:
                f.write(new)

# The one real use: PhysicsTools/MVATrainer (10_6) reads the output of a
# popen()ed command through __gnu_cxx::stdio_filebuf. libc++ has no such
# class, so give it the few lines of read-only FILE* streambuf it needs.
# libstdc++ builds keep the original.
path = "cmssw/PhysicsTools/MVATrainer/src/XMLDocument.cc"
if os.path.exists(path):
    def stdio_filebuf_for_libcxx(src):
        if "stdio_filebuf_compat" in src:
            return src
        if src.count("#include <ext/stdio_filebuf.h>\n") != 1 or \
                src.count("typedef __gnu_cxx::stdio_filebuf<char>\t__filebuf_type;") != 1:
            raise SystemExit("XMLDocument.cc: stdio_filebuf use not where expected")
        src = src.replace("#include <ext/stdio_filebuf.h>\n", "\n".join([
            "#include <cstdio>",
            "#ifdef _LIBCPP_VERSION",
            "#include <streambuf>",
            "namespace {",
            "  // read-only stand-in for __gnu_cxx::stdio_filebuf<char>",
            "  class stdio_filebuf_compat : public std::streambuf {",
            "  public:",
            "    stdio_filebuf_compat(FILE* file, std::ios_base::openmode) : file_(file) {}",
            "",
            "  protected:",
            "    int_type underflow() override {",
            "      if (gptr() < egptr())",
            "        return traits_type::to_int_type(*gptr());",
            "      std::size_t n = std::fread(buf_, 1, sizeof buf_, file_);",
            "      if (n == 0)",
            "        return traits_type::eof();",
            "      setg(buf_, buf_, buf_ + n);",
            "      return traits_type::to_int_type(*gptr());",
            "    }",
            "",
            "  private:",
            "    FILE* file_;",
            "    char buf_[4096];",
            "  };",
            "}  // namespace",
            "#else",
            "#include <ext/stdio_filebuf.h>",
            "#endif",
            ""]))
        # (and the constructor has to name a base constructor: libc++'s
        # istream, unlike libstdc++'s, has no default one to fall back on)
        src = src.replace("\t\t\tfile_(file), filebuf_(file, std::ios_base::in)",
                          "\t\t\tstd::istream(nullptr), file_(file), filebuf_(file, std::ios_base::in)")
        return src.replace(
            "typedef __gnu_cxx::stdio_filebuf<char>\t__filebuf_type;",
            "#ifdef _LIBCPP_VERSION\n\t\ttypedef stdio_filebuf_compat\t__filebuf_type;\n#else\n"
            "\t\ttypedef __gnu_cxx::stdio_filebuf<char>\t__filebuf_type;\n#endif")
    edit(path, stdio_filebuf_for_libcxx)

# --- UUID_STR_LEN outside util-linux (20_1) ---------------------------------
# Guid.cc sizes its buffer with UUID_STR_LEN, which util-linux's libuuid
# defines and the macOS <uuid/uuid.h> does not. It is the length of the
# 36-character text form plus its terminator either way.
path = "cmssw/FWCore/Utilities/src/Guid.cc"
if os.path.exists(path):
    def define_uuid_str_len(src):
        if "UUID_STR_LEN" not in src or "#define UUID_STR_LEN" in src:
            return src
        anchor = '#include "FWCore/Utilities/interface/Guid.h"\n'
        if anchor not in src:
            raise SystemExit("Guid.cc: include not where expected")
        return src.replace(anchor, anchor + "#ifndef UUID_STR_LEN\n#define UUID_STR_LEN 37\n#endif\n")
    edit(path, define_uuid_str_len)

# --- includes libstdc++ supplied transitively (all versions) ----------------
# libc++ includes far less from its own headers than libstdc++ does, so files
# that use a standard facility without including its header compile on
# Linux and fail on macOS. Adding the include is right under either library.
missing_includes = {
    "cmssw/DataFormats/ForwardDetId/src/BTLDetId.cc": ["<sstream>"],
    "cmssw/DataFormats/ForwardDetId/src/ETLDetId.cc": ["<sstream>"],
    "cmssw/Geometry/TrackerGeometryBuilder/interface/PixelTopologyMap.h": ["<sstream>"],
    "cmssw/Geometry/HGCalCommonData/interface/HGCalCell.h": ["<utility>"],
    "cmssw/CondCore/CondDB/interface/Utils.h": ["<map>"],
    "cmssw/FWCore/Framework/interface/Callback.h": ["<array>"],
    "cmssw/Geometry/HGCalCommonData/interface/HGCalDDDConstants.h": ["<array>"],
    "cmssw/SimDataFormats/TrackerDigiSimLink/interface/StripCompactDigiSimLinks.h": ["<vector>"],
    "cmssw/CondFormats/PCLConfig/src/AlignPCLThreshold.cc": ["<array>"],
    "cmssw/CondFormats/PCLConfig/src/AlignPCLThresholds.cc": ["<array>"],
    "cmssw/DetectorDescription/OfflineDBLoader/src/DDCoreToDDXMLOutput.cc": ["<array>"],
    "cmssw/GeneratorInterface/Core/src/BaseHadronizer.cc": ["<array>"],
    "cmssw/PhysicsTools/MVATrainer/src/XMLDocument.cc": ["<fstream>"],
    "cmssw/Geometry/HGCalCommonData/interface/HGCalParameters.h": ["<array>"],
    "cmssw/RecoParticleFlow/PFClusterTools/src/PFResolutionMap.cc": ["<array>"],
    "cmssw/Geometry/MTDGeometryBuilder/src/MTDParametersFromDD.cc": ["<array>"],
    "cmssw/L1Trigger/L1TMuonEndCap/interface/TrackTools.h": ["<utility>"],
    # iterates a reco::TrackCollection with only TrackFwd.h in sight
    "cmssw/RecoTracker/FinalTrackSelectors/interface/TrackMVAClassifier.h":
        ['"DataFormats/TrackReco/interface/Track.h"'],
}
for path, headers in missing_includes.items():
    if not os.path.exists(path):
        continue
    def add_includes(src, headers=headers, path=path):
        lines = src.split("\n")
        last = max((i for i, l in enumerate(lines) if l.startswith("#include")), default=None)
        if last is None:
            raise SystemExit(f"{path}: no #include to add {headers} after")
        new = [f"#include {h}" for h in headers if f"#include {h}" not in src]
        return "\n".join(lines[:last + 1] + new + lines[last + 1:])
    edit(path, add_includes)

# --- the vector-extension SIMD types on Apple arm64 (all versions) ---------
# SIMDVec.h falls back to the scalar Basic2DVector/Basic3DVector when
# __BIGGEST_ALIGNMENT__ is below 16, as a proxy for "no 16-byte vectors".
# The Apple arm64 ABI reports 8 there (long double is double), although its
# NEON vectors and operator new are 16-byte aligned like on aarch64 Linux,
# which reports 16. The scalar fallback is otherwise unused and has rotted
# (RecoParticleFlow/PFClusterTools reaches for the .v member only the
# vector-extension implementation has), so let Apple arm64 take the same
# kind of implementation every Linux build does. (10_6's PFClusterTools needs
# it as much: x86_64 took the SSE one there, which has the same members.)
path = "cmssw/DataFormats/Math/interface/SIMDVec.h"
if os.path.exists(path):
    def extvect_on_apple_arm64(src):
        new = re.sub(r"\(__BIGGEST_ALIGNMENT__\s*<\s*16\)",
                     lambda m: "(__BIGGEST_ALIGNMENT__ < 16 && !(defined(__APPLE__) && defined(__aarch64__)))",
                     src, count=1)
        if new == src and "defined(__APPLE__) && defined(__aarch64__)" not in src:
            raise SystemExit("SIMDVec.h: alignment test not where expected")
        return new
    edit(path, extvect_on_apple_arm64)

# --- constexpr std::abs (20_1) ----------------------------------------------
# TTTrack_TrackWord computes its binning steps as constexpr from
# std::abs(<negative constant>). std::abs is constexpr only from C++23; gcc
# folds it as a builtin anyway, clang with libc++ does not. Spell it out.
path = "cmssw/DataFormats/L1TrackTrigger/interface/TTTrack_TrackWord.h"
if os.path.exists(path):
    def constexpr_abs(src):
        return re.sub(r"\(2\. \* std::abs\((min\w+)\)\)", r"(2. * (\1 < 0 ? -\1 : \1))", src)
    edit(path, constexpr_abs)

# --- a vector iterator made from a pointer (20_1) ---------------------------
# SiStripClusterInfo::chargeLR declares std::vector<uint8_t>::const_iterator
# variables but initialises them from stripCharges(), a range over plain
# pointers. libstdc++'s iterator happens to have a public constructor from
# the pointer; libc++'s does not. Let the variables have the range's type.
# (10_6 spells the same declaration over several lines, but there the range
# is a real std::vector, so it is correct as it stands.)
path = "cmssw/RecoLocalTracker/SiStripClusterizer/src/SiStripClusterInfo.cc"
if os.path.exists(path):
    def iterators_from_range(src):
        old = "std::vector<uint8_t>::const_iterator begin(stripCharges().begin()), end(stripCharges().end()), max;"
        # (and qualify the algorithms: unqualified, they were only found by
        # argument-dependent lookup on the std:: iterator type)
        src = src.replace(old, "auto begin = stripCharges().begin(), end = stripCharges().end(), max = begin;")
        src = src.replace("  max = max_element(begin, end);", "  max = std::max_element(begin, end);")
        return src.replace("std::make_pair(accumulate(begin, max, uint16_t(0)), accumulate(max + 1, end, uint16_t(0)))",
                           "std::make_pair(std::accumulate(begin, max, uint16_t(0)), std::accumulate(max + 1, end, uint16_t(0)))")
    edit(path, iterators_from_range)

# --- HOST_NAME_MAX (20_1) ---------------------------------------------------
# glibc's name for the hostname length limit; macOS has only the POSIX
# minimum, _POSIX_HOST_NAME_MAX (255, which is also what glibc defines
# HOST_NAME_MAX to be).
path = "cmssw/CondCore/CondDB/interface/Utils.h"
if os.path.exists(path):
    def host_name_max(src):
        if "HOST_NAME_MAX" not in src or "#define HOST_NAME_MAX" in src:
            return src
        anchor = "#include <climits>\n"
        if anchor not in src:
            raise SystemExit("CondDB Utils.h: <climits> include not where expected")
        return src.replace(anchor, anchor + "#ifndef HOST_NAME_MAX\n#define HOST_NAME_MAX _POSIX_HOST_NAME_MAX\n#endif\n")
    edit(path, host_name_max)

# --- the stack-trace helper process outside Linux (all versions) ------------
# InitRootHandlers forks a helper for stack traces. Two Linux-isms in it:
# pipe2(), which macOS does not have (pipe() plus FD_CLOEXEC is the same
# thing for a process that has not started other threads yet), and the
# non-Linux execv branch, which passes the char const* const* argv execv's
# char* const* parameter does not accept.
path = "cmssw/FWCore/Services/plugins/InitRootHandlers.cc"
if os.path.exists(path):
    def portable_helper_process(src):
        if "pipe2(" in src and "cms_pipe2" not in src:
            anchor = "#include <sys/wait.h>"
            lines = src.split("\n")
            if anchor not in lines:
                raise SystemExit("InitRootHandlers.cc: <sys/wait.h> include not where expected")
            at = lines.index(anchor) + 1
            lines[at:at] = [
                "#ifndef __linux__",
                "#include <fcntl.h>",
                "#include <unistd.h>",
                "namespace {",
                "  int cms_pipe2(int fds[2], int flags) {",
                "    if (pipe(fds) == -1)",
                "      return -1;",
                "    if (flags & O_CLOEXEC) {",
                "      fcntl(fds[0], F_SETFD, FD_CLOEXEC);",
                "      fcntl(fds[1], F_SETFD, FD_CLOEXEC);",
                "    }",
                "    return 0;",
                "  }",
                "}  // namespace",
                "#define pipe2 cms_pipe2",
                "#endif",
            ]
            src = "\n".join(lines)
        return src.replace('execv("/bin/sh", argv);', 'execv("/bin/sh", const_cast<char* const*>(argv));')
    edit(path, portable_helper_process)

# --- constexpr std::pow (20_1) ----------------------------------------------
# TTBV builds its powers-of-two table in a constexpr function with
# std::pow, which gcc folds as a builtin and libc++ does not declare
# constexpr. Doubling the previous entry gives the same, exact, values.
path = "cmssw/DataFormats/L1TrackTrigger/interface/TTBV.h"
if os.path.exists(path):
    def constexpr_powers_of_two(src):
        old = "      lut[i] = std::pow(2, i);"
        if old not in src:
            if "lut[i] = i == 0" in src:
                return src
            raise SystemExit("TTBV.h: powersOfTwo not where expected")
        return src.replace(old, "      lut[i] = i == 0 ? 1. : 2. * lut[i - 1];")
    edit(path, constexpr_powers_of_two)

# --- uint64_t is unsigned long long on macOS (20_1) ------------------------
# The L1 particle-flow jet formats overload unpack() for both
# std::array<uint64_t, 2> and std::array<unsigned long long, 2>. Those are
# two types where uint64_t is unsigned long (Linux) and one type where it is
# unsigned long long (macOS), and there the second overload redeclares the
# first. Keep it only where the types differ, as a template constrained to
# exactly unsigned long long, so the overload set on Linux is unchanged.
for path in ["cmssw/DataFormats/L1TParticleFlow/interface/jets.h",
             "cmssw/DataFormats/L1TParticleFlow/interface/gt_datatypes.h"]:
    if not os.path.exists(path):
        continue
    def ull_overload_where_distinct(src):
        src, n = re.subn(
            r"inline static (\w+) unpack\(const std::array<long long unsigned int, 2> &src\) \{",
            r"template <typename U = long long unsigned int,"
            r" typename = std::enable_if_t<std::is_same_v<U, long long unsigned int> && !std::is_same_v<U, uint64_t>>>"
            "\n    "
            r"inline static \1 unpack(const std::array<U, 2> &src) {",
            src)
        if n and "#include <type_traits>" not in src:
            src = src.replace("#include <array>", "#include <array>\n#include <type_traits>", 1)
        return src
    edit(path, ull_overload_where_distinct)

# --- conditions payloads read through std::stringbuf::pubsetbuf (all versions)
# default_deserialize hands the payload bytes to a std::stringbuf with
# pubsetbuf() and reads from that. libstdc++'s stringbuf takes the buffer as
# its contents; libc++'s keeps the no-op setbuf of basic_streambuf (both are
# allowed), so there the stream is empty, the archive runs dry at once and
# every payload fails with "data size does not fit with the current class
# layout" - even one written by the same job. Read from a copy instead.
path = "cmssw/CondCore/CondDB/interface/Serialization.h"
if os.path.exists(path):
    def deserialize_from_copy(src):
        src, n1 = re.subn(
            r"std::stringbuf sstreamerInfoBuf;\s*"
            r"sstreamerInfoBuf\.pubsetbuf\(\s*static_cast<char\*>\(const_cast<void\*>\(streamerInfoData\.data\(\)\)\),\s*streamerInfoData\.size\(\)\s*\);\s*"
            r"std::string streamerInfo = sstreamerInfoBuf\.str\(\);",
            "std::string streamerInfo(static_cast<const char*>(streamerInfoData.data()), streamerInfoData.size());",
            src)
        src, n2 = re.subn(
            r"std::stringbuf sdataBuf;\s*"
            r"sdataBuf\.pubsetbuf\(\s*static_cast<char\*>\(const_cast<void\*>\(payloadData\.data\(\)\)\),\s*payloadData\.size\(\)\s*\);\s*"
            r"std::istream dataBuffer\(\s*&sdataBuf\s*\);",
            "std::istringstream dataBuffer(\n"
            "          std::string(static_cast<const char*>(payloadData.data()), payloadData.size()));",
            src)
        if (n1, n2) != (1, 1) and "pubsetbuf" in src:
            raise SystemExit("CondDB Serialization.h: default_deserialize not where expected")
        return src
    edit(path, deserialize_from_copy)

# --- iterators of map<K, V> and map<const K, V> (10_6) ----------------------
# libstdc++ gives std::map<K, V> and std::map<const K, V> one and the same
# iterator type, so code can declare the one and initialise it from the
# other; libc++ gives them different types. Let the declarations take the
# type of what initialises them.
for path, old, new in [
    ("cmssw/DetectorDescription/OfflineDBLoader/plugins/OutputDDToDDL.cc",
     "std::map<DDsvalues_type, std::set<const DDPartSelection*> >::const_iterator mit( specStore.begin()), mend( specStore.end());",
     "auto mit = specStore.begin(), mend = specStore.end();"),
    ("cmssw/DetectorDescription/OfflineDBLoader/plugins/OutputMagneticFieldDDToDDL.cc",
     "std::map<DDsvalues_type, std::set<const DDPartSelection*> >::const_iterator mit( specStore.begin()), mend( specStore.end());",
     "auto mit = specStore.begin(), mend = specStore.end();"),
    ("cmssw/FWCore/MessageService/src/MessageLogger.cc",
     "std::map<const std::string, ELseverityLevel>::const_iterator it =",
     "auto it ="),
]:
    if os.path.exists(path):
        edit(path, lambda src, old=old, new=new: src.replace(old, new))

# --- make_shared and noexcept(false) destructors (10_6) ---------------------
# The 10_6 framework declares many EventSetup components' destructors
# noexcept(false). libc++ 11's make_shared control block holds the object as
# a member, and its own implicit destructor then cannot be as noexcept as the
# base it overrides. A shared_ptr made from new keeps the object out of the
# control block; ComponentMaker is the one place every ES module goes through.
path = "cmssw/FWCore/Framework/interface/ComponentMaker.h"
if os.path.exists(path):
    edit(path, lambda src: src.replace(
        "std::shared_ptr<TComponent> component = std::make_shared<TComponent>(iConfiguration);",
        "std::shared_ptr<TComponent> component(new TComponent(iConfiguration));"))

# --- the 10_6 vector-extension implementation under clang (10_6) ----------
# In 10_6, x86_64 always took the SSE implementation, so the vector-extension
# one (which the SIMDVec.h change above selects on Apple arm64) was only ever
# compiled by gcc, on aarch64 and ppc64le. Two gcc-isms in it:
# * operator[] returning T& to an element of a vector type, which clang does
#   not allow a reference to bind to; the vector is laid out as T[N], so
#   index that;
# * __builtin_shuffle, which clang does not have. With its constant mask
#   {1,0,5,4} over the concatenation of t1 and t2 it picks t1[1], t1[0],
#   t2[1], t2[0]; under clang, say so element by element.
for path in ["cmssw/DataFormats/GeometryVector/interface/extBasic2DVector.h",
             "cmssw/DataFormats/GeometryVector/interface/extBasic3DVector.h"]:
    if os.path.exists(path):
        edit(path, lambda src: src.replace(
            "T & operator[](int i) { return v[i];}",
            "T & operator[](int i) { return reinterpret_cast<T*>(&v)[i];}"))
# * and, the one that matters: under __clang__ ExtVec.h spelled its vector
#   types with ext_vector_type(N), whose N counts elements, while it passes
#   N in bytes - so a "4 doubles" vector was a vector of 32 doubles, and the
#   geometry built on it computed nonsense (no strip rec hit within 500 um of
#   its SimHit) without a single compiler complaint. vector_size(N), which
#   gcc always got, is what later releases use for every compiler.
path = "cmssw/DataFormats/Math/interface/ExtVec.h"
if os.path.exists(path):
    def vector_size_for_clang(src):
        old = ("#ifdef __clang__\n#define VECTOR_EXT(N) __attribute__( ( ext_vector_type( N ) ) )\n"
               "#else\n#define VECTOR_EXT(N) __attribute__( ( vector_size( N ) ) )\n#endif")
        if "ext_vector_type" not in src:
            return src
        if old not in src:
            raise SystemExit("ExtVec.h: VECTOR_EXT definition not where expected")
        return src.replace(old, "#define VECTOR_EXT(N) __attribute__( ( vector_size( N ) ) )")
    edit(path, vector_size_for_clang)
path = "cmssw/TrackingTools/AnalyticalJacobians/src/AnalyticalCurvilinearJacobianEXT.icc"
if os.path.exists(path):
    def shufflevector_for_clang(src):
        old = "  Vec4D t = __builtin_shuffle(t1,t2,mask);"
        if "__builtin_shufflevector" in src:  # later releases handle clang themselves
            return src
        if old not in src:
            raise SystemExit("AnalyticalCurvilinearJacobianEXT.icc: shuffle not where expected")
        return src.replace(old, "#ifdef __clang__\n  Vec4D t{t1[1], t1[0], t2[1], t2[0]};\n#else\n"
                           + old + "\n#endif")
    edit(path, shufflevector_for_clang)

# --- non-const comparison operators (all versions) -------------------------
# NanoAOD's ScaleVarWeight (10_6) and the phase-2 pixel Phase2ITQCore and
# Phase2ITChipBitStream (20_1) declare operator< without const. libstdc++'s std::sort happens never to
# compare through a const reference; libc++'s does, and finds no usable
# operator. Each compares two members and changes neither.
for path, decl in [
        ("cmssw/PhysicsTools/NanoAOD/plugins/GenWeightsTableProducer.cc",
         "bool operator<(const ScaleVarWeight& other)"),
        ("cmssw/DataFormats/Phase2TrackerDigi/interface/Phase2ITQCore.h",
         "bool operator<(const Phase2ITQCore& other)"),
        ("cmssw/DataFormats/Phase2TrackerDigi/interface/Phase2ITChipBitStream.h",
         "bool operator<(const Phase2ITChipBitStream& other)")]:
    if os.path.exists(path):
        edit(path, lambda src, decl=decl: src.replace(decl + " {", decl + " const {"))

# --- a map iterator decremented past begin() (all versions) ---------------
# HcalPulseContainmentCorrection::getCorrection decrements the result of
# upper_bound() before checking whether it is begin(), which it is for every
# amplitude below the first tabulated point (1 fC) - and decrementing begin()
# is undefined. libstdc++'s tree lands on its header node and the value is
# never read in that branch; libc++'s walks off the tree and dereferences
# null, killing every HBHE reconstruction that sees a small pulse. Only step
# back when there is somewhere to step to.
path = "cmssw/CalibCalorimetry/HcalAlgos/src/HcalPulseContainmentCorrection.cc"
if os.path.exists(path):
    def no_decrement_past_begin(src):
        if "if (fclower != mCorFactors_.begin())" in src:
            return src
        new, n = re.subn(r"(\n(\s*)fclower = fcupper;\n)\s*fclower--;\n",
                         r"\1\2if (fclower != mCorFactors_.begin())\n\2  fclower--;\n", src)
        if n != 1:
            raise SystemExit("HcalPulseContainmentCorrection.cc: getCorrection not where expected")
        return new
    edit(path, no_decrement_past_begin)

# --- DQMServices/Core: the protobuf code from the protoc at hand (20_1) ------
# The DQM histogram file format (ROOTFilePB) comes as protoc output checked
# into the release, and generated protobuf code only compiles against the
# exact protobuf version that generated it (6.31.1 for 20_1_0_pre4). Generate
# it again from the .proto with the protoc of the build environment.
pb = "cmssw/DQMServices/Core"
if os.path.exists(pb + "/src/ROOTFilePB.proto") and shutil.which("protoc"):
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as out:
        subprocess.run(["protoc", "-Icmssw", "--cpp_out=" + out,
                        "DQMServices/Core/src/ROOTFilePB.proto"], check=True)
        gen = out + "/DQMServices/Core/src/ROOTFilePB.pb"
        # the release keeps the header in interface/, where its users look
        with open(gen + ".cc") as f:
            cc = f.read().replace('"DQMServices/Core/src/ROOTFilePB.pb.h"',
                                  '"DQMServices/Core/interface/ROOTFilePB.pb.h"')
        with open(pb + "/src/ROOTFilePB.pb.cc", "w") as f:
            f.write(cc)
        shutil.copyfile(gen + ".h", pb + "/interface/ROOTFilePB.pb.h")

# --- the PAT MVA producers without TensorFlow (20_1) ------------------------
# BaseMVAValueMapProducer, the template behind the PAT and NanoAOD MVA value
# maps, evaluates with TMVA, ONNXRuntime or TensorFlow. The TensorFlow C++
# API is not packaged: drop that backend, so a configuration asking for it
# fails when the module is constructed, and keep the other two.
path = "cmssw/PhysicsTools/PatAlgos/interface/BaseMVAValueMapProducer.h"
if os.path.exists(path):
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
# evaluates a TensorFlow graph. Neither external is packaged.
nano = "cmssw/PhysicsTools/NanoAOD"
if os.path.exists(nano + "/plugins/TauSpinnerTableProducer.cc"):
    os.remove(nano + "/plugins/TauSpinnerTableProducer.cc")
    drop_tool_deps(nano + "/plugins/BuildFile.xml", ["tauolapp"])
if os.path.exists(nano + "/plugins/DisTauTag.cc"):
    os.remove(nano + "/plugins/DisTauTag.cc")

# --- (re)setiosflags found by argument-dependent lookup only (all versions) -
# A few files (TKinFitter, TopObjects' printParticle, ...) call setiosflags()
# and resetiosflags() unqualified. With libstdc++ the argument (std::ios::right,
# of the enum type _Ios_Fmtflags) brings std into the lookup; with libc++
# fmtflags is a plain unsigned int, and nothing does. Qualify them wherever
# no using-directive makes it unnecessary.
_iosflags = re.compile(r"(?<![:\w])((?:re)?setiosflags)\(")
for root, dirs, files in os.walk("cmssw"):
    for name in files:
        if not name.endswith((".cc", ".h", ".cpp", ".cxx")):
            continue
        path = os.path.join(root, name)
        with open(path, encoding="latin-1") as f:
            src = f.read()
        if "setiosflags(" in src and "using namespace std" not in src and _iosflags.search(src):
            with open(path, "w", encoding="latin-1") as f:
                f.write(_iosflags.sub(r"std::\1(", src))

# --- b-tagging DNNs without the Triton client (20_1) ------------------------
# RecoBTag/ONNXRuntime evaluates the ParticleNet / ParticleTransformer
# taggers in process with ONNXRuntime; its *Sonic* producers are the same
# taggers offloaded to a Triton inference server, whose client is not
# packaged.
path = "cmssw/RecoBTag/ONNXRuntime/plugins"
if glob.glob(path + "/*Sonic*.cc"):
    for f in glob.glob(path + "/*Sonic*.cc"):
        os.remove(f)
    drop_tool_deps(path + "/BuildFile.xml", TF_TRITON_DEPS)

# --- the EMTF emulator library without TensorFlow (20_1) --------------------
# L1Trigger/L1TMuonEndCap lists PhysicsTools/TensorFlow among its
# dependencies, but none of its code uses it. EventFilter/L1TRawToDigi's
# EMTF unpacker needs the library (the track and hit helpers).
drop_tool_deps("cmssw/L1Trigger/L1TMuonEndCap/BuildFile.xml", ["PhysicsTools/TensorFlow"])

# --- packages kept as configuration only -----------------------------------
def python_only(pkg):
    """Keep a package's python/ (and data/, and its headers, for code that
    includes them): no library, no plugins."""
    pkg = "cmssw/" + pkg
    if os.path.exists(pkg + "/BuildFile.xml"):
        for d in ("src", "plugins", "test", "bin"):
            shutil.rmtree(os.path.join(pkg, d), ignore_errors=True)
        os.remove(pkg + "/BuildFile.xml")


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

# --- the legacy global muon trigger without std::atomic<std::shared_ptr> (20_1)
# L1MuGlobalMuonTrigger shares its configuration between instances through
# static std::atomic<std::shared_ptr<T>> members, a C++20 specialisation
# libc++ does not implement (the primary template then rejects the type as
# not trivially copyable). The same operations, load and
# compare_exchange_strong, through the shared_ptr atomic free functions.
gmt = "cmssw/L1Trigger/GlobalMuonTrigger/interface/L1MuGlobalMuonTrigger.h"
if os.path.exists(gmt) and "std::atomic<std::shared_ptr<" in open(gmt).read():
    shim = """
template <typename T>
class L1MuGMTAtomicSharedPtr {
public:
  std::shared_ptr<T> load() const { return std::atomic_load(&p_); }
  bool compare_exchange_strong(std::shared_ptr<T>& expected,
                               std::shared_ptr<T> desired,
                               std::memory_order success,
                               std::memory_order failure) {
    return std::atomic_compare_exchange_strong_explicit(&p_, &expected, std::move(desired), success, failure);
  }

private:
  std::shared_ptr<T> p_;
};
"""
    def atomics(src):
        for t in ("L1MuGMTConfig", "L1MuGMTDebugBlock"):
            src = src.replace(f"std::atomic<std::shared_ptr<{t}>>", f"L1MuGMTAtomicSharedPtr<{t}>")
        return src
    edit(gmt, lambda src: atomics(src.replace("#include <memory>\n", "#include <memory>\n" + shim, 1)))
    edit("cmssw/L1Trigger/GlobalMuonTrigger/src/L1MuGlobalMuonTrigger.cc", atomics)

# --- the DT trigger primitive configuration from python, marked valid (20_1)
# DTConfigManager carries a flag saying whether the chamber (CCB)
# configuration is valid for the run; the DT trigger primitive emulator
# produces empty collections when it is not. The database producer sets it,
# the trivial (from-python) producer never does, and the constructor leaves
# it uninitialised - so whether the emulator runs at all depends on what was
# in the heap memory (on macOS: it did not). A configuration given in python
# is valid by construction.
path = "cmssw/L1TriggerConfig/DTTPGConfigProducers/src/DTConfigTrivialProducer.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace(
        "  m_manager->setUseAcceptParam(useBtiAcceptParam);  // CB Are these needed here???\n",
        "  m_manager->setUseAcceptParam(useBtiAcceptParam);  // CB Are these needed here???\n"
        "  m_manager->setCCBConfigValidity(true);\n", 1))

# --- iterators initialised from nullptr (20_1) ------------------------------
# The RPC PAC trigger's RPCStripsRing initialises a std::map iterator with
# nullptr, and the ECAL DQM's IntegrityClient a std::vector one (the channel
# status map's), which libstdc++'s iterators (a pointer underneath) accept
# and libc++'s do not. A value-initialised iterator is what was meant.
path = "cmssw/L1Trigger/RPCTrigger/interface/RPCStripsRing.h"
if os.path.exists(path):
    edit(path, lambda src: src.replace("m_logplaneSize(0), m_it(nullptr)", "m_logplaneSize(0), m_it()"))
path = "cmssw/DQM/EcalMonitorClient/src/IntegrityClient.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace("EcalChannelStatusMap::const_iterator chIt(nullptr);",
                                       "EcalChannelStatusMap::const_iterator chIt{};"))

# --- the release version as a string (20_1) --------------------------------
# The legacy GMT online configuration producer compares the version stored
# with a trigger key against PROJECT_VERSION, as a string literal: scram
# defines it with quotes. The CMake build defines it bare, like
# FWCore/Version, which stringifies it itself; do the same here.
path = "cmssw/L1TriggerConfig/GMTConfigProducers/src/L1MuGMTParametersOnlineProducer.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace(
        '#include "L1TriggerConfig/GMTConfigProducers/interface/L1MuGMTParametersOnlineProducer.h"\n',
        '#include "L1TriggerConfig/GMTConfigProducers/interface/L1MuGMTParametersOnlineProducer.h"\n'
        '#define L1MUGMT_STRINGIFY_(x) #x\n#define L1MUGMT_STRINGIFY(x) L1MUGMT_STRINGIFY_(x)\n'
        '#define L1MUGMT_PROJECT_VERSION L1MUGMT_STRINGIFY(PROJECT_VERSION)\n', 1)
        .replace(" PROJECT_VERSION", " L1MUGMT_PROJECT_VERSION"))

# --- maps keyed on "const int" (20_1) ---------------------------------------
# CommonTools/TrackerMap declares its maps std::map<const int, T> and walks
# them with std::map<int, T>::iterator, and DPGAnalysis/SiStripTools does the
# same with multimap<const uint32_t, T>. libstdc++'s iterator depends only on
# the value type, pair<const int, T> in both cases, so the two are the same
# type there; libc++'s also carries the key type, and they are not. A const
# key type adds nothing (map keys are const anyway): drop it.
for path in ("cmssw/CommonTools/TrackerMap/interface/TrackerMap.h",
             "cmssw/CommonTools/TrackerMap/src/TrackerMap.cc",
             "cmssw/DPGAnalysis/SiStripTools/plugins/TrackerDpgAnalysis.cc"):
    if os.path.exists(path):
        edit(path, lambda src: src.replace("map<const int, ", "map<int, ")
             .replace("map<const uint32_t, ", "map<uint32_t, "))

# --- the processor model on macOS (20_1) ------------------------------------
# The FastTimerService reports the processor it ran on. Its macOS branch
# declares the result string a second time, so it has never compiled
# there; and the length sysctlbyname returns counts the terminating NUL,
# which would end up in the string (and in the service's JSON).
path = "cmssw/HLTrigger/Timer/src/processor_model.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace(
        '  std::string result;\n  size_t len;\n', '  size_t len;\n', 1).replace(
        '  sysctlbyname("machdep.cpu.brand_string", result.data(), &len, NULL, 0);\n',
        '  sysctlbyname("machdep.cpu.brand_string", result.data(), &len, NULL, 0);\n'
        '  result.resize(len > 0 ? len - 1 : 0);\n', 1))

# --- an ifstream from a boost::filesystem::path (20_1) ----------------------
# Alignment/OfflineValidation's Trend opens a std::ifstream from a
# boost::filesystem::path, relying on the path converting implicitly to a
# std::string - which it does only where boost::filesystem::path::string_type
# is std::string and the conversion is not disabled. Name the string.
path = "cmssw/Alignment/OfflineValidation/src/Trend.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace("  ifstream f(file);\n", "  ifstream f(file.string());\n", 1))

# --- headers libstdc++ includes transitively and libc++ does not (20_1) -----
path = "cmssw/HLTriggerOffline/Scouting/plugins/ScoutingMuonPropertiesAnalyzer.cc"
if os.path.exists(path):  # std::numbers::pi
    edit(path, lambda src: src.replace("#include <map>\n", "#include <map>\n#include <numbers>\n", 1))
for path in ("cmssw/Validation/Geometry/src/MaterialBudgetTree.cc",
             "cmssw/DQMServices/StreamerIO/plugins/DQMStreamerReader.cc"):
    if os.path.exists(path):  # unlink()
        edit(path, lambda src: "#include <unistd.h>\n" + src)
# libc++'s <string> declares operator<<(ostream&, const string&) but defines it
# only in <ostream>: without that, the compiler leaves an undefined reference
# to a template nothing instantiates, which only dlopen finds.
path = "cmssw/FastSimulation/SimplifiedGeometryPropagator/interface/InteractionModel.h"
if os.path.exists(path):
    edit(path, lambda src: src.replace("#include <string>\n", "#include <ostream>\n#include <string>\n", 1))

# --- ulong, a glibc typedef (20_1) ------------------------------------------
# <sys/types.h> on glibc defines ulong as unsigned long; macOS's does not.
for path in ("cmssw/DQMServices/FileIO/plugins/DQMFileSaverPB.h",
             "cmssw/DQMServices/FileIO/plugins/DQMFileSaverPB.cc"):
    if os.path.exists(path):
        edit(path, lambda src: re.sub(r"\bulong\b", "unsigned long", src))

# --- the FastSim decayer without Pythia 6 (20_1) ----------------------------
# FastSimulation/ParticleDecay decays with Pythia 8 alone since Pythia 6 left
# the release, but its BuildFile still asks for Pythia 6's particle data
# (pydata) and the Fortran compiler that came with it.
path = "cmssw/FastSimulation/ParticleDecay"
if os.path.exists(path + "/src/PythiaDecays.cc") and "pydata" not in open(path + "/src/PythiaDecays.cc").read():
    drop_tool_deps(path + "/BuildFile.xml", ["pydata", "f77compiler"])

# --- FastSim's SimTracks marked as primaries (20_1) -------------------------
# SimTrack::genpartIndex() returns the generator particle's index only when
# the track is flagged primary (SimTrack::setIsPrimary), which the Geant4
# simulation sets on the particles it took from the generator. FastSim's
# ParticleManager stores the index but never sets the flag, so every FastSim
# SimTrack reads as having no generator particle, and the TrackingParticles
# built from them lose their link to it. Set it where the index is set.
path = "cmssw/FastSimulation/SimplifiedGeometryPropagator/src/ParticleManager.cc"
if os.path.exists(path) and "setIsPrimary" not in open(path).read():
    edit(path, lambda src: src.replace(
        "  simTracks_->back().setTrackId(simTrackIndex);\n",
        "  simTracks_->back().setTrackId(simTrackIndex);\n"
        "  if (particle->genParticleIndex() >= 0)\n"
        "    simTracks_->back().setIsPrimary();\n", 1))
