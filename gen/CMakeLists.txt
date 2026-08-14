# 3.22 is what nixos-22.05 (used for the 10_6-era builds) ships
cmake_minimum_required(VERSION 3.22)
project(CMSSW LANGUAGES C CXX)

# C++ standard of the release era (20 for >= 13_X, 17 for the 10_6 era).
if(NOT DEFINED CMSSW_CXX_STANDARD)
  set(CMSSW_CXX_STANDARD 20)
endif()
set(CMAKE_CXX_STANDARD ${CMSSW_CXX_STANDARD})
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

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
find_path(md5_INCLUDE_DIRECTORIES NAMES md5.h REQUIRED)
find_library(libuuid_LIBRARIES NAMES uuid REQUIRED)
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
  # the same package (SimDataFormats/GeneratorProducts) also uses liblzma
  # through the scram tool name "xz"
  find_library(xz_LIBRARIES NAMES lzma REQUIRED)
  find_path(xz_INCLUDE_DIRECTORIES NAMES lzma.h REQUIRED)
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
endif()
if(CMSSW_WITH_LWTNN)
  find_library(lwtnn_LIBRARIES NAMES lwtnn REQUIRED)
  find_path(lwtnn_INCLUDE_DIRECTORIES NAMES lwtnn/LightweightNeuralNetwork.hh REQUIRED)
endif()
if(CMSSW_WITH_OPENBLAS)
  find_library(openblas_LIBRARIES NAMES openblas REQUIRED)
endif()
if(CMSSW_WITH_CURL)
  find_library(curl_LIBRARIES NAMES curl REQUIRED)
  find_path(curl_INCLUDE_DIRECTORIES NAMES curl/curl.h REQUIRED)
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

set(gcc-atomic_LIBRARIES atomic)
set(resolv_LIBRARIES resolv)
set(rt_LIBRARIES rt)

# ---------------------------------------------------------------------------
# Global compile flags
# ---------------------------------------------------------------------------

add_compile_definitions(
  GNU_GCC
  _GNU_SOURCE
  TBB_SUPPRESS_DEPRECATED_MESSAGES
  TBB_PREVIEW_RESUMABLE_TASKS=1
  TBB_PREVIEW_TASK_GROUP_EXTENSIONS=1
  PROJECT_NAME=CMSSW
  PROJECT_VERSION=${CMSSW_VERSION}
  CMS_MICRO_ARCH="x86-64"
)

set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -msse3 -Wno-deprecated-declarations -Wno-attributes -Wno-unused-result -Wno-psabi")

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
        ${cpu_features_INCLUDE_DIRECTORIES} ${openssl_INCLUDE_DIRECTORIES})
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
        ${INCLUDE_COMPILER_LIST}
        DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/src/${MY_HEADER}.h ${CMAKE_CURRENT_SOURCE_DIR}/src/${MY_XML}.xml
    )

endmacro()

# go into the cmssw source directory
add_subdirectory(cmssw)
