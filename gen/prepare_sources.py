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
import os
import re
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
        with open(path, encoding="latin-1", newline="") as f:
            src = f.read()
        if "boost/spirit/home/support/detail/endian" not in src:  # rerun
            return
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
        with open(path, "w", encoding="latin-1", newline="") as f:
            f.write(src)

    fix_eos_portable_archive("cmssw/CondFormats/Serialization/interface/eos/portable_iarchive.hpp")
    fix_eos_portable_archive("cmssw/CondFormats/Serialization/interface/eos/portable_oarchive.hpp")

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

    # PFCluster.cc is the only user of the vdt fast-math headers, which
    # nixos-22.05 does not package; std::log computes the same thing (only
    # slower and more accurately).
    def drop_vdt(src):
        src = src.replace('#include "vdt/vdtMath.h"\n', "")
        return src.replace("vdt::fast_log(", "std::log(")

    edit("cmssw/DataFormats/ParticleFlowReco/src/PFCluster.cc", drop_vdt)
    edit(
        "cmssw/DataFormats/ParticleFlowReco/BuildFile.xml",
        lambda xml: xml.replace('<use   name="vdt_headers"/>\n', ""),
    )
