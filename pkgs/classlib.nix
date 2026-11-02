# classlib: the general-purpose C++ library (I/O, sockets, time, errors)
# that CMS still carries as an external for DQMServices/Core, whose DQMNet
# (the network protocol to the online DQM GUI) is written against it. Built
# as cmsdist does: autotools, with pcre and without the compression back
# ends, which nothing in CMSSW uses.
{ lib, stdenv, pcre, src }:

stdenv.mkDerivation {
  pname = "classlib";
  version = "3.1.3";
  inherit src;

  buildInputs = [ pcre ];

  configureFlags = [
    "--without-zlib"
    "--without-bz2lib"
    "--without-lzma"
    "--without-lzo"
    "--without-openssl"
    "--with-pcre-includes=${lib.getDev pcre}/include"
    "--with-pcre-libraries=${lib.getLib pcre}/lib"
  ];

  # Linux-only includes: the BSD sysctl interface lives in <sys/sysctl.h>
  # on macOS, and TimeInfo.cpp only needs clock_t from glibc's <bits/types.h>
  postPatch = lib.optionalString stdenv.hostPlatform.isDarwin ''
    for f in classlib/sysapi/{FileNameLock,SystemInfo,TimeInfo}.h; do
      substituteInPlace $f --replace-fail "<linux/sysctl.h>" "<sys/sysctl.h>"
    done
    substituteInPlace src/utils/TimeInfo.cpp \
      --replace-fail "#include <bits/types.h>" "" --replace-fail "__clock_t" "clock_t"
  '';

  # configure links the compression libraries even without their back ends
  # (cmsdist edits them out of the Makefile the same way)
  postConfigure = ''
    sed -i -E 's/ -l(z|bz2|crypto|lzma|lzo2)\b//g' Makefile
  '';

  # the default flags are -ansi -pedantic -Werror; cmsdist overrides them
  # at make time too
  preBuild = ''
    makeFlagsArray+=("CXXFLAGS=-O2 -std=c++11")
  '';

  enableParallelBuilding = true;
}
