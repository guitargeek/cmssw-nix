"""Generate CMakeLists.txt files for (a subset of) CMSSW from its scram BuildFile.xml files.

Adapted from the Arch Linux packaging attempt (PKGBUILDs/cmssw/cmssw_cmake.py) for
the nix build:

  * all <iftool> blocks are dropped (no CUDA/ROCm builds),
  * test/ directories are skipped entirely,
  * plugins/ directories can be disabled per subsystem or package ("no_plugins"),
  * bin/ directories are only built for packages listed under the top-level
    "bins" config key,
  * multi-header LCG dictionaries declared via LCG_DICT_HEADER are handled
    correctly instead of being collapsed to classes.h.
"""

import glob
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict


class CMakeLists(object):
    def __init__(self):
        self._txt = []
        self._target_started = False

    def add_subdirs(self, directories):
        def add_with_guard(directory, guard):
            self._txt += [f"if({guard})", f"    add_subdirectory({directory})", "endif()"]

        for d in directories:
            if d == "bin":
                add_with_guard(d, "CMSSW_BUILD_BIN")
            elif d == "plugins":
                add_with_guard(d, "CMSSW_BUILD_PLUGINS")
            elif d == "test":
                add_with_guard(d, "CMSSW_BUILD_TEST")
            else:
                self._txt += [f"add_subdirectory({d})"]

        return self

    def __iadd__(self, rhs):
        self._txt += rhs
        return self

    def add_interface_library(self):
        if self._target_started:
            raise RuntimeError("CMakeLists object already has an added target, fill it's name first!")

        self._txt += [
            "add_library(<target>)",
        ]
        self._target_started = True

    def add_library(self, source_files):
        if self._target_started:
            raise RuntimeError("CMakeLists object already has an added target, fill it's name first!")

        self._txt += [
            "add_library(<target> SHARED " + " ".join(source_files) + ")",
            "set_target_properties(<target> PROPERTIES LIBRARY_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/lib)",
            "install(TARGETS <target> LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR} OPTIONAL)",
        ]
        self._target_started = True

    def add_executable(self, source_files):
        if self._target_started:
            raise RuntimeError("CMakeLists object already has an added target, fill it's name first!")

        self._txt += [
            "add_executable(<target> " + " ".join(source_files) + ")",
            "set_target_properties(<target> PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin)",
            "install(TARGETS <target> DESTINATION ${CMAKE_INSTALL_BINDIR} OPTIONAL)",
        ]
        self._target_started = True

    def fill_target(self, target):
        self._txt = list(map(lambda l: l.replace("<target>", target), self._txt))
        self._target_started = False

    def write(self, path):
        self._path = os.path.join(os.getcwd(), path)

        text = self._txt
        if type(text) == list:
            text = "\n".join(text)

        if "<target>" in text:
            raise RuntimeError("There are still <target> placeholders in the CMake file " + path)

        filename = os.path.join(self._path, "CMakeLists.txt")
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write(text)
        with open(filename, "r") as f:
            old_text = f.read()
        if old_text != text:
            with open(filename, "w") as f:
                f.write(text)


def name(elem):
    if not elem.get("name") is None:
        return elem.get("name")
    return elem.get("Name")


def load_config(config_file):
    import yaml

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    for subsystem, subsystem_config in config["subsystems"].items():
        if subsystem_config is not None:
            if "whitelist" in subsystem_config and "blacklist" in subsystem_config:
                raise ValueError("Package config can't contain blacklist and whitelist at the same time.")
        else:
            config["subsystems"][subsystem] = {}

    config.setdefault("bins", [])

    return config


def cmake_dependency_lines(dependency, config):
    # deal with local cmssw deps
    if "/" in dependency:
        return ["", "target_link_libraries(<target> " + dependency.replace("/", "") + ")"]

    cmake = ["target_include_directories(<target> PUBLIC ${" + dependency + "_INCLUDE_DIRECTORIES})"]
    cmake += ["target_link_libraries(<target> ${" + dependency + "_LIBRARIES})"]

    return cmake


