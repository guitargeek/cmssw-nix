{ stdenv, src }:

stdenv.mkDerivation {
  pname = "cms-md5";
  version = "1.0.0";

  inherit src;

  buildPhase = ''
    runHook preBuild
    $CC md5.c -shared -fPIC -o libcms-md5.so
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm644 md5.h -t $out/include
    install -Dm755 libcms-md5.so -t $out/lib
    runHook postInstall
  '';
}
