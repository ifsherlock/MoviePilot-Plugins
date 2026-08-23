#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
context_dir="$repo_root/scripts/webrtcvad-wheel"
output_dir="${1:-$repo_root/plugins.v3/subtitlemanualupload/wheels}"
version="${WEBRTCVAD_VERSION:-2.0.14}"

mkdir -p "$output_dir"
rm -f "$output_dir"/webrtcvad_wheels-*.whl "$output_dir/SHA256SUMS"

for platform in linux/amd64 linux/arm64; do
    build_dir="$(mktemp -d)"
    trap 'rm -rf "$build_dir"' EXIT

    echo "Building webrtcvad-wheels ${version} for ${platform}"
    docker buildx build \
        --platform "$platform" \
        --build-arg "WEBRTCVAD_VERSION=${version}" \
        --progress plain \
        --output "type=local,dest=${build_dir}" \
        "$context_dir"

    wheel="$(find "$build_dir" -maxdepth 2 -type f -name 'webrtcvad_wheels-*.whl' -print -quit)"
    if [[ -z "$wheel" ]]; then
        echo "No wheel was produced for ${platform}" >&2
        exit 1
    fi

    cp "$wheel" "$output_dir/"
    sha256sum "$wheel" | sed "s#${build_dir}/##" >> "$output_dir/SHA256SUMS"
    rm -rf "$build_dir"
    trap - EXIT
done

sort -o "$output_dir/SHA256SUMS" "$output_dir/SHA256SUMS"
echo "Wheels written to $output_dir"