def complete_build_file(build_file, default_lib_name=None, in_plugin_dir=False):
    with open(build_file) as f:
        xml = f.read()

    # Remove all "iftool" blocks: they guard optional externals (cuda, rocm,
    # ...) that we don't build with.
    filtered_lines = []
    iftool_depth = 0
    for line in xml.split("\n"):
        if "<iftool" in line and "/>" not in line:
            iftool_depth += 1
        elif "</iftool" in line:
            iftool_depth = max(0, iftool_depth - 1)
        elif "<iftool" in line:
            pass  # self-closing, ignore
        elif iftool_depth == 0:
            filtered_lines.append(line)

    xml = "\n".join(filtered_lines)

    # skip empty build files
    if xml.strip() == "":
        return None

    auto = not "<bin" in xml and not "<library" in xml

    if auto and in_plugin_dir:
        xml = '<flags EDM_PLUGIN="1"/>\n' + xml
        default_lib_name = default_lib_name + "Plugins"
    if auto:
        patterns = ["*.cc", "*.cxx", "*.cpp"]
        # ADD_SUBDIR="1" in a plugins/ directory: scram also compiles the
        # sources one directory down (EventFilter/L1TRawToDigi/plugins/
        # implementations_stage2/, ...); alpaka/ holds the per-backend
        # sources, which are not built here. (For a package library, the
        # subdirectories of src/ are globbed anyway.)
        if in_plugin_dir and re.search(r'ADD_SUBDIR\s*=\s*"1"', xml):
            here = os.path.dirname(build_file)
            for d in sorted(os.listdir(here)):
                if d != "alpaka" and os.path.isdir(os.path.join(here, d)):
                    patterns += [f"{d}/{p}" for p in ("*.cc", "*.cxx", "*.cpp")]
        xml = ('<library   file="' + " ".join(patterns) + '" name="' + default_lib_name + '">\n'
               + xml + "\n</library>")

    if not auto and in_plugin_dir:
        # scram semantics: a <library> in a plugins/ directory is an EDM
        # plugin by default; only an explicit EDM_PLUGIN="0" opts out. Some
        # BuildFiles rely on the default (e.g. PhysicsTools/HepMCCandAlgos),
        # and a plugin library that misses the flag here is built with the
        # lib prefix and silently never registered.
        def _mark_plugin(m):
            block = m.group(0)
            if "EDM_PLUGIN" in block:
                return block
            i = block.index(">") + 1
            return block[:i] + '\n  <flags   EDM_PLUGIN="1"/>' + block[i:]
        xml = re.sub(r"<library\b(?:(?!</library>).)*</library>", _mark_plugin, xml, flags=re.DOTALL)

    return xml


def parse_elements(root_node, config):
    cmake = []
    flags = {"LCG_DICT_HEADER": [], "LCG_DICT_XML": []}

    for elem in root_node:
        if elem.tag == "flags":
            if elem.get("cppflags"):
                cmake += ['set_target_properties(<target> PROPERTIES COMPILE_FLAGS "' + elem.get("cppflags") + '")']
            if elem.get("EDM_PLUGIN"):
                cmake += ['set_target_properties(<target> PROPERTIES PREFIX "plugin")']
            if elem.get("LCG_DICT_HEADER"):
                flags["LCG_DICT_HEADER"] += elem.get("LCG_DICT_HEADER").split()
            if elem.get("LCG_DICT_XML"):
                flags["LCG_DICT_XML"] += elem.get("LCG_DICT_XML").split()
        if elem.tag == "use" or elem.tag == "lib" and name(elem) != "1":
            if elem.get("source_only") == "1":
                continue
            cmake += cmake_dependency_lines(name(elem), config)
        if elem.tag == "lib":
            cmake += ["target_link_libraries(<target> " + name(elem) + ")"]

    return cmake, flags


def interpret_files(root, file_expressions):
    # sometimes there is space separation instead of comma
    file_expressions = file_expressions.replace(" ", ",")

    files = []
    for f in file_expressions.split(","):
        if f == "":
            continue
        if "*" in f:
            globbed = glob.glob(os.path.join(root, f))
            files += [g[len(root) + 1 :] for g in globbed]
        else:
            files.append(f)
    return files


def make_lcg_source_names(n_dicts):
    sources = []
    if n_dicts == 1:
        sources.append("<target>_xr.cxx")
    if n_dicts > 1:
        for i in range(1, n_dicts + 1):
            sources.append(f"<target>_x{i}r.cxx")
    return sources


def lcg_dict_sources(headers, xmls):
    sources = make_lcg_source_names(len(headers))

    cmake = []
    if len(sources) > 0:
        cmake += ['list(APPEND SOURCE_FILES "' + '" "'.join(sources) + '")']

    return cmake


