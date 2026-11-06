"""CMSSW on clang, libc++, macOS and non-glibc systems.

CMSSW is developed against gcc and libstdc++ on Linux. Nearly all of these
are portability fixes that compile to the same thing there: missing includes,
standard code that libstdc++ happens to be lenient about, glibc-only
functions. See docs/macos.md for the ones worth knowing about.
"""
from common import *  # noqa: F401,F403

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
    edit(path, define_uuid_str_len, required=release_cycle >= (11, 0))  # (10_6 does not use it)

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
    "cmssw/RecoTracker/LSTCore/src/ModuleMethods.h": ["<fstream>"],
    # iterates a reco::TrackCollection with only TrackFwd.h in sight
    "cmssw/RecoTracker/FinalTrackSelectors/interface/TrackMVAClassifier.h":
        ['"DataFormats/TrackReco/interface/Track.h"'],
}
# ... of which 20_1 includes these itself
includes_10_6_only = {
    "cmssw/Geometry/HGCalCommonData/interface/HGCalDDDConstants.h",
    "cmssw/Geometry/HGCalCommonData/interface/HGCalParameters.h",
    "cmssw/SimDataFormats/TrackerDigiSimLink/interface/StripCompactDigiSimLinks.h",
    "cmssw/RecoTracker/FinalTrackSelectors/interface/TrackMVAClassifier.h",
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
    # (some are only missing in 10_6)
    edit(path, add_includes, required=release_cycle < (11, 0) or path not in includes_10_6_only)

# --- a non-const operator< (20_1) ------------------------------------------
# RecoPPS/Local partial_sorts CTPPSPixelLocalTracks with std::less<>, which
# libc++ calls on const references; libstdc++ compares through the iterators.
for path, sig in [("cmssw/DataFormats/CTPPSReco/interface/CTPPSPixelLocalTrack.h",
                   "bool operator<(const CTPPSPixelLocalTrack& r)"),
                  ("cmssw/DataFormats/CTPPSReco/src/CTPPSPixelLocalTrack.cc",
                   "bool CTPPSPixelLocalTrack::operator<(const CTPPSPixelLocalTrack &r)")]:
    if os.path.exists(path):
        edit(path, required=release_cycle >= (11, 0), editor=lambda src, sig=sig: src.replace(sig + ";", sig + " const;")
             .replace(sig + " {", sig + " const {"))
# LST's output converter takes std::ranges::size of a TrajectorySeed's hit
# range, whose OwnVector iterators libc++ does not count as a sized range.
path = "cmssw/RecoTracker/LST/plugins/LSTOutputConverter.cc"
if os.path.exists(path):
    edit(path, lambda src: src.replace("std::ranges::size(pixelSeeds[iSeed].recHits())",
                                       "pixelSeeds[iSeed].nHits()"))

# --- a persistent std::atomic<int> under libc++ (20_1) ---------------------
# DetSetVectorNew's Item keeps its data offset in a std::atomic<int>, which
# is written out (the clusters and digis of every RAW and RECO file). ROOT
# has no notion of atomics: it streams the class the standard library
# implements std::atomic<int> with. libstdc++'s base class holds a plain int
# (_M_i), which ROOT can write; libc++'s holds a __cxx_atomic_impl wrapper,
# which has no dictionary, so writing a DetSetVectorNew fails ("data member
# __a_ will not be saved", a fatal ROOT error in cmsRun). Under libc++, let
# ROOT (rootcling and the interpreter, which define __CLING__) see the int
# the atomic holds - same size, alignment and offset - and initialize()
# without the atomic exchange; the compiled code, the dictionary's
# included, keeps the atomic.
path = "cmssw/DataFormats/Common/interface/DetSetVectorNew.h"
if os.path.exists(path):
    def int_for_root(src):
        decl = ("        mutable std::atomic<int> offset;\n"
                "        bool initialize() const {\n"
                "          int expected = -1;\n"
                "          return offset.compare_exchange_strong(expected, -2);\n"
                "        }\n")
        if decl not in src:
            # 10_6 does it already: the atomic only #ifdef DSVN_USE_ATOMIC,
            # which its dictionaries do not define
            if "DSVN_USE_ATOMIC" in src:
                return src
            raise SystemExit(f"{path}: Item::offset not where expected")
        return src.replace(decl,
            "#if defined(__CLING__) && defined(_LIBCPP_VERSION)\n"
            "        mutable int offset;\n"
            "        bool initialize() const {\n"
            "          if (offset != -1)\n"
            "            return false;\n"
            "          offset = -2;\n"
            "          return true;\n"
            "        }\n"
            "#else\n" + decl + "#endif\n")
    edit(path, int_for_root, required=release_cycle >= (11, 0))  # (10_6 is not atomic)

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
    edit(path, constexpr_abs, required=release_cycle >= (11, 0))

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
    edit(path, iterators_from_range, required=release_cycle >= (11, 0))

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

# --- payload type names without libc++'s inline namespace (all versions) ---
# The conditions database stores each payload's C++ type name as libstdc++
# spells it, and the reader compares it with the demangled typeid of the
# type it asks for (cond::demangledName). libc++ demangles its containers
# inside its inline namespace, std::__1::vector<...>, so every payload of a
# standard type (DT's KeyList: std::vector<unsigned long long>) is refused
# with "Type mismatch". Drop the inline namespace, as libstdc++'s names have
# none for these types.
if os.path.exists(path):
    def without_libcxx_namespace(src):
        # (10_6 spells the line with spaces inside the parentheses)
        m = re.search(r"\n[ \t]*ret\.erase\(\s*std::remove\(\s*ret\.begin\(\),\s*ret\.end\(\),\s*' '\s*\),\s*ret\.end\(\)\s*\);[ \t]*\n", src)
        if m is None:
            raise SystemExit("CondDB Utils.h: the demangled name's clean-up not where expected")
        return (src[:m.end()] +
                "      for (std::string::size_type p; (p = ret.find(\"std::__1::\")) != std::string::npos;)\n"
                "        ret.erase(p + 5, 5);\n" + src[m.end():])
    edit(path, without_libcxx_namespace)

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
# layout" - even one written by the same job. Read through a read-only
# stream buffer over the bytes instead, which copies nothing, as before with
# libstdc++. (The same change as proposed upstream, which also covers the
# HDF5 conditions source and the XML converter; neither is built here.)
INPUT_MEMORY_BUFFER = """#ifndef CondFormats_Serialization_InputMemoryBuffer_h
#define CondFormats_Serialization_InputMemoryBuffer_h

#include <cstddef>
#include <streambuf>

namespace cond {
  namespace serialization {

    // A read-only stream buffer over serialized data in memory, without copying it.
    // std::stringbuf::pubsetbuf cannot be used for this: its effect is
    // implementation-defined, and libc++ ignores it.
    class InputMemoryBuffer : public std::streambuf {
    public:
      InputMemoryBuffer(const void* data, std::size_t size) {
        char* begin = const_cast<char*>(static_cast<const char*>(data));
        setg(begin, begin, begin + size);
      }
    };

  }  // namespace serialization
}  // namespace cond

#endif
"""
path = "cmssw/CondCore/CondDB/interface/Serialization.h"
if os.path.exists(path):
    with open("cmssw/CondFormats/Serialization/interface/InputMemoryBuffer.h", "w") as f:
        f.write(INPUT_MEMORY_BUFFER)

    def deserialize_in_place(src):
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
            "serialization::InputMemoryBuffer sdataBuf(payloadData.data(), payloadData.size());\n"
            "      std::istream dataBuffer(&sdataBuf);",
            src)
        include = '#include "CondFormats/Serialization/interface/Archive.h"\n'
        if (n1, n2) != (1, 1) or include not in src:
            raise SystemExit("CondDB Serialization.h: default_deserialize not where expected")
        return src.replace(include, include + '#include "CondFormats/Serialization/interface/InputMemoryBuffer.h"\n', 1)
    edit(path, deserialize_in_place)

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
        # (20_1 still has the MessageLogger one)
        edit(path, required=release_cycle < (11, 0) or path.endswith("MessageLogger.cc"),
             editor=lambda src, old=old, new=new: src.replace(old, new))

# --- make_shared and noexcept(false) destructors (10_6) ---------------------
# The 10_6 framework declares many EventSetup components' destructors
# noexcept(false). libc++ 11's make_shared control block holds the object as
# a member, and its own implicit destructor then cannot be as noexcept as the
# base it overrides. A shared_ptr made from new keeps the object out of the
# control block; ComponentMaker is the one place every ES module goes through.
path = "cmssw/FWCore/Framework/interface/ComponentMaker.h"
if os.path.exists(path):
    edit(path, required=release_cycle < (11, 0), editor=lambda src: src.replace(
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
    edit(path, vector_size_for_clang, required=release_cycle < (11, 0))
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
    edit(path, shufflevector_for_clang, required=release_cycle < (11, 0))

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
        edit(path, required=release_cycle >= (11, 0), editor=lambda src: src.replace("map<const int, ", "map<int, ")
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
        edit(path, required=release_cycle >= (11, 0), editor=lambda src: re.sub(r"\bulong\b", "unsigned long", src))
