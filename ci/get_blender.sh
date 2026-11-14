#!/usr/bin/env bash
# Linux runner'a Blender kur (headless Cycles CPU render + VSE montaj icin). Her adim tekrar denemeli; ayna yedekli.
set -uo pipefail
SER=${BLENDER_SERIES:-5.2}
retry() { for k in 1 2 3 4 5; do "$@" && return 0; echo "tekrar ($k): $*"; sleep $((k * 10)); done; return 1; }
retry sudo apt-get update -qq || true
retry sudo apt-get install -y -qq libgl1 libegl1 libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libsm6 libxrender1 libx11-6 fonts-dejavu-core > /dev/null || exit 1
for BASE in https://download.blender.org/release https://mirrors.ocf.berkeley.edu/blender/release https://mirror.clarkson.edu/blender/release; do
  F=""
  for k in 1 2 3; do
    F=$(curl -sfL --max-time 60 "$BASE/Blender$SER/" | grep -o "blender-$SER\.[0-9]*-linux-x64\.tar\.xz" | sort -V | tail -1)
    [ -n "$F" ] && break; sleep $((k * 10))
  done
  [ -z "$F" ] && { echo "liste alinamadi: $BASE"; continue; }
  echo "Blender: $F ($BASE)"
  for k in 1 2 3; do
    if curl -sfL --retry 3 --max-time 600 -o /tmp/b.tar.xz "$BASE/Blender$SER/$F" && tar -xJf /tmp/b.tar.xz -C "$HOME"; then
      rm -f /tmp/b.tar.xz; echo "$HOME/${F%.tar.xz}" >> "$GITHUB_PATH"; exit 0
    fi
    echo "indirme tekrar ($k)"; sleep $((k * 15))
  done
done
echo "Blender indirilemedi"; exit 1