def lcg_dict_generation(headers, xmls):
    cmake = ["", "get_include_compiler_list(<target>)", ""]

    for header, xml, source in zip(headers, xmls, make_lcg_source_names(len(headers))):
        cmake += ["make_genreflex_command(<target> " + source[:-4] + " " + header[:-2] + " " + xml[:-4] + ")"]

    return cmake


def get_global_dependencies(root_node):
    global_dependencies = []

    for elem in root_node:
        if elem.tag == "use" and elem.get("source_only") != "1":
            global_dependencies.append(name(elem))
        if elem.tag == "environment":
            for sub_elem in elem:
                if sub_elem.tag == "use":
                    global_dependencies.append(name(sub_elem))

    return global_dependencies


def get_global_libs(root_node):
    """Top-level <lib name="..."/>: a library every target of the BuildFile
    links (CalibMuon/DTCalibration/plugins links ROOT's Spectrum this way)."""
    return [name(elem) for elem in root_node if elem.tag == "lib" and name(elem) != "1"]


# (target name, "Subsystem/Package") of every shared library built: used to
# generate the fillDescriptions-based *_cfi.py files (scram's "cfipython")
# with edmWriteConfigs at install time and place them in the right package.
library_manifest = []


def write_cmake_for_target(cmake, root, elem, n_src_files, global_dependencies, global_libs, config):
    target = name(elem)

    files = interpret_files(root, elem.get("file"))

    if target is None:
        target = files[0].split(".")[0]

    cmake_from_build_file, flags = parse_elements(elem, config)

    # If no dictionary headers were declared explicitly, but the conventional
    # classes.h / classes_def.xml pair exists, generate a dictionary for it.
    if len(flags["LCG_DICT_HEADER"]) == 0 and os.path.exists(os.path.join(root, "src/classes.h")):
        flags["LCG_DICT_HEADER"] = ["classes.h"]
        flags["LCG_DICT_XML"] = ["classes_def.xml"]

    if len(flags["LCG_DICT_HEADER"]) != len(flags["LCG_DICT_XML"]):
        raise RuntimeError(f"LCG_DICT_HEADER and LCG_DICT_XML lengths differ in {root}")

    cmake += lcg_dict_sources(flags["LCG_DICT_HEADER"], flags["LCG_DICT_XML"])

    is_interface = False

    if elem.tag == "library":
        n_files = n_src_files + len(files) + len(flags["LCG_DICT_HEADER"])
        if n_files == 0:
            is_interface = True
            cmake.add_interface_library()
        else:
            cmake.add_library(["${SOURCE_FILES}"] + files)
            parts = os.path.normpath(root).split(os.sep)
            if len(parts) >= 2:
                library_manifest.append((target, parts[0] + "/" + parts[1]))
    if elem.tag == "bin":
        cmake.add_executable(files)

    for dependency in global_dependencies:
        cmake += cmake_dependency_lines(dependency, config)
    # some BuildFiles name their own library here (Geometry/DTGeometryBuilder)
    for lib in (l for l in global_libs if l != target):
        cmake += cmake_dependency_lines(lib, config)
        cmake += ["target_link_libraries(<target> " + lib + ")"]

    cmake += cmake_from_build_file

    if is_interface:
        # for INTERFACE targets the scope keyword is INTERFACE (injected via
        # fill_target below), so drop the PUBLIC keyword
        cmake._txt = [l.replace("(<target> PUBLIC", "(<target>") for l in cmake._txt]
        # and there is no file to name: a package with nothing but python/
        # can still declare EDM_PLUGIN (DQMOffline/HLTScouting)
        cmake._txt = [l for l in cmake._txt if not l.startswith("set_target_properties(<target>")]

    cmake.fill_target(target + " INTERFACE" * (0 + is_interface))

    cmake += lcg_dict_generation(flags["LCG_DICT_HEADER"], flags["LCG_DICT_XML"])

    cmake.fill_target(target)


