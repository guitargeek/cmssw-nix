# 3.22 is what nixos-22.05 (used for the 10_6-era builds) ships
cmake_minimum_required(VERSION 3.22)
# macOS: compile against the SDK of the nix toolchain, never the host's.
# Left to itself, CMake asks xcrun for the system SDK; nixpkgs' cmake hook
# prevents that, but this project is configured by hand. The modern stdenv
# names its SDK in SDKROOT; the 22.05 one has none and wants an empty sysroot
# (its compiler wrapper supplies the headers), which is what its cmake hook
# passes. Building against the host SDK is not only impure: a library that
# records a recent SDK and has no LC_UUID - which the 22.05 linker never
# writes - is refused by dyld outright.
if(APPLE AND NOT DEFINED CMAKE_OSX_SYSROOT)
  set(CMAKE_OSX_SYSROOT "$ENV{SDKROOT}" CACHE PATH "macOS SDK (from SDKROOT, empty for the toolchain default)")
endif()
project(CMSSW LANGUAGES C CXX)

# C++ standard of the release era (20 for >= 13_X, 17 for the 10_6 era).
if(NOT DEFINED CMSSW_CXX_STANDARD)
  set(CMSSW_CXX_STANDARD 20)
endif()
set(CMAKE_CXX_STANDARD ${CMSSW_CXX_STANDARD})
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# macOS: keep the .so suffix for every library, the way ROOT itself does
# there. The name is baked into more places than the link line: the rootmaps
# genreflex writes (--rootmap-lib below), the library manifest the install
# step generates the cfi files from, and python's import of the pybind11
# modules, which only looks for .so.
#
# And allow undefined symbols at link time, which is the ELF default this
# build was written against: scram never links with -z defs either, and a
# number of BuildFiles rely on that. They are resolved when the library is
# loaded, and the plugin refresh at install time loads every plugin, so a
# symbol that is really missing still fails the build - just there rather
# than here.
if(APPLE)
  set(CMAKE_SHARED_LIBRARY_SUFFIX ".so")
  set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} -undefined dynamic_lookup")
endif()

if(NOT DEFINED CMSSW_VERSION)
  set(CMSSW_VERSION "CMSSW_UNKNOWN")
endif()

# ---------------------------------------------------------------------------
# Dependency management: all dependencies come from the nix build environment.
# The generated per-package CMakeLists reference scram tool names X through
# ${X_LIBRARIES} and ${X_INCLUDE_DIRECTORIES}, so define those here.
# ---------------------------------------------------------------------------

find_package(ROOT REQUIRED)
find_package(Boost REQUIRED COMPONENTS
  filesystem thread regex serialization program_options iostreams date_time)
find_package(CLHEP REQUIRED)
find_package(Eigen3 REQUIRED NO_MODULE)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 REQUIRED)
find_package(tinyxml2 REQUIRED)
find_package(fmt REQUIRED)

# oneTBB ships a cmake config; classic TBB 2020 (10_6 era) does not.
find_package(TBB QUIET)
if(NOT TBB_FOUND)
  find_library(TBB_PLAIN_LIBRARY NAMES tbb REQUIRED)
endif()

find_library(md5_LIBRARIES NAMES cms-md5 REQUIRED)
find_path(md5_INCLUDE_DIRECTORIES NAMES edm_md5.h md5.h REQUIRED)
# libuuid is part of libSystem on macOS
if(APPLE)
  set(libuuid_LIBRARIES "")
else()
  find_library(libuuid_LIBRARIES NAMES uuid REQUIRED)
endif()
find_library(openssl_LIBRARIES NAMES crypto REQUIRED)
find_path(openssl_INCLUDE_DIRECTORIES NAMES openssl/md5.h REQUIRED)
find_library(zlib_LIBRARIES NAMES z REQUIRED)
find_library(jemalloc_LIBRARIES NAMES jemalloc REQUIRED)
if(CMSSW_WITH_CPU_FEATURES)
  find_library(cpu_features_LIBRARIES NAMES cpu_features REQUIRED)
  find_path(cpu_features_INCLUDE_DIRECTORIES NAMES cpu_features/cpu_features_macros.h REQUIRED)
endif()
if(CMSSW_WITH_ALPAKA)
  find_path(alpaka_INCLUDE_DIRECTORIES NAMES alpaka/alpaka.hpp REQUIRED)
endif()
if(CMSSW_WITH_XERCESC)
  find_library(xerces-c_LIBRARIES NAMES xerces-c REQUIRED)
  find_path(xerces-c_INCLUDE_DIRECTORIES NAMES xercesc/parsers/XercesDOMParser.hpp REQUIRED)
