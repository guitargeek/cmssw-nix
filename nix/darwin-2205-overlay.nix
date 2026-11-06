# The fixes nixos-22.05 needs to build the 10_6 release's externals on
# aarch64-darwin. That nixpkgs predates most of the Apple silicon work, and
# a few of the packages the 10_6 release needs do not build there as
# shipped. They go in as an overlay, so that everything else in the set
# (ROOT 6.24 on the patched TBB, above all) is built against them.
(final: prev: {
  # built with LLVM 10 on clang platforms (its test suite
  # fails with 11+), whose compiler-rt is marked broken
  # here. The library itself is fine with the default
  # stdenv; only the tests are not.
  jemalloc = (prev.jemalloc.override { stdenv = final.stdenv; }).overrideAttrs (_: {
    doCheck = false;
  });

  # declared Linux-only, and links -framework System, which
  # the SDK this nixpkgs ships does not have (libSystem is
  # linked by default anyway). Later nixpkgs build the same
  # sources on darwin.
  pacparser = prev.pacparser.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      substituteInPlace src/Makefile --replace "-framework System" ""
    '';
    meta = old.meta // { platforms = final.lib.platforms.unix; };
  });

  # ROOT 6.24's interpreter carries the LLVM 9 clang driver,
  # which accepts only 10.x macOS deployment targets - it
  # predates Big Sur - and fails every rootcling run with
  # "invalid version number in MACOSX_DEPLOYMENT_TARGET=11.0",
  # the lowest target arm64 has. The relaxed check is the
  # one later LLVMs have. (At run time too: cling parses the
  # same variable, and every nix shell exports it.)
  #
  # And the C++ standard: nothing in the expression sets one,
  # so ROOT takes the compiler's default - C++17 for the gcc
  # 11 of Linux, which is what the 10_6 release and its
  # dictionaries are written for, but C++14 for the clang 11
  # of darwin, under which genreflex cannot parse them.
  root = prev.root.overrideAttrs (old: {
    cmakeFlags = (old.cmakeFlags or [ ]) ++ [ "-DCMAKE_CXX_STANDARD=17" ];
    postPatch = (old.postPatch or "") + ''
      f=interpreter/llvm/src/tools/clang/lib/Driver/ToolChains/Darwin.cpp
      grep -q 'HadExtra || Major != 10 || Minor >= 100' $f \
        || { echo "root: macOS version check not where expected" >&2; exit 1; }
      sed -i 's/HadExtra || Major != 10 || Minor >= 100/HadExtra || Major < 10 || Major >= 100 || Minor >= 100/' $f

      # cling parses the release's headers at run time with
      # libc++ in C++17 mode, which drops std::auto_ptr and
      # the other features C++17 removed - and the 10_6
      # headers still use them (LHEEventProduct,
      # GenEventInfoProduct). The compiler and genreflex get
      # libc++'s switch to keep them (gen/CMakeLists.txt);
      # cling needs it from the start, since a dictionary
      # payload's own defines come after <memory> has been
      # parsed once already.
      f=interpreter/cling/lib/Interpreter/CIFactory.cpp
      grep -q 'argvCompile.push_back("--target=arm64-apple-darwin20.3.0");' $f \
        || { echo "root: cling target setup not where expected" >&2; exit 1; }
      sed -i 's|argvCompile.push_back("--target=arm64-apple-darwin20.3.0");|&\n    argvCompile.push_back("-D_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES");|' $f

      # PyROOT loads its C++ backend by bare file name
      # whenever LD_LIBRARY_PATH or DYLD_LIBRARY_PATH is
      # set, leaving the search to dyld - which reads only
      # DYLD_LIBRARY_PATH, and SIP strips that from the
      # environment of anything started through a protected
      # binary, /usr/bin/env included. So `import ROOT`
      # works in the shell and fails in every
      # "#!/usr/bin/env" script run from it. Load the
      # backend from ROOT's own lib/ on darwin, which is
      # what PyROOT already does when neither variable is
      # set.
      f=bindings/pyroot/cppyy/cppyy/python/cppyy/__init__.py
      grep -q "if not any(var in os.environ for var in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH')):" $f \
        || { echo "root: cppyy backend lookup not where expected" >&2; exit 1; }
      sed -i "s|if not any(var in os.environ for var in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH')):|if sys.platform == 'darwin' or not any(var in os.environ for var in ('LD_LIBRARY_PATH','DYLD_LIBRARY_PATH')):|" $f
    '';
  });

  # the classic TBB the 10_6 framework is written against
  # has no arm64 Mac port; see the patch
  tbb = prev.tbb.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [ ../pkgs/tbb-2020-darwin-arm64.patch ];
    makeFlags = (old.makeFlags or [ ]) ++ final.lib.optional final.stdenv.hostPlatform.isAarch64 "arch=arm64";
  });
})
