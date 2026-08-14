# lwtnn: the lightweight trained neural network inference library, used by
# the 10_6-era DeepFlavour b-tagger (RecoBTag/Combined) and the lwtnn-based
# track classifier (RecoTracker/FinalTrackSelectors).
{ stdenv, cmake, boost, eigen, src }:

stdenv.mkDerivation {
  pname = "lwtnn";
  version = "2.9";
  inherit src;

  nativeBuildInputs = [ cmake ];
  buildInputs = [ boost eigen ];

  # bare size_t no longer compiles with gcc >= 11
  postPatch = ''
    sed -i -e 's/\bsize_t\b/std::size_t/g' -e 's/std::std::size_t/std::size_t/g' \
      -e '/#define NN_LAYER_CONFIG_HH/a #include <cstddef>' \
      include/lwtnn/NNLayerConfig.hh
  '';

  cmakeFlags = [
    "-DBUILTIN_BOOST=OFF"
    "-DBUILTIN_EIGEN=OFF"
  ];
}
