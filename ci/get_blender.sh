#!/usr/bin/env bash
# Linux runner'a Blender kur (headless Cycles CPU render + VSE montaj icin)
set -euo pipefail
SER=${BLENDER_SERIES:-5.2}
sudo apt-get update -qq
sudo apt-get install -y -qq libgl1 libegl1 libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libsm6 libxrender1 libx11-6 fonts-dejavu-core > /dev/null
F=$(curl -s https://download.blender.org/release/Blender$SER/ | grep -o "blender-$SER\.[0-9]*-linux-x64\.tar\.xz" | sort -V | tail -1)
echo "Blender: $F"
curl -sL https://download.blender.org/release/Blender$SER/$F | tar -xJ -C $HOME
echo "$HOME/${F%.tar.xz}" >> $GITHUB_PATH
