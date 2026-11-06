#!/usr/bin/env bash
# release-with-data.sh <build> <out> [<data tree> ...]
#
# Make the release area users get from a built release (pkgs/cmssw.nix) and
# the cms-data it reads (pkgs/cms-data.nix): <out> mirrors <build>, with each
# data tree's <Subsystem>/<Package>/data merged into
# src/<Subsystem>/<Package>/data, where scram puts them too, and a setup
# hook that names <out>. The data is on CMSSW_SEARCH_PATH that way and in
# the release area, which is where edm::FileInPath accepts it: it knows one
# data area besides the release (CMSSW_DATA_PATH), not a list of them.
#
# Everything is linked a directory at a time: FileInPath refuses a file that
# is a symbolic link (it may link directories on the way). Only where two
# trees meet in one directory are its files copied - the few a data
# repository and the package's own data/ (or two data repositories) share a
# directory with.
#
# Copying the data into the build instead would rebuild the release, hours,
# whenever a data repository changes; this takes seconds. Used by
# pkgs/cmssw-release.nix and by scripts/worktree.sh.
set -euo pipefail

build=$1 out=$2
shift 2

# merge <dst> <src>...: the directories srcs as one directory dst - a link
# where there is one source, a directory of merged entries where there are
# several. Of a name that is a file in some source, the last source's wins.
merge() {
  local dst=$1
  shift
  if [ $# -eq 1 ]; then
    ln -s "$1" "$dst"
    return
  fi
  mkdir -p "$dst"
  local name src dirs last
  while IFS= read -r name; do
    dirs=() last=
    for src in "$@"; do
      [ -e "$src/$name" ] || continue
      last=$src/$name
      [ -d "$last" ] && dirs+=("$last")
    done
    if [ -d "$last" ]; then
      merge "$dst/$name" "${dirs[@]}"
    else
      cp "$last" "$dst/$name"
      chmod u+w "$dst/$name"
    fi
  done < <(for src in "$@"; do ls -A "$src"; done | sort -u)
}

# Sub/Pkg -> the data directories that go into its data/
declare -A data
for tree in "$@"; do
  for d in "$tree"/data/*/*/data; do
    [ -e "$d" ] || continue
    p=${d#"$tree"/data/}
    p=${p%/data}
    data[$p]+="$d "
  done
done

mkdir -p "$out/src"
for f in "$build"/*; do
  case $(basename "$f") in
    src | nix-support) ;;
    *) ln -s "$f" "$out/" ;;
  esac
done

# Subsystems and packages without data: links into the build.
for sub in "$build"/src/*; do
  s=$(basename "$sub")
  touched=
  for p in "${!data[@]}"; do
    [ "${p%%/*}" = "$s" ] && touched=1 && break
  done
  if [ -z "$touched" ]; then
    ln -s "$sub" "$out/src/$s"
    continue
  fi
  mkdir "$out/src/$s"
  for pkg in "$sub"/*; do
    [ -n "${data[$s/$(basename "$pkg")]:-}" ] || ln -s "$pkg" "$out/src/$s/"
  done
done

# Packages with data: their entries linked, data/ merged from the package's
# own (if it has one) and the data trees'.
for p in "${!data[@]}"; do
  mkdir -p "$out/src/$p"
  if [ -d "$build/src/$p" ]; then
    for entry in "$build/src/$p"/* "$build/src/$p"/.[!.]*; do
      [ -e "$entry" ] && [ "$(basename "$entry")" != data ] && ln -s "$entry" "$out/src/$p/"
    done
  fi
  srcs=()
  [ -d "$build/src/$p/data" ] && srcs+=("$build/src/$p/data")
  # shellcheck disable=SC2206 # the store paths have no spaces
  srcs+=(${data[$p]})
  merge "$out/src/$p/data" "${srcs[@]}"
done

mkdir -p "$out/nix-support"
sed "s|$build|$out|g" "$build/nix-support/setup-hook" > "$out/nix-support/setup-hook"
