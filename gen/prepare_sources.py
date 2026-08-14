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

