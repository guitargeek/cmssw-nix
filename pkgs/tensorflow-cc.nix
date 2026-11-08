# The TensorFlow C++ API (scram tool "tensorflow-cc"), taken from the
# binary wheel nixpkgs packages TensorFlow as. The 20_1 reconstruction
# evaluates TensorFlow graphs in the standard Run 3 configuration: the track
# selection DNN of every tracking iteration, mkFit's candidate DNN, the
# DeepCore seeding, DeepTau. cmsdist builds TensorFlow from source; nixpkgs
# no longer can, but the wheel carries everything a C++ user needs:
# libtensorflow_cc and libtensorflow_framework, and the headers - with the
# Eigen, absl and protobuf versions the libraries were built against.
#
# Verified on aarch64-darwin (the wheel links the system libc++, as
# everything else built here does) and x86_64-linux (where it links gcc's
# libstdc++ and libgcc_s, which autoPatchelfHook finds in the compiler's lib
# output).
{ lib, stdenv, unzip, fixDarwinDylibNames, autoPatchelfHook, wheel }:

let
  so = if stdenv.hostPlatform.isDarwin then "dylib" else "so";
  # libtensorflow_cc.2.dylib on darwin, libtensorflow_cc.so.2 on Linux
  versioned = name: if stdenv.hostPlatform.isDarwin then "${name}.2.dylib" else "${name}.so.2";
in
stdenv.mkDerivation {
  pname = "tensorflow-cc";
  inherit (wheel) version;
  src = wheel.src;

  nativeBuildInputs = [ unzip ]
    ++ lib.optional stdenv.hostPlatform.isDarwin fixDarwinDylibNames
    ++ lib.optional stdenv.hostPlatform.isLinux autoPatchelfHook;
  # the libstdc++ and libgcc_s the Linux libraries link, for autoPatchelfHook
  buildInputs = lib.optional stdenv.hostPlatform.isLinux stdenv.cc.cc.lib;

  # only the C++ libraries and the headers, not the 220 MB python package
  unpackPhase = ''
    runHook preUnpack
    unzip -q $src 'tensorflow/${versioned "libtensorflow_cc"}' \
      'tensorflow/${versioned "libtensorflow_framework"}' 'tensorflow/include/*'
    runHook postUnpack
  '';

  dontBuild = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib
    for l in libtensorflow_cc libtensorflow_framework; do
      case $l in
        libtensorflow_cc) v=tensorflow/${versioned "libtensorflow_cc"} ;;
        *) v=tensorflow/${versioned "libtensorflow_framework"} ;;
      esac
      install -m 755 $v $out/lib/
      ln -s $(basename $v) $out/lib/$l.${so}
    done
    # Not $out/include: the cc-wrapper passes every buildInput's include/
    # as -isystem, after the nixpkgs Eigen; and clang drops an -I that is
    # also an -isystem. TensorFlow's headers need its own Eigen (3.5-dev)
    # found first, which the -I of gen/CMakeLists.txt does for this
    # directory.
    mkdir -p $out/include
    cp -r tensorflow/include $out/include/tensorflow-cc

    # The SavedModel tag constants are the one header of the C++ API the
    # wheel leaves out (PhysicsTools/TensorFlow includes it). As in the
    # TensorFlow sources:
    cat > $out/include/tensorflow-cc/tensorflow/cc/saved_model/tag_constants.h <<'EOF'
    #ifndef TENSORFLOW_CC_SAVED_MODEL_TAG_CONSTANTS_H_
    #define TENSORFLOW_CC_SAVED_MODEL_TAG_CONSTANTS_H_

    namespace tensorflow {

    /// Tag for the `gpu` graph.
    constexpr char kSavedModelTagGpu[] = "gpu";

    /// Tag for the `tpu` graph.
    constexpr char kSavedModelTagTpu[] = "tpu";

    /// Tag for the `serving` graph.
    constexpr char kSavedModelTagServe[] = "serve";

    /// Tag for the `training` graph.
    constexpr char kSavedModelTagTrain[] = "train";

    }  // namespace tensorflow

    #endif  // TENSORFLOW_CC_SAVED_MODEL_TAG_CONSTANTS_H_
    EOF
    sed -i 's/^    //' $out/include/tensorflow-cc/tensorflow/cc/saved_model/tag_constants.h
    runHook postInstall
  '';

  meta = {
    description = "TensorFlow C++ API (libraries and headers from the binary wheel)";
    homepage = "https://www.tensorflow.org";
    license = lib.licenses.asl20;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
}
