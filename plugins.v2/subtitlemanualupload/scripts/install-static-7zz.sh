#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-26.01}"
INSTALL_PATH="${INSTALL_PATH:-}"
MP_CONTAINER="${MP_CONTAINER:-}"
DOWNLOAD_URL="${DOWNLOAD_URL:-}"
TOOL_SUBDIR="${TOOL_SUBDIR:-tools}"

log() {
  printf '[SubtitleManualUpload] %s\n' "$*"
}

fail() {
  printf '[SubtitleManualUpload] ERROR: %s\n' "$*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

detect_platform() {
  case "$(uname -m)" in
    x86_64|amd64) echo "linux-x64" ;;
    aarch64|arm64) echo "linux-arm64" ;;
    armv7l|armv7*) echo "linux-arm" ;;
    i386|i686) echo "linux-x86" ;;
    *) fail "unsupported CPU architecture: $(uname -m)" ;;
  esac
}

download_file() {
  local url="$1"
  local target="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --connect-timeout 20 -o "$target" "$url"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -O "$target" "$url"
    return
  fi
  fail "curl or wget is required to download 7zz"
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi
  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi
  fail "root or sudo is required to install ${INSTALL_PATH}"
}

detect_moviepilot_container() {
  if [ -n "$MP_CONTAINER" ]; then
    echo "$MP_CONTAINER"
    return
  fi
  if ! command -v docker >/dev/null 2>&1; then
    return
  fi
  docker ps --format '{{.Names}}' | awk 'tolower($0) ~ /movie[-_]?pilot|^mp($|[-_])/ { print; exit }'
}

path_basename() {
  local path="${1%/}"
  printf '%s\n' "${path##*/}"
}

path_dirname() {
  local path="${1%/}"
  local parent="${path%/*}"
  if [ "$parent" = "$path" ]; then
    printf '%s\n' "$path"
    return
  fi
  printf '%s\n' "${parent:-/}"
}

candidate_root_from_mount() {
  local source="${1%/}"
  local dest="${2%/}"
  local source_l="${source,,}"
  local dest_l="${dest,,}"
  local base_l

  [ -n "$source" ] || return
  if [[ "$source_l" != *moviepilot* && "$source_l" != *movie-pilot* && "$source_l" != *movie_pilot* && "$dest_l" != *moviepilot* && "$dest_l" != *movie-pilot* && "$dest_l" != *movie_pilot* && "$dest_l" != "/config" && "$dest_l" != "/app/config" ]]; then
    return
  fi

  base_l="$(path_basename "$source")"
  base_l="${base_l,,}"
  if [[ "$base_l" =~ ^(config|configs|data|db|logs|log|cache|temp|tmp)$ ]]; then
    path_dirname "$source"
    return
  fi
  printf '%s\n' "$source"
}

detect_moviepilot_root_from_container() {
  local container="$1"
  local type source dest candidate
  [ -n "$container" ] || return
  command -v docker >/dev/null 2>&1 || return

  while IFS=$'\t' read -r type source dest; do
    [ "$type" = "bind" ] || continue
    candidate="$(candidate_root_from_mount "$source" "$dest" || true)"
    if [ -n "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done < <(docker inspect --format '{{range .Mounts}}{{println .Type "\t" .Source "\t" .Destination}}{{end}}' "$container" 2>/dev/null)
}

detect_moviepilot_root_from_common_paths() {
  local path
  for path in \
    /vol1/1000/docker/moviepilot \
    /vol1/1000/docker/MoviePilot \
    /vol1/1000/docker/movie-pilot \
    /volume1/docker/moviepilot \
    /volume1/docker/MoviePilot \
    /volume1/docker/movie-pilot \
    /volume1/@appdata/moviepilot \
    /opt/moviepilot \
    /root/moviepilot \
    /home/moviepilot
  do
    if [ -d "$path" ]; then
      printf '%s\n' "$path"
      return
    fi
  done

  if [ -d /vol1/1000/docker ]; then
    printf '%s\n' /vol1/1000/docker/moviepilot
    return
  fi
  if [ -d /volume1/docker ]; then
    printf '%s\n' /volume1/docker/moviepilot
    return
  fi
  printf '%s\n' /opt/moviepilot
}

resolve_install_path() {
  local container="$1"
  local root
  if [ -n "$INSTALL_PATH" ]; then
    printf '%s\n' "$INSTALL_PATH"
    return
  fi

  root="$(detect_moviepilot_root_from_container "$container" || true)"
  if [ -z "$root" ]; then
    root="$(detect_moviepilot_root_from_common_paths)"
  fi
  printf '%s/%s/7zz\n' "${root%/}" "$TOOL_SUBDIR"
}

need_cmd uname
need_cmd tar
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
container="$(detect_moviepilot_container || true)"
INSTALL_PATH="$(resolve_install_path "$container")"

platform="$(detect_platform)"
version_num="${VERSION//./}"
asset="7z${version_num}-${platform}.tar.xz"
url="${DOWNLOAD_URL:-https://github.com/ip7z/7zip/releases/download/${VERSION}/${asset}}"
archive="${tmp_dir}/${asset}"

log "install path: ${INSTALL_PATH}"
log "downloading ${asset}"
download_file "$url" "$archive"

log "extracting 7zz"
tar -xf "$archive" -C "$tmp_dir" 7zz
test -f "${tmp_dir}/7zz" || fail "7zz not found in downloaded archive"

install_dir="$(dirname "$INSTALL_PATH")"
run_as_root install -d -m 0755 "$install_dir"
run_as_root install -m 0755 "${tmp_dir}/7zz" "$INSTALL_PATH"

"$INSTALL_PATH" -h >/dev/null 2>&1 || fail "installed 7zz is not executable: ${INSTALL_PATH}"
log "installed static 7zz: ${INSTALL_PATH}"

if [ -n "$container" ] && command -v docker >/dev/null 2>&1; then
  log "detected MoviePilot container: ${container}"
  if docker exec "$container" sh -lc 'command -v 7z >/dev/null 2>&1 && 7z i >/dev/null 2>&1' >/dev/null 2>&1; then
    log "container already has usable 7z in PATH"
    exit 0
  fi
  log "container cannot see 7z yet; add the volume mapping below and recreate/restart the container"
elif [ -n "$container" ]; then
  log "Docker CLI was not found; add the volume mapping below to your MoviePilot compose"
else
  log "MoviePilot container was not detected; add the volume mapping below to your MoviePilot compose"
fi

cat <<EOF

Add this to the MoviePilot service volumes:
  - ${INSTALL_PATH}:/usr/local/bin/7z:ro

Then recreate or restart MoviePilot, and verify:
  docker exec <moviepilot-container> which 7z
  docker exec <moviepilot-container> 7z i

If your container name is known, rerun detection with:
  MP_CONTAINER=<moviepilot-container> bash plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh

You can override the install path manually:
  INSTALL_PATH=/volume1/docker/moviepilot/tools/7zz bash plugins.v2/subtitlemanualupload/scripts/install-static-7zz.sh
EOF