endif()
if(CMSSW_WITH_HEPMC)
  find_library(hepmc_LIBRARIES NAMES HepMC REQUIRED)
  find_path(hepmc_INCLUDE_DIRECTORIES NAMES HepMC/GenEvent.h REQUIRED)
  # The fortran-io half of HepMC 2 (the HEPEVT_Wrapper statics the Pythia8
  # interface uses) is a separate tool: libHepMCfio references the hepevt_
  # fortran common, which only the Pythia8Interface plugin library defines
  # (see prepare_sources.py) - linking fio from every hepmc user would make
  # every one of them fail to dlopen.
  find_library(hepmcfio_LIBRARIES NAMES HepMCfio REQUIRED)
  set(hepmcfio_INCLUDE_DIRECTORIES ${hepmc_INCLUDE_DIRECTORIES})
  # scram tool names are case-insensitive; the GEM and ME0 validation
  # plugins spell this one "HepMC"
  set(HepMC_LIBRARIES ${hepmc_LIBRARIES})
  set(HepMC_INCLUDE_DIRECTORIES ${hepmc_INCLUDE_DIRECTORIES})
  # the same package (SimDataFormats/GeneratorProducts) also uses liblzma
  # through the scram tool name "xz"
  find_library(xz_LIBRARIES NAMES lzma REQUIRED)
  find_path(xz_INCLUDE_DIRECTORIES NAMES lzma.h REQUIRED)
endif()
# zstd: the streamer file format (IOPool/Streamer, and through it the DAQ
# input sources of EventFilter/Utilities)
if(CMSSW_WITH_ZSTD)
  find_library(zstd_LIBRARIES NAMES zstd REQUIRED)
  find_path(zstd_INCLUDE_DIRECTORIES NAMES zstd.h REQUIRED)
endif()
# bzip2 (scram tool bz2lib): the Geners archives of the JetMET correction
# tables
if(CMSSW_WITH_BZ2LIB)
  find_library(bz2lib_LIBRARIES NAMES bz2 REQUIRED)
  find_path(bz2lib_INCLUDE_DIRECTORIES NAMES bzlib.h REQUIRED)
endif()
if(CMSSW_WITH_VDT)
  # inline fast-math headers only (scram tool vdt_headers)
  find_path(vdt_headers_INCLUDE_DIRECTORIES NAMES vdt/vdtMath.h REQUIRED)
endif()
if(CMSSW_WITH_GSL)
  find_library(gsl_LIBRARIES NAMES gsl REQUIRED)
  find_library(_gslcblas NAMES gslcblas REQUIRED)
  list(APPEND gsl_LIBRARIES ${_gslcblas})
  find_path(gsl_INCLUDE_DIRECTORIES NAMES gsl/gsl_math.h REQUIRED)
endif()
if(CMSSW_WITH_FASTJET)
  find_library(fastjet_LIBRARIES NAMES fastjet REQUIRED)
  foreach(_l fastjetplugins fastjettools siscone siscone_spherical)
    find_library(_fj_${_l} NAMES ${_l})
    if(_fj_${_l})
      list(APPEND fastjet_LIBRARIES ${_fj_${_l}})
    endif()
  endforeach()
  find_path(fastjet_INCLUDE_DIRECTORIES NAMES fastjet/PseudoJet.hh REQUIRED)
  # fastjet-contrib installs a single combined library
  find_library(fastjet-contrib_LIBRARIES NAMES fastjetcontribfragile REQUIRED)
  find_path(fastjet-contrib_INCLUDE_DIRECTORIES NAMES fastjet/contrib/SoftDrop.hh REQUIRED)
endif()
if(CMSSW_WITH_HEPPDT)
  find_library(heppdt_LIBRARIES NAMES HepPDT REQUIRED)
  find_library(_heppid NAMES HepPID REQUIRED)
  list(APPEND heppdt_LIBRARIES ${_heppid})
  find_path(heppdt_INCLUDE_DIRECTORIES NAMES HepPDT/ParticleID.hh REQUIRED)
  # PhysicsTools/RecoUtils spells the tool "HepPDT"
  set(HepPDT_LIBRARIES ${heppdt_LIBRARIES})
  set(HepPDT_INCLUDE_DIRECTORIES ${heppdt_INCLUDE_DIRECTORIES})
endif()
if(CMSSW_WITH_LWTNN)
  find_library(lwtnn_LIBRARIES NAMES lwtnn REQUIRED)
  find_path(lwtnn_INCLUDE_DIRECTORIES NAMES lwtnn/LightweightNeuralNetwork.hh REQUIRED)
endif()
if(CMSSW_WITH_OPENBLAS)
  find_library(openblas_LIBRARIES NAMES openblas REQUIRED)
endif()
if(CMSSW_WITH_HEPMC3)
  find_library(hepmc3_LIBRARIES NAMES HepMC3 REQUIRED)
  find_path(hepmc3_INCLUDE_DIRECTORIES NAMES HepMC3/GenEvent.h REQUIRED)
