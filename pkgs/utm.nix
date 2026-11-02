# utm: the CMS L1 trigger menu library (XML menu parsing and the event-setup
# view of a menu). The L1TUtm* payloads in CondFormats/L1TObjects wrap it,
# and L1Trigger/L1TGlobal, HLTcore's L1 prescale and seed readers, the PAT
# trigger matching and NanoAOD's L1 bits all go through them. Built like
# cmsdist does; at run time, menus are validated against the XML schemas
# installed in share/utm/xsd (found through UTM_XSD_DIR, set by the setup
# hook).
{ lib, stdenv, xercesc, boost, src }:

stdenv.mkDerivation {
  pname = "utm";
  version = "0.14.1";
  inherit src;

  buildInputs = [ xercesc boost ];

  configurePhase = ''
    runHook preConfigure
    # Boost.System has been header-only for years, and recent boost no
    # longer ships the stub library
    sed -i 's/-lboost_system//' */Makefile.default
    ./configure
    runHook postConfigure
  '';

  # The libraries are .so files on every platform. On macOS they get their
  # install name from the start (the default would be the bare file name)
  # and link each other by it.
  preBuild = ''
    makeFlagsArray+=(
      "CXX=$CXX"
      "AR=$CXX -shared -fPIC ${lib.optionalString stdenv.hostPlatform.isDarwin
        "-Wl,-install_name,$out/lib/\\$(LIBRARY)"}"
      "XERCES_C_BASE=${lib.getDev xercesc}"
      "BOOST_BASE=${lib.getDev boost}"
    )
  '';

  buildFlags = [ "all" ];

  installPhase = ''
    runHook preInstall
    make install PREFIX=$out "''${makeFlagsArray[@]}"
    # the schemas land in the prefix itself (menu.xsd, the other *.xsd it
    # includes, and xsd-type/)
    mkdir -p $out/share/utm/xsd
    mv $out/*.xsd $out/xsd-type $out/share/utm/xsd/
    runHook postInstall
  '';
}
