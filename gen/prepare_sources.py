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

# --- L1 trigger menu payloads without the utm external (all versions) ------
# CondFormats/L1TObjects carries the L1TUtm* trigger-menu classes, which wrap
# the CMS utm library. Nothing in the reconstruction reads them, and they are
# self-contained (their EventSetup records live in their own files), so drop
# them together with the dependency.
l1t = "cmssw/CondFormats/L1TObjects"
if os.path.isdir(l1t) and os.path.exists(l1t + "/BuildFile.xml"):
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

    edit(p8i + "/src/Py8GunBase.cc",
         lambda src: src.replace('#include "Pythia8Plugins/EvtGen.h"\n', EVTGEN_STUB))

    def _stub_hadronizer(src):
        src = src.replace('#include "Vincia/Vincia.h"\n#include "Dire/Dire.h"\n',
                          SHOWER_STUB)
        src = src.replace('#include "Pythia8Plugins/EvtGen.h"\n', EVTGEN_STUB)
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
             '}\n', ""))

    # PhysicsTools/NanoAOD: the flat-table producers (NanoGen and, later,
    # nanoAOD production). Two plugins are pruned: the nano DQM module (the
    # DQM subsystem is not built) and the b-jet energy-regression MVA (its
    # base template lives in PhysicsTools/PatAlgos, not built yet). The
    # TensorFlow dependency of the plugins BuildFile is stale in 10_6 -
    # nothing in the package includes it.
    nano = "cmssw/PhysicsTools/NanoAOD"
    if os.path.exists(nano):
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
                        "GeneratorInterface/AlpgenInterface", "f77compiler"])

        def _prune_matchers(src):
            # the base-class header used to come in through the matcher headers
            src = src.replace(
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatchingMadgraph.h"\n',
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatching.h"\n')
            src = src.replace(
                '#include "GeneratorInterface/PartonShowerVeto/interface/JetMatchingAlpgen.h"\n', "")
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