endif()
if(CMSSW_WITH_ONNXRUNTIME)
  find_library(onnxruntime_LIBRARIES NAMES onnxruntime REQUIRED)
  # CMSSW includes it as <onnxruntime/onnxruntime_cxx_api.h>
  find_path(onnxruntime_INCLUDE_DIRECTORIES NAMES onnxruntime/onnxruntime_cxx_api.h REQUIRED)
endif()
if(CMSSW_WITH_XGBOOST)
  find_library(xgboost_LIBRARIES NAMES xgboost REQUIRED)
  find_path(xgboost_INCLUDE_DIRECTORIES NAMES xgboost/c_api.h REQUIRED)
endif()
if(CMSSW_WITH_HLS)
  find_path(hls_INCLUDE_DIRECTORIES NAMES ap_int.h REQUIRED)
endif()
if(CMSSW_WITH_HLS4ML_EMULATOR_EXTRAS)
  find_library(hls4mlEmulatorExtras_LIBRARIES NAMES emulator_interface REQUIRED)
  find_path(hls4mlEmulatorExtras_INCLUDE_DIRECTORIES NAMES hls4ml/emulator.h REQUIRED)
  # The AXOL1TL (and CICADA) externals are the trained models, which
  # L1Trigger/L1TGlobal loads through the emulator interface at run time,
  # only for menus with those conditions: nothing to compile or link against.
  set(AXOL1TL_LIBRARIES "")
endif()
if(CMSSW_WITH_UTM)
  foreach(_l tmeventsetup tmtable tmxsd tmgrammar tmutil)
    find_library(_utm_${_l} NAMES ${_l} REQUIRED)
    list(APPEND utm_LIBRARIES ${_utm_${_l}})
  endforeach()
  find_path(utm_INCLUDE_DIRECTORIES NAMES tmEventSetup/tmEventSetup.hh REQUIRED)
endif()
if(CMSSW_WITH_CLASSLIB)
  find_library(classlib_LIBRARIES NAMES classlib REQUIRED)
  find_path(classlib_INCLUDE_DIRECTORIES NAMES classlib/iobase/Socket.h REQUIRED)
endif()
if(CMSSW_WITH_PROTOBUF)
  find_package(protobuf CONFIG REQUIRED)
  set(protobuf_LIBRARIES protobuf::libprotobuf)
  get_target_property(protobuf_INCLUDE_DIRECTORIES protobuf::libprotobuf
                      INTERFACE_INCLUDE_DIRECTORIES)
