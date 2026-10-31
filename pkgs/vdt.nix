{
  lib,
  stdenv,
  fetchFromGitHub,
  cmake,
  python3,
}:

stdenv.mkDerivation (finalAttrs: {
  pname = "vdt";
  version = "0.4.6";

  src = fetchFromGitHub {
    owner = "dpiparo";
    repo = "vdt";
    tag = "v${finalAttrs.version}";
    hash = "sha256-wnnFby4J4k0TQcLwy4wiEdldJVzc9+yIxwESaI+KmqY=";
  };

  # CMake 4 removed compatibility with versions < 3.5
  postPatch = ''
    substituteInPlace CMakeLists.txt \
      --replace-fail "cmake_minimum_required(VERSION 3.2 FATAL_ERROR)" \
                     "cmake_minimum_required(VERSION 3.10)"
  '';

  nativeBuildInputs = [
    cmake
    python3
  ];

  cmakeFlags = [
    # the SSE option (on by default) adds -msse, which only x86 compilers accept
    (lib.cmakeBool "SSE" stdenv.hostPlatform.isx86)
  ];

  meta = {
    description = "Vectorisable, fast and inline-able double and single precision math functions";
    homepage = "https://github.com/dpiparo/vdt";
    changelog = "https://github.com/dpiparo/vdt/blob/v${finalAttrs.version}/ReleaseNotes.txt";
    license = lib.licenses.lgpl3Plus;
    maintainers = with lib.maintainers; [ guitargeek ];
    platforms = lib.platforms.unix;
  };
})
