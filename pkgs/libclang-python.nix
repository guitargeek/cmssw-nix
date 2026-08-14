{ stdenvNoCC, llvmPackages }:

# The libclang python bindings (clang.cindex), taken from the clang source
# tree and pinned to the matching libclang shared library. Needed by the
# CondFormats serialization generator.
stdenvNoCC.mkDerivation {
  pname = "libclang-python";
  version = llvmPackages.libclang.version;

  src = llvmPackages.libclang.src;

  dontConfigure = true;
  dontBuild = true;

  installPhase = ''
    dir=$(find . -type d -path "*bindings/python/clang" | head -1)
    if [ -z "$dir" ]; then
      echo "clang python bindings not found in the source tree" >&2
      exit 1
    fi
    mkdir -p $out/site-packages
    cp -r "$dir" $out/site-packages/clang
    chmod -R u+w $out/site-packages

    # point the bindings at the store's libclang, so no runtime search is
    # needed (Config is defined in cindex.py, appending works)
    cat >> $out/site-packages/clang/cindex.py <<EOF

Config.library_file = "${llvmPackages.libclang.lib}/lib/libclang.so"
EOF
  '';
}