endif()
if(CMSSW_WITH_GEANT4)
  find_package(Geant4 REQUIRED)
  set(geant4core_LIBRARIES ${Geant4_LIBRARIES})
  set(geant4core_INCLUDE_DIRECTORIES ${Geant4_INCLUDE_DIRS})
  set(geant4_LIBRARIES ${Geant4_LIBRARIES})
  set(geant4_INCLUDE_DIRECTORIES ${Geant4_INCLUDE_DIRS})

  # Geant4_DEFINITIONS is not optional decoration: it carries
  # -DG4MULTITHREADED, -DG4_STORE_TRAJECTORY and -DG4VERBOSE, and the first
  # two change the layout of G4Event and G4TrackingManager. Code compiled
  # without them against a toolkit built with them links cleanly and then
  # reads the wrong offsets at run time. scram passes the same flags through
  # its geant4 toolfile. Applied globally, like the include directories
  # above, because the generated per-package targets have no place to hang
  # tool-specific definitions.
  # add_definitions, not add_compile_definitions: Geant4 ships these already
  # -D-prefixed, which is what the older command expects verbatim.

  # ... and Geant4_DEFINITIONS is still not all of them. -DG4USE_STD11 is
  # shipped in Geant4_CXX_FLAGS instead, mixed in among -Wall and -pedantic,
  # and it is every bit as load-bearing: tls.hh keys on it, so without it
  # G4ThreadLocal expands to __thread where the toolkit's own build used
  # thread_local. 238 installed headers declare variables with that macro -
  # G4TransportationManager::fTransportationManager among them - so leaving
  # it out means the toolkit and everything compiled against it disagree
  # about how those variables are declared. It surfaces as a compile error
  # only where the type has a non-trivial destructor, which __thread forbids:
  # SimG4Core/CustomPhysics has a G4ThreadLocal std::unique_ptr and is the
  # one place in the release that fails loudly rather than quietly.
  #
  # Take the -D options out of the flags variable and leave the rest: the
  # warning options and -std are CMSSW's own business, and -ftls-model is
  # deliberately not forced on CMSSW code (see gen/setup-hook.sh, which sizes
  # the static-TLS surplus for the toolkit alone).
  set(_g4_flag_definitions "")
  separate_arguments(_g4_cxx_flags NATIVE_COMMAND "${Geant4_CXX_FLAGS}")
  foreach(_flag IN LISTS _g4_cxx_flags)
    if(_flag MATCHES "^-D")
      list(APPEND _g4_flag_definitions "${_flag}")
    endif()
  endforeach()

  add_definitions(${Geant4_DEFINITIONS} ${_g4_flag_definitions})
  message(STATUS "Geant4: ${Geant4_VERSION}, definitions ${Geant4_DEFINITIONS} ${_g4_flag_definitions}")

  # scram's geant4 toolfile defines G4VERSION_NUMBER; CMake's Geant4Config
  # does not, and the CMSSW sources that test it do not include G4Version.hh
  # themselves. Undefined, `#if G4VERSION_NUMBER >= 1130` is `0 >= 1130` -
  # false, silently - so the 20_1-era guards all take their pre-11.3 branch:
  #
  #   RunManagerMT.cc / GeometryProducer.cc  RequestParallelOptimisation(false)
  #   FieldStepper.h / CMSTDormandPrince45.h  which Dormand-Prince stepper
  #
  # The first of those is not cosmetic. Without it Geant4 keeps parallel
  # geometry voxelisation on, and CMSSW's threading model - master finishes
  # initialisation and parks, then workers initialise - leaves the worker
  # sleeping in G4VoxelisationHelper::WaitForVoxelisationFinish for help that
  # is never coming. The job hangs after building the geometry, with no error.
  #
  # Read out of the installed header rather than computed from Geant4_VERSION,
  # so the number is whatever the toolkit itself says it is.
  find_file(_g4_version_header G4Version.hh PATHS ${Geant4_INCLUDE_DIRS}
            NO_DEFAULT_PATH REQUIRED)
  file(STRINGS "${_g4_version_header}" _g4_version_line
       REGEX "^[ \t]*#[ \t]*define[ \t]+G4VERSION_NUMBER[ \t]+[0-9]+")
  if(NOT _g4_version_line MATCHES "G4VERSION_NUMBER[ \t]+([0-9]+)")
    message(FATAL_ERROR "could not read G4VERSION_NUMBER from ${_g4_version_header}")
  endif()
  add_definitions(-DG4VERSION_NUMBER=${CMAKE_MATCH_1})
  message(STATUS "Geant4 version number: ${CMAKE_MATCH_1}")
endif()
if(CMSSW_WITH_HDF5)
  find_package(HDF5 REQUIRED COMPONENTS CXX)
  set(hdf5_LIBRARIES ${HDF5_LIBRARIES} ${HDF5_CXX_LIBRARIES})
  set(hdf5_INCLUDE_DIRECTORIES ${HDF5_INCLUDE_DIRS})
endif()
if(CMSSW_WITH_G4HEPEM)
  # SimG4Core/PhysicsLists asks for this as "g4hepemcore". Upstream splits the
  # implementation across four libraries and CMSSW's tracking manager pulls
  # symbols from all of them, so link the set rather than the front-end alone.
  foreach(_l g4HepEm g4HepEmData g4HepEmInit g4HepEmRun)
    find_library(_g4hepem_${_l} NAMES ${_l} REQUIRED)
    list(APPEND g4hepemcore_LIBRARIES ${_g4hepem_${_l}})
  endforeach()
  # PATH_SUFFIXES because the headers sit in include/G4HepEm/ while CMSSW
  # includes them unprefixed, so the subdirectory itself is the include path.
  find_path(g4hepemcore_INCLUDE_DIRECTORIES NAMES G4HepEmTrackingManager.hh
            PATH_SUFFIXES G4HepEm REQUIRED)
endif()
if(CMSSW_WITH_DD4HEP)
  # the 20_1-era geometry is built on DD4hep (DetectorDescription/DDCMS and
  # every Geometry/*Builder package)
  foreach(_l DDCore DDParsers DDRec)
    find_library(_dd4hep_${_l} NAMES ${_l} REQUIRED)
    list(APPEND dd4hep_LIBRARIES ${_dd4hep_${_l}})
  endforeach()
  find_path(dd4hep_INCLUDE_DIRECTORIES NAMES DD4hep/Detector.h REQUIRED)
  # SimG4Core/Geometry asks for dd4hep-geant4 by that name. Only the link
  # needs it: DDG4 installs its headers under the same prefix as DDCore, and
  # dd4hep_INCLUDE_DIRECTORIES is on the global include path already.
  find_library(dd4hep-geant4_LIBRARIES NAMES DDG4 REQUIRED)
endif()
if(CMSSW_WITH_CURL)
  find_library(curl_LIBRARIES NAMES curl REQUIRED)
  find_path(curl_INCLUDE_DIRECTORIES NAMES curl/curl.h REQUIRED)
