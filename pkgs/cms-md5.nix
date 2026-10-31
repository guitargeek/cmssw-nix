{ stdenv, src, version ? "1.0.0" }:

# The small md5 library CMS uses (scram tool "md5"). The 1.0.0 branch
# ships md5.c/md5.h; 2.0.0 the same code as edm_md5.c/edm_md5.h, in a
# namespace of its own (and so compiled as C++). The library is libcms-md5
# either way.
stdenv.mkDerivation {
  pname = "cms-md5";
  inherit version src;

  buildPhase = ''
    runHook preBuild
    # (edm_md5.c is C++ despite its name: the namespace is the point of it)
    if [ -f edm_md5.c ]; then
      name=edm_md5; compile="$CXX -x c++"
    else
      name=md5; compile=$CC
    fi
    $compile $name.c -shared -fPIC -o libcms-md5.so
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    install -Dm644 $name.h -t $out/include
    install -Dm755 libcms-md5.so -t $out/lib
    runHook postInstall
  '';
}
