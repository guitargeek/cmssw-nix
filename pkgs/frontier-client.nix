{ stdenv
, lib
, src
, version ? "2.8.21"
, expat
, openssl
, zlib
, pacparser
}:

# The Frontier client: the HTTP transport CMS uses to read conditions out of
# the central Oracle databases through a caching squid hierarchy. CORAL's
# FrontierAccess backend is a thin layer on top of this library, and without
# it a PoolDBESSource can only talk to a local sqlite file.
#
# Plain Makefile, no configure. It bundles its own minimal HTTP client
# (client/http) rather than using libcurl, so the dependency list is short:
# expat for the XML responses, openssl for https, zlib for the compressed
# payloads. pacparser (proxy auto-config) is dlopened at runtime rather than
# linked, but its header is a hard compile dependency all the same.
stdenv.mkDerivation {
  pname = "frontier-client";
  inherit version src;

  buildInputs = [ expat openssl zlib pacparser ];

  sourceRoot = "source/client";

  postPatch = ''
    patchShebangs . || true

    # pacparser_setmyip returned void when this was written; it returns int
    # as of pacparser 1.4, and this file's own definition of the dlopen shim
    # has to agree with the header it includes. Non-zero is pacparser's
    # "success", matching what the other int-returning wrappers here do.
    sed -i \
      -e 's|^static void (\*pp_setmyip)(const char \*);$|static int (*pp_setmyip)(const char *);|' \
      -e '/^void pacparser_setmyip/,/^ }$/{
            s|^void pacparser_setmyip|int pacparser_setmyip|
            s|^    return;$|    return 0;|
            s|^  (\*pp_setmyip)(ip);$|  (*pp_setmyip)(ip);\n  return 1;|
          }' \
      pacparser-dlopen.c

    # sed does not complain when a pattern matches nothing, and a silently
    # unpatched file only shows up as a confusing compile error later
    grep -q '^int pacparser_setmyip' pacparser-dlopen.c \
      || { echo "pacparser_setmyip patch did not apply"; exit 1; }
    grep -q '^static int (\*pp_setmyip)' pacparser-dlopen.c \
      || { echo "pp_setmyip pointer patch did not apply"; exit 1; }
  '';

  dontConfigure = true;

  # frontier_mem_alloc/_free are tentative definitions in a shared header, so
  # every translation unit that includes it defines them. That is fine under
  # the pre-gcc-10 -fcommon default and a multiple-definition link error
  # under -fno-common. The Makefile sets COPT itself, so the flag has to come
  # in through the compiler wrapper rather than CFLAGS.
  NIX_CFLAGS_COMPILE = "-fcommon";

  # Deliberately not the "all" target: it also links fn-req.static, which
  # needs static expat/openssl/zlib that nixpkgs does not ship by default.
  # The shared library and the fn-req probe tool are what we want.
  buildFlags = [ "htclient" "libfrontier_client.so" "fn-req" ];

  # libfrontier_client.so depends on http/.libs, which is a directory the
  # htclient target produces as a side effect with no rule of its own - so a
  # parallel make happily starts the link before the http objects exist.
  enableParallelBuilding = false;

  # The Makefile's own install target writes to a hardcoded ./dist and then
  # copies from it; doing it here is shorter than fighting it.
  installPhase = ''
    runHook preInstall

    mkdir -p $out/lib $out/include $out/bin
    cp libfrontier_client.so.${version} $out/lib/
    ln -s libfrontier_client.so.${version} $out/lib/libfrontier_client.so.2
    ln -s libfrontier_client.so.${version} $out/lib/libfrontier_client.so
    cp -r include/frontier_client $out/include/
    cp fn-req $out/bin/

    runHook postInstall
  '';

  meta = {
    description = "Frontier client: HTTP access to relational databases, used by CMS conditions";
    homepage = "https://github.com/fermitools/frontier";
    license = lib.licenses.bsd3;
    platforms = [ "x86_64-linux" ];
  };
}
