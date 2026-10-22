#!/usr/bin/env bash
# Run from the OpenWrt source root, before make defconfig.
set -euo pipefail
./scripts/feeds update -a

# Xray needs Go 1.27; replace only the old Go recipes in the 24.10 feed.
go_commit=$(python3 -c 'import json; print(json.load(open(".github/passwall-upstream.json"))["commits"]["golang"])')
go_source="$PWD/feeds/passwall_golang"
if [ ! -d "$go_source/.git" ]; then
  git clone --no-checkout https://github.com/sbwml/packages_lang_golang.git "$go_source"
fi
git -C "$go_source" fetch origin "$go_commit"
git -C "$go_source" checkout --detach "$go_commit"
rm -rf feeds/packages/lang/golang
mkdir -p feeds/packages/lang/golang
git -C "$go_source" archive HEAD | tar -x -C feeds/packages/lang/golang
./scripts/feeds update -i packages

# feeds.conf.default orders the official PassWall sources before distro duplicates.
./scripts/feeds install -a
./scripts/feeds install -a -f -p passwall_packages
./scripts/feeds install -a -f -p passwall_luci
test "$(readlink -f package/feeds/passwall_luci/luci-app-passwall)" = "$PWD/feeds/passwall_luci/luci-app-passwall"
test "$(readlink -f package/feeds/passwall_packages/xray-core)" = "$PWD/feeds/passwall_packages/xray-core"
