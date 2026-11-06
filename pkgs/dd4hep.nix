# DD4hep: the detector description toolkit. CMSSW_20_1 builds its geometry
# on it — DetectorDescription/DDCMS and every Geometry/*Builder package need
# it in their main libraries (in the 10_6 era dd4hep was an optional second
# code path that could simply be pruned).
#
# The core plus DDG4, the Geant4 bridge. DDG4 is here because
# SimG4Core/Geometry needs it even on the DDD path this flake uses:
# DDG4ProductionCuts declares one constructor taking a DD4hep
# Geant4GeometryMaps::VolumeMap, so <DDG4/Geant4GeometryInfo.h> is included
# unconditionally and the header does not compile without it. LCIO, EDM4hep,
# HepMC3 and GEAR stay off.
{ lib, stdenv, cmake, fixDarwinDylibNames, root, boost, xercesc, python3, geant4, src, version }:

stdenv.mkDerivation {
  pname = "dd4hep";
  inherit version src;

  # On darwin, DD4hep installs its libraries under @rpath-relative install
  # names, which only resolve for a consumer that carries DD4hep's lib/ in
  # its own rpaths. Nothing in nixpkgs does that on darwin - the libraries
  # are expected to name themselves absolutely - so the CMSSW libraries that
  # link DDCore fail to load. Give them absolute install names.
  nativeBuildInputs = [ cmake ] ++ lib.optional stdenv.hostPlatform.isDarwin fixDarwinDylibNames;
  buildInputs = [ root boost xercesc python3 geant4 ];

  # The graphics plugin links ROOT::ROOTHistDraw (a ROOT 7 target nixpkgs'
  # ROOT does not export). CMSSW only uses DDCore/DDParsers, so drop it.
  postPatch = ''
    grep -q 'dd4hep_add_plugin(DDCoreGraphics' DDCore/CMakeLists.txt
    sed -i '/dd4hep_add_plugin(DDCoreGraphics/,+2d' DDCore/CMakeLists.txt

    # The plugin manager finds factories through <library>.components files
    # in the directories of a search path variable, which outside the
    # thisdd4hep.sh environment holds neither DD4hep's own lib/ (the XML
    # processor, the shape constructors) nor anything else. Always look in
    # lib/ as well.
    substituteInPlace GaudiPluginService/src/PluginServiceV2.cpp \
      --replace-fail 'search_path = envPtr ? envPtr : "/usr/lib64:/usr/lib:/usr/local/lib";' \
                     'search_path = std::string(envPtr ? envPtr : "") + sep + "'"$out"'/lib";'
    substituteInPlace GaudiPluginService/src/PluginServiceV1.cpp \
      --replace-fail 'std::string path = search_path ? std::string(search_path) : "/usr/lib64:/usr/lib:/usr/local/lib";' \
                     'std::string path = (search_path ? std::string(search_path) : std::string()) + sep + "'"$out"'/lib";'
  '' + lib.optionalString stdenv.hostPlatform.isDarwin ''

    # On macOS the search path variable is DYLD_LIBRARY_PATH, which System
    # Integrity Protection strips from the environment of anything started
    # through /bin or /usr/bin, and which redirects every library lookup of
    # the process when set. DD4hep's own environment scripts set
    # DD4HEP_LIBRARY_PATH for this (thisdd4hep.sh); read that one instead.
    substituteInPlace GaudiPluginService/src/PluginServiceV1.cpp \
      --replace-fail 'const char* envVar = "DYLD_LIBRARY_PATH";' 'const char* envVar = "DD4HEP_LIBRARY_PATH";'
    substituteInPlace GaudiPluginService/src/PluginServiceV2.cpp \
      --replace-fail 'const std::string envVar = "DYLD_LIBRARY_PATH";' 'const std::string envVar = "DD4HEP_LIBRARY_PATH";'


    # DDCore loads its plugin manager by bare name through gSystem->Load
    # (unless DD4HEP_PLUGINMGR says otherwise). On Linux the name resolves
    # because the library is already loaded by then, and dlopen of a loaded
    # soname needs no search; ROOT on macOS looks for the file on its library
    # path first and gives up. Default to the absolute path instead.
    grep -q 'plugin_name = "libDD4hepGaudiPluginMgr";' DDCore/src/Plugins.cpp \
      || { echo "dd4hep: plugin manager name not where expected" >&2; exit 1; }
    sed -i "s|plugin_name = \"libDD4hepGaudiPluginMgr\";|plugin_name = \"$out/lib/libDD4hepGaudiPluginMgr.dylib\";|" \
      DDCore/src/Plugins.cpp
  '';

  cmakeFlags = [
    "-DDD4HEP_USE_XERCESC=ON"
    "-DBUILD_TESTING=OFF"
    "-DBUILD_DOCS=OFF"
    "-DDD4HEP_BUILD_EXAMPLES=OFF"
    "-DCMAKE_CXX_STANDARD=20"
    # Off by default. Without it dd4hep does not fail, it prints
    # "Not Using geant4, not building DDG4" and carries on, so the miss
    # only surfaces as a missing libDDG4.so at the CMSSW link step.
    "-DDD4HEP_USE_GEANT4=ON"
  ];

  # DD4HEP_BUILD_PACKAGES is one CMake variable holding a space-separated list
  # (dd4hep calls SEPARATE_ARGUMENTS on it). It cannot go in cmakeFlags, whose
  # entries are word-split by the shell - that silently drops DDG4 and builds
  # only DDRec, which then fails much later as a missing libDDG4.so.
  preConfigure = ''
    cmakeFlagsArray+=("-DDD4HEP_BUILD_PACKAGES=DDRec DDG4")
  '';

  # The .components files name each factory's library by file name, which
  # the plugin manager dlopens as is; on darwin a bare name is only looked
  # up on the dyld search paths. Name them absolutely.
  postInstall = ''
    sed -i "s|^v2::lib|v2::$out/lib/lib|" $out/lib/*.components
  '';

  # the ROOT setup hook must not run at two offsets (see pkgs/cmssw.nix)
  dontUseCmakeBuildDir = false;
}
