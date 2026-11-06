# hls4mlEmulatorExtras: the interface CMSSW's L1 trigger emulators use to
# load hls4ml-generated models (hls4ml/emulator.h, plus the small
# libemulator_interface library behind it). L1Trigger/L1TGlobal needs it to
# compile its AXOL1TL and CICADA anomaly-detection conditions; the models
# themselves (the AXOL1TL and CICADA externals) are loaded at run time, only
# by menus that use those conditions.
{ lib, stdenv, src }:

stdenv.mkDerivation {
  pname = "hls4ml-emulator-extras";
  version = "1.1.4";
  inherit src;

  # The model loader dlopens a model by bare file name, which on Linux
  # searches LD_LIBRARY_PATH; macOS's dlopen searches only the dyld paths
  # (DYLD_LIBRARY_PATH, which System Integrity Protection strips). Try the
  # LD_LIBRARY_PATH directories, where pkgs/hls4ml-models.nix puts the
  # models, when the bare name does not resolve.
  postPatch = ''
    substituteInPlace src/hls4ml/emulator.cc \
      --replace-fail '#include "emulator.h"' '#include "emulator.h"
    #include <cstdlib>' \
      --replace-fail '    model_lib_ = dlopen(model_lib_name.c_str(), RTLD_LAZY | RTLD_LOCAL);' \
                     '    model_lib_ = dlopen(model_lib_name.c_str(), RTLD_LAZY | RTLD_LOCAL);
        if (!model_lib_ && std::getenv("LD_LIBRARY_PATH")) {
          std::string const path = std::getenv("LD_LIBRARY_PATH");
          for (std::size_t b = 0, e; !model_lib_ && b < path.size(); b = e + 1) {
            e = path.find(":", b);
            if (e == std::string::npos) e = path.size();
            if (e > b)
              model_lib_ = dlopen((path.substr(b, e - b) + "/" + model_lib_name).c_str(), RTLD_LAZY | RTLD_LOCAL);
          }
        }'
  '';

  buildPhase = ''
    runHook preBuild
    $CXX -O2 -fPIC -std=c++17 -shared -I include/hls4ml \
      -o libemulator_interface.so src/hls4ml/emulator.cc \
      ${lib.optionalString stdenv.hostPlatform.isDarwin
        "-Wl,-install_name,$out/lib/libemulator_interface.so"}
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib
    cp libemulator_interface.so $out/lib/
    cp -r include $out/include
    runHook postInstall
  '';
}