endif()
if(CMSSW_WITH_PYTHIA8)
  find_library(pythia8_LIBRARIES NAMES pythia8 REQUIRED)
  find_path(pythia8_INCLUDE_DIRECTORIES NAMES Pythia8/Pythia.h REQUIRED)
endif()
if(CMSSW_WITH_LHAPDF)
  find_library(lhapdf_LIBRARIES NAMES LHAPDF REQUIRED)
  find_path(lhapdf_INCLUDE_DIRECTORIES NAMES LHAPDF/LHAPDF.h REQUIRED)
endif()
if(CMSSW_WITH_HIGHFIVE)
  # header-only; the HDF5 it wraps is the hdf5 tool
  find_path(highfive_INCLUDE_DIRECTORIES NAMES highfive/H5File.hpp REQUIRED)
  set(highfive_LIBRARIES ${hdf5_LIBRARIES})
endif()
if(CMSSW_WITH_SIGCPP)
  # libsigc++ 2: headers under include/sigc++-2.0, and the generated
  # sigc++config.h next to the library
  find_library(sigcpp_LIBRARIES NAMES sigc-2.0 REQUIRED)
  find_path(sigcpp_INCLUDE_DIRECTORIES NAMES sigc++/sigc++.h PATH_SUFFIXES sigc++-2.0 REQUIRED)
  get_filename_component(_sigcpp_libdir ${sigcpp_LIBRARIES} DIRECTORY)
  list(APPEND sigcpp_INCLUDE_DIRECTORIES ${_sigcpp_libdir}/sigc++-2.0/include)
endif()
if(CMSSW_WITH_CORAL)
  # the CORAL libraries carry the lcg_ prefix (CoralKernel dlopens the
  # backend/service plugins under exactly that name)
  foreach(_c CoralBase CoralKernel CoralCommon RelationalAccess)
    find_library(${_c}_LIBRARIES NAMES lcg_${_c} REQUIRED)
    find_path(${_c}_INCLUDE_DIRECTORIES NAMES CoralBase/Exception.h REQUIRED)
  endforeach()
endif()

# ROOT: the scram tool names are fine-grained, but linking the common set of
# ROOT libraries everywhere is fine for our purposes.
set(_root_common_libs
  ROOT::Core ROOT::RIO ROOT::Net ROOT::Tree ROOT::TreePlayer ROOT::Thread
  ROOT::MathCore ROOT::MathMore ROOT::Hist ROOT::Matrix ROOT::Physics
  ROOT::GenVector ROOT::Smatrix ROOT::ROOTVecOps)
