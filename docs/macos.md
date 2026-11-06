# CMSSW on macOS

Both releases build on `aarch64-darwin` (Apple silicon). On macOS the 20_1
package targets macOS 26 or later: `FWCore/ParameterSet` parses numbers with
the floating-point `std::from_chars`, which the system C++ library only has
from that version on.

CMSSW has only ever been developed against gcc and libstdc++ on Linux, so
the macOS port is mostly about what clang and libc++ do differently. The
fixes live in [gen/prepare/](../gen/prepare/) (each with a comment saying
why), and nearly all of them are plain portability fixes that compile to
the same thing on Linux. The ones worth knowing about:

* **Undefined behaviour that libstdc++ forgives.** A map iterator
  stepped back past `begin()` in the HCAL reconstruction, a vector indexed
  out of bounds in the strip conditions: harmless with libstdc++, a crash
  with libc++. nixpkgs also builds against libc++ in its "fast" hardening
  mode, which turns such precondition violations into traps; the 20_1
  release and everything compiled against it turn that off, as Linux
  builds never check them either.
* **`std::stringbuf::pubsetbuf`**, which libc++ ignores: the conditions
  database read every payload as empty. The payloads are now read through
  a stream buffer over the bytes in memory.
* **Type names.** libc++ demangles its containers inside its inline
  namespace (`std::__1::vector`), and the conditions database compares the
  stored payload type name with the demangled one; the inline namespace is
  dropped before comparing.
* **Persistent `std::atomic`.** ROOT streams the class the standard library
  implements an atomic with, and libc++'s has no dictionary: the cluster
  collections' `DetSetVectorNew` keeps a plain `int` for ROOT under libc++.
* **The SIMD vector types.** Apple's arm64 ABI reports 8 for
  `__BIGGEST_ALIGNMENT__`, which made CMSSW fall back to a scalar
  implementation nothing else uses any more. The vector-extension one is
  used instead, as on every Linux build, with 10_6's gcc-only spellings
  fixed for clang.
* **Static destruction order.** Geant4 11 destroys the particle table's
  mutex before the table that locks it; glibc tolerates locking a
  destroyed mutex, macOS does not. The 20_1 Geant4 is patched.
* **One vtable per class is not a given.** A class whose virtual functions
  are all inline gets its vtable emitted, with hidden visibility, into every
  library that uses it. clang 17 and later compile a `dynamic_cast` to a
  `final` class into a single comparison against the class's vtable, which
  then fails whenever the object was built in another library: `typeid`
  says `SiPixelRecHit`, the cast returns null. The track associator found
  it by crashing; code that checks the cast would just have skipped the
  object. `gen/CMakeLists.txt` builds with `-fno-assume-unique-vtables` on
  macOS.
* **Weak symbols are coalesced across libraries.** TensorFlow's library
  exports protobuf's inline code as weak definitions, which dyld merges
  with those of any other protobuf in the process. So there is one
  protobuf, TensorFlow's version, for the release, ONNX Runtime and
  TensorFlow alike ([flake.nix](../flake.nix)).
* **Fortran COMMON blocks** are not merged across dylibs as they are
  across ELF shared objects: Tauola++ is built as one combined library
  ([pkgs/tauolapp.nix](../pkgs/tauolapp.nix)).
* **Bare library names do not resolve.** `dlopen("libfoo.so")` searches
  only `DYLD_LIBRARY_PATH`, which SIP strips from protected processes; the
  DD4hep plugin service and the hls4ml model loader are patched to search
  the paths the release sets up.
* **Case-insensitive filesystems**, the nix store included: the generated
  `*_cfi.py` files go into a `cfipython/` tree of their own (as with
  scram), because a generated `siStrip..._cfi.py` and a handwritten
  `SiStrip..._cfi.py` cannot share a directory.

The 10_6 build on macOS uses nixos-22.05, which predates most Apple
silicon work; `flake.nix` carries a small overlay for it (TBB 2020 for
arm64, ROOT 6.24 built as C++17 and able to target macOS 11). The plugin
manager reads `LD_LIBRARY_PATH` on macOS as well, so the examples work
unchanged on both platforms.