def build_xml_to_cmake(root, root_node, config):
    cmake = CMakeLists()

    # scram's default source glob also picks up .cxx and .cpp (e.g. the
    # GBRForest*.cxx files in CondFormats/EgammaObjects)
    n_globbed_files = sum(
        len(glob.glob(os.path.join(root, "src/*" + ext))) for ext in [".cc", ".cxx", ".cpp"]
    )

    cmake += ['file(GLOB_RECURSE SOURCE_FILES "src/*.cc" "src/*.cxx" "src/*.cpp")']
    # src/alpaka/ sources belong to per-accelerator-backend libraries that
    # scram would build separately with backend-specific defines; they are not
    # part of the base (host) library.
    cmake += ['list(FILTER SOURCE_FILES EXCLUDE REGEX "/alpaka/")']

    global_dependencies = get_global_dependencies(root_node)
    global_libs = get_global_libs(root_node)

    # scram tolerates a target declared twice (CondTools/RunInfo/plugins has
    # two identical LHCInfoPerLSWriter stanzas); CMake does not
    seen = set()
    for elem in root_node:
        if elem.tag in ["library", "bin"]:
            key = (elem.tag, name(elem))
            if name(elem) is not None:
                if key in seen:
                    continue
                seen.add(key)
            write_cmake_for_target(cmake, root, elem, n_globbed_files, global_dependencies, global_libs, config)

    return cmake


def cmssw_to_cmake(cmssw_src_dir, config_path):
    config = load_config(config_path)

    def compile_package(subsystem, pkg):
        if not subsystem in config["subsystems"]:
            return False
        cfg = config["subsystems"][subsystem]

        return not (
            "whitelist" in cfg and not pkg in cfg["whitelist"] or "blacklist" in cfg and pkg in cfg["blacklist"]
        )

    def build_plugins(subsystem, pkg):
        cfg = config["subsystems"].get(subsystem) or {}
        no_plugins = cfg.get("no_plugins", False)
        if no_plugins is True:
            return False
        if isinstance(no_plugins, list) and pkg in no_plugins:
            return False
        return True

    os.chdir(cmssw_src_dir)

    cmake_in_subsystem = defaultdict(dict)

    for root, directories, files in os.walk("."):
        if root.count("/") < 2:
            continue

        subsystem, package = root.split("/")[1:3]

        if not compile_package(subsystem, package):
            continue

        basename = os.path.basename(root)

        def accept_as_build_file(filename):
            if filename != "BuildFile.xml" or root.count("/") > 3:
                return False
            # scripts/BuildFile.xml only says which scripts scram installs
            if basename in ["python", "test", "scripts"]:
                return False
            if basename == "plugins" and not build_plugins(subsystem, package):
                return False
            if basename == "bin" and f"{subsystem}/{package}" not in config["bins"]:
                return False
            return True

        for file in filter(accept_as_build_file, files):
            xml = complete_build_file(
                os.path.join(root, file),
                default_lib_name=subsystem + package,
                in_plugin_dir=basename == "plugins",
            )
            if xml is None:
                continue
            # don't write cmake files immediately, we might want to change them later
            cmake_in_subsystem[subsystem]["/".join(root.split("/")[2:])] = build_xml_to_cmake(
                root, ET.fromstring("<root>" + xml + "</root>"), config
            )

    # Finally, include all subdirs into which we have written CMakeList files
    cmake = CMakeLists()
    cmake += ["include_directories(.)", ""]
    for subsystem, cmakes in cmake_in_subsystem.items():
        cmake.add_subdirs([subsystem])

        packages = sorted(list(set(map(lambda p: p.split("/")[0], cmakes.keys()))))

        subdirs_to_include = {package: [] for package in packages}

        for dir_in_subsystem in cmakes.keys():
            package = dir_in_subsystem.split("/")[0]
            if "/" in dir_in_subsystem:
                subdirs_to_include[package].append("/".join(dir_in_subsystem.split("/")[1:]))

        subdirs_included = {package: len(subdirs_to_include[package]) == 0 for package in packages}

        for dir_in_subsystem, cmake_i in cmakes.items():
            package = dir_in_subsystem.split("/")[0]
            if not "/" in dir_in_subsystem:
                cmake_i.add_subdirs(subdirs_to_include[package])
                subdirs_included[package] = True
            cmake_i.write(os.path.join(subsystem, dir_in_subsystem))

        for package in subdirs_to_include:
            if not subdirs_included[package]:
                CMakeLists().add_subdirs(subdirs_to_include[package]).write(os.path.join(subsystem, package))

        CMakeLists().add_subdirs(packages).write(subsystem)

    cmake.write(".")

    os.chdir("..")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate CMakeLists for CMSSW.")
    parser.add_argument("config", type=str, help="path to yaml config file")
    parser.add_argument("--src", type=str, default="cmssw", help="path to the cmssw source directory")

    args = parser.parse_args()

    cmssw_to_cmake(args.src, os.path.abspath(args.config))

    with open("library_manifest.txt", "w") as f:
        for target, pkg in library_manifest:
            f.write(f"{target} {pkg}\n")