foreach(_t root rootcore rootcling rootrflx rootmath rootmathcore
        roothistmatrix rootsmatrix rootrio rootphysics)
  set(${_t}_LIBRARIES ${_root_common_libs})
  set(${_t}_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
endforeach()
# TMVA on top of the common set (CommonTools/MVAUtils)
# RNTuple (the NanoAOD RNTuple output module), where ROOT has it
if(TARGET ROOT::ROOTNTuple)
  set(rootntuple_LIBRARIES ${_root_common_libs} ROOT::ROOTNTuple)
  set(rootntuple_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
endif()
# graphics pads (TopQuarkAnalysis/TopTools draws into a TCanvas)
set(rootgpad_LIBRARIES ${_root_common_libs} ROOT::Gpad)
set(rootgpad_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
# the graphics libraries as cmsdist's rootgraphics (Validation/RecoTau's
# DQMHistPlotter writes TPostScript files)
set(rootgraphics_LIBRARIES ${_root_common_libs} ROOT::Gpad ROOT::Graf ROOT::Graf3d ROOT::Postscript)
set(rootgraphics_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
# the histogram painter (CommonTools/TrackerMap) and the geometry library
# (DetectorDescription/DDCMS)
set(roothistpainter_LIBRARIES ${_root_common_libs} ROOT::HistPainter)
set(roothistpainter_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
set(rootgeom_LIBRARIES ${_root_common_libs} ROOT::Geom)
set(rootgeom_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
# TDatabasePDG (Validation/MuonGEMHits)
set(rooteg_LIBRARIES ${_root_common_libs} ROOT::EG)
set(rooteg_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
set(roottmva_LIBRARIES ${_root_common_libs} ROOT::TMVA)
set(roottmva_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
# Minuit/Minuit2 (Hcal method-2 pulse fits) and the TMultiLayerPerceptron
# (Ecal dead-channel recovery) on top of the common set
set(rootminuit_LIBRARIES ${_root_common_libs} ROOT::Minuit)
set(rootminuit_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
set(rootmlp_LIBRARIES ${_root_common_libs} ROOT::MLP)
set(rootmlp_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
# RooFit (PhysicsTools/Utilities)
set(roofit_LIBRARIES ${_root_common_libs} ROOT::RooFitCore ROOT::RooFit)
set(roofit_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
set(roofitcore_LIBRARIES ${_root_common_libs} ROOT::RooFitCore)
set(roofitcore_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
# Minuit2: from ROOT if it was built with it, else from the standalone
# Minuit2 package (pkgs/minuit2.nix, used with the 22.05-era ROOT)
if(TARGET ROOT::Minuit2)
  set(rootminuit2_LIBRARIES ${_root_common_libs} ROOT::Minuit2)
  set(rootminuit2_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS})
else()
  find_library(_minuit2_lib NAMES Minuit2 REQUIRED)
  find_library(_minuit2math_lib NAMES Minuit2Math REQUIRED)
  # the standalone package nests its header root at include/Minuit2
  find_path(_minuit2_inc NAMES Minuit2/Minuit2Minimizer.h PATH_SUFFIXES Minuit2 REQUIRED)
  set(rootminuit2_LIBRARIES ${_root_common_libs} ${_minuit2_lib} ${_minuit2math_lib})
  set(rootminuit2_INCLUDE_DIRECTORIES ${ROOT_INCLUDE_DIRS} ${_minuit2_inc})
endif()

set(boost_LIBRARIES Boost::filesystem Boost::thread Boost::regex
    Boost::serialization Boost::iostreams Boost::date_time)
set(boost_INCLUDE_DIRECTORIES ${Boost_INCLUDE_DIRS})
set(boost_header_INCLUDE_DIRECTORIES ${Boost_INCLUDE_DIRS})
set(boost_program_options_LIBRARIES Boost::program_options)
set(boost_program_options_INCLUDE_DIRECTORIES ${Boost_INCLUDE_DIRS})
set(boost_regex_LIBRARIES Boost::regex)
set(boost_serialization_LIBRARIES Boost::serialization)
set(boost_iostreams_LIBRARIES Boost::iostreams)

if(TBB_FOUND)
  set(tbb_LIBRARIES TBB::tbb)
else()
  set(tbb_LIBRARIES ${TBB_PLAIN_LIBRARY})
endif()
find_path(tbb_INCLUDE_DIRECTORIES NAMES oneapi/tbb.h tbb/tbb.h REQUIRED)

set(clhep_LIBRARIES CLHEP::CLHEP)
set(clhep_INCLUDE_DIRECTORIES ${CLHEP_INCLUDE_DIRS})
set(clhepheader_INCLUDE_DIRECTORIES ${CLHEP_INCLUDE_DIRS})

set(eigen_LIBRARIES Eigen3::Eigen)
set(eigen_INCLUDE_DIRECTORIES ${EIGEN3_INCLUDE_DIRS})

set(python3_LIBRARIES Python3::Python)
set(python3_INCLUDE_DIRECTORIES ${Python3_INCLUDE_DIRS})
set(py3-pybind11_LIBRARIES pybind11::headers Python3::Python)
set(py3-pybind11_INCLUDE_DIRECTORIES ${pybind11_INCLUDE_DIRS} ${Python3_INCLUDE_DIRS})
# The 10_6-era tool names ("python" was python2 back then; we build the
# python3 variant of the release, which existed as cmsRunPython3).
set(python_LIBRARIES Python3::Python)
set(python_INCLUDE_DIRECTORIES ${Python3_INCLUDE_DIRS})
set(py2-pybind11_LIBRARIES pybind11::headers Python3::Python)
set(py2-pybind11_INCLUDE_DIRECTORIES ${pybind11_INCLUDE_DIRS} ${Python3_INCLUDE_DIRS})

# tinyxml2 < 7 (10_6 era) exports the target without namespace
if(TARGET tinyxml2::tinyxml2)
  set(tinyxml2_LIBRARIES tinyxml2::tinyxml2)
else()
  set(tinyxml2_LIBRARIES tinyxml2)
endif()
find_path(tinyxml2_INCLUDE_DIRECTORIES NAMES tinyxml2.h REQUIRED)

set(fmt_LIBRARIES fmt::fmt)
find_path(fmt_INCLUDE_DIRECTORIES NAMES fmt/format.h REQUIRED)

# libatomic and librt are glibc/gcc things; on macOS their contents are in
# libSystem and the compiler runtime
if(APPLE)
  set(gcc-atomic_LIBRARIES "")
  set(rt_LIBRARIES "")
else()
  set(gcc-atomic_LIBRARIES atomic)
  set(rt_LIBRARIES rt)
endif()
set(resolv_LIBRARIES resolv)

# ---------------------------------------------------------------------------
# Global compile flags
# ---------------------------------------------------------------------------

# what scram's microarch flags would name the default target
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64)$")
  set(_cms_micro_arch "x86-64")
else()
  set(_cms_micro_arch "armv8.0-a")
endif()

add_compile_definitions(
  GNU_GCC
  _GNU_SOURCE
  TBB_SUPPRESS_DEPRECATED_MESSAGES
  TBB_PREVIEW_RESUMABLE_TASKS=1
  TBB_PREVIEW_TASK_GROUP_EXTENSIONS=1
  PROJECT_NAME=CMSSW
  PROJECT_VERSION=${CMSSW_VERSION}
  CMS_MICRO_ARCH="${_cms_micro_arch}"
)

# -DNDEBUG matches scram: without it the boost assertions are live, and e.g.
# the nanoAOD TableOutputBranches aborts on taking .front() of a legitimately
# empty table column
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -DNDEBUG -Wno-deprecated-declarations -Wno-attributes -Wno-unused-result -Wno-psabi")
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64)$")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -msse3")
endif()
# clang rejects a constexpr function that can never be a constant expression
# (10_6's approx_erf calls the non-constexpr std::abs); gcc, which the
# release is written against, accepts it. The diagnostic is an error only by
# default.
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-invalid-constexpr")
endif()

# A dynamic_cast to a final class is, since clang 17, a single comparison of
# the object's vtable pointer against the class's vtable - correct only if a
# class has exactly one vtable in the process. On macOS it does not: a class
# with no out-of-line virtual function (no key function) gets a hidden copy
# of its vtable in every library that uses it, so the cast fails whenever the
# object was made in a different library than the cast is written in.
# CMSSW's tracker rec hits are such classes, and code like
#     auto const* hit = dynamic_cast<const SiPixelRecHit*>(rhit);
# then gets nullptr for a hit typeid() itself calls a SiPixelRecHit (the
# track associator crashed on exactly this). ELF platforms merge the copies,
# so only macOS needs the general comparison.
if(APPLE)
  include(CheckCXXCompilerFlag)
  check_cxx_compiler_flag(-fno-assume-unique-vtables CMSSW_HAVE_NO_ASSUME_UNIQUE_VTABLES)
  if(CMSSW_HAVE_NO_ASSUME_UNIQUE_VTABLES)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-assume-unique-vtables")
  endif()
endif()

# libc++ (the C++ library on macOS) drops the library features C++17 and
# C++20 deprecated as soon as the standard does; libstdc++, which CMSSW is
# written against, keeps most of them. 10_6 in particular still says
# std::auto_ptr in three dozen places. libc++ keeps each of them on request.
# genreflex parses the same headers, so it gets the same list (below).
set(CMSSW_STDLIB_DEFINITIONS "")
if(APPLE)
  set(CMSSW_STDLIB_DEFINITIONS
    _LIBCPP_ENABLE_CXX17_REMOVED_AUTO_PTR
    _LIBCPP_ENABLE_CXX17_REMOVED_BINDERS
    _LIBCPP_ENABLE_CXX17_REMOVED_RANDOM_SHUFFLE
    _LIBCPP_ENABLE_CXX17_REMOVED_UNARY_BINARY_FUNCTION
    _LIBCPP_ENABLE_CXX17_REMOVED_UNEXPECTED_FUNCTIONS
    _LIBCPP_ENABLE_CXX20_REMOVED_BINDER_TYPEDEFS
    _LIBCPP_ENABLE_CXX20_REMOVED_NEGATORS
    _LIBCPP_ENABLE_CXX20_REMOVED_RAW_STORAGE_ITERATOR
    _LIBCPP_ENABLE_CXX20_REMOVED_TYPE_TRAITS)
  add_compile_definitions(${CMSSW_STDLIB_DEFINITIONS})
endif()
list(TRANSFORM CMSSW_STDLIB_DEFINITIONS PREPEND "-D" OUTPUT_VARIABLE GENREFLEX_STDLIB_DEFINITIONS)

if(CMSSW_WITH_ALPAKA)
  add_compile_definitions(
    ALPAKA_DEFAULT_HOST_MEMORY_ALIGNMENT=128
    ALPAKA_DISABLE_VENDOR_RNG
    ALPAKA_HAS_STD_ATOMIC_REF
  )
  # alpaka headers are needed nearly everywhere the SoA data formats appear
  include_directories(${alpaka_INCLUDE_DIRECTORIES})
endif()

# ---------------------------------------------------------------------------
# Macros for LCG/reflex dictionary generation
# ---------------------------------------------------------------------------

# Extra include directories that genreflex (which does not see the compiler
# wrapper's implicit search paths) always needs. All optional external tool
# include directories are listed here as well: the per-target collection
# below only sees the include directories of *already-configured* targets,
# so tool includes of packages configured later in the tree walk would be
# missed (empty variables expand to nothing).
set(GENREFLEX_INCLUDE_LIST "")
foreach(dir ${Boost_INCLUDE_DIRS} ${CLHEP_INCLUDE_DIRS} ${eigen_INCLUDE_DIRECTORIES}
        ${alpaka_INCLUDE_DIRECTORIES} ${tbb_INCLUDE_DIRECTORIES} ${fmt_INCLUDE_DIRECTORIES}
        ${libuuid_INCLUDE_DIRECTORIES} ${md5_INCLUDE_DIRECTORIES}
        ${hepmc_INCLUDE_DIRECTORIES} ${vdt_headers_INCLUDE_DIRECTORIES}
        ${gsl_INCLUDE_DIRECTORIES} ${fastjet_INCLUDE_DIRECTORIES}
        ${fastjet-contrib_INCLUDE_DIRECTORIES} ${heppdt_INCLUDE_DIRECTORIES}
        ${lwtnn_INCLUDE_DIRECTORIES} ${CoralBase_INCLUDE_DIRECTORIES}
        ${cpu_features_INCLUDE_DIRECTORIES} ${openssl_INCLUDE_DIRECTORIES}
        ${dd4hep_INCLUDE_DIRECTORIES} ${hls_INCLUDE_DIRECTORIES}
        ${geant4core_INCLUDE_DIRECTORIES} ${hdf5_INCLUDE_DIRECTORIES}
        ${g4hepemcore_INCLUDE_DIRECTORIES}
        ${hepmc3_INCLUDE_DIRECTORIES} ${onnxruntime_INCLUDE_DIRECTORIES}
        ${xgboost_INCLUDE_DIRECTORIES} ${pythia8_INCLUDE_DIRECTORIES}
        ${lhapdf_INCLUDE_DIRECTORIES} ${sigcpp_INCLUDE_DIRECTORIES}
        ${hls4mlEmulatorExtras_INCLUDE_DIRECTORIES} ${classlib_INCLUDE_DIRECTORIES}
        ${protobuf_INCLUDE_DIRECTORIES} ${utm_INCLUDE_DIRECTORIES})
  list(APPEND GENREFLEX_INCLUDE_LIST "-I${dir}")
endforeach()
list(REMOVE_DUPLICATES GENREFLEX_INCLUDE_LIST)

macro(GET_INCLUDE_COMPILER_LIST MY_TARGET)

    get_target_property(MY_INTERFACE_LINK_LIBRARIES ${MY_TARGET} INTERFACE_LINK_LIBRARIES)
    list(APPEND MY_INTERFACE_LINK_LIBRARIES ${MY_TARGET})

    set(INCLUDE_COMPILER_LIST "-I${PROJECT_SOURCE_DIR}/cmssw" ${GENREFLEX_INCLUDE_LIST})

    # Construct the compiler string for the include directories.
    foreach(lib ${MY_INTERFACE_LINK_LIBRARIES})
        if (TARGET ${lib})
            get_target_property(MY_INCLUDE_DIRECTORIES ${lib} INCLUDE_DIRECTORIES)
            if(NOT MY_INCLUDE_DIRECTORIES)
                set(MY_INCLUDE_DIRECTORIES "")
            endif()
            foreach(dir ${MY_INCLUDE_DIRECTORIES})
                if(NOT ${dir} MATCHES "${PROJECT_SOURCE_DIR}")
                    list(APPEND INCLUDE_COMPILER_LIST "-I${dir}")
                endif()
            endforeach()
        endif()
    endforeach()
    list(REMOVE_DUPLICATES INCLUDE_COMPILER_LIST)

endmacro()


macro(MAKE_GENREFLEX_COMMAND MY_TARGET MY_SOURCE MY_HEADER MY_XML)

    add_custom_command(OUTPUT ${MY_SOURCE}.cxx
        COMMAND genreflex ${CMAKE_CURRENT_SOURCE_DIR}/src/${MY_HEADER}.h
        -s ${CMAKE_CURRENT_SOURCE_DIR}/src/${MY_XML}.xml
        -o ${MY_SOURCE}.cxx
        --rootmap=${CMAKE_BINARY_DIR}/lib/lib${MY_TARGET}_${MY_SOURCE}.rootmap
        --rootmap-lib=lib${MY_TARGET}.so
        --library lib${MY_TARGET}.so --multiDict
        -DCMS_DICT_IMPL -D_REENTRANT -DGNUSOURCE -D__STRICT_ANSI__ -DCMSSW_REFLEX_DICT
        -DALPAKA_DEFAULT_HOST_MEMORY_ALIGNMENT=128 -DALPAKA_DISABLE_VENDOR_RNG -DALPAKA_HAS_STD_ATOMIC_REF
        ${GENREFLEX_STDLIB_DEFINITIONS}
        ${INCLUDE_COMPILER_LIST}
        DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/${MY_HEADER}.h ${CMAKE_CURRENT_SOURCE_DIR}/src/${MY_XML}.xml
    )

endmacro()

# go into the cmssw source directory
add_subdirectory(cmssw)
