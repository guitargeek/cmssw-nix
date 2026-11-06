"""The release against externals and compilers newer than the ones it was
written for.

The nixpkgs boost, ROOT, protobuf and tinyxml2, gcc 11 for the 10_6 build
(released with gcc 7/8), python 3 for 10_6's python 2 scripts, and the CMake
build itself where it differs from scram (how PROJECT_VERSION is defined).
"""
from common import *  # noqa: F401,F403

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


# --- boost and libstdc++ of the generator interfaces' era (all versions) -----
if os.path.exists("cmssw/GeneratorInterface/Pythia8Interface"):
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

# --- an ifstream from a boost::filesystem::path (20_1) ----------------------
# Alignment/OfflineValidation's Trend opens a std::ifstream from a
# boost::filesystem::path, relying on the path converting implicitly to a
# std::string - which it does only where boost::filesystem::path::string_type
# is std::string and the conversion is not disabled. Name the string.
path = "cmssw/Alignment/OfflineValidation/src/Trend.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace("  ifstream f(file);\n", "  ifstream f(file.string());\n", 1))
