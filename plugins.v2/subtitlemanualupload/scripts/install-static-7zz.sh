#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-26.01}"
INSTALL_PATH="${INSTALL_PATH:-/opt/bin/7zz}"
MP_CONTAINER="${MP_CONTAINER:-}"
DOWNLOAD_URL="${DOWNLOAD_URL:-}"

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
  docker ps --format '{{.Names}}' | awk 'tolower($0) ~ /moviepilot|mp/ { print; exit }'
}

need_cmd uname
need_cmd tar
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

platform="$(detect_platform)"
version_num="${VERSION//./}"
asset="7z${version_num}-${platform}.tar.xz"
url="${DOWNLOAD_URL:-https://github.com/ip7z/7zip/releases/download/${VERSION}/${asset}}"
archive="${tmp_dir}/${asset}"

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

container="$(detect_moviepilot_container || true)"
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
EOF
