#!/usr/bin/env bash
# Copia le dipendenze ESM da node_modules a game/vendor/, così il gioco gira
# senza bundler e senza CDN (basta un server di file statici).
#
#   game/tools/vendor.sh        (richiede: npm install in game/)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME="$(cd "$HERE/.." && pwd)"
NM="$GAME/node_modules"
VENDOR="$GAME/vendor"

[[ -d "$NM/three" ]] || { echo "manca node_modules: esegui 'npm install' in game/" >&2; exit 1; }

rm -rf "$VENDOR"
mkdir -p "$VENDOR/three" "$VENDOR/three-addons/loaders" "$VENDOR/three-addons/utils" "$VENDOR/three-addons/libs"

cp "$NM/three/build/three.module.js" "$NM/three/build/three.core.js" "$VENDOR/three/"
cp "$NM/three/examples/jsm/loaders/GLTFLoader.js"        "$VENDOR/three-addons/loaders/"
cp "$NM/three/examples/jsm/utils/BufferGeometryUtils.js" "$VENDOR/three-addons/utils/"
cp "$NM/three/examples/jsm/utils/SkeletonUtils.js"       "$VENDOR/three-addons/utils/"
cp "$NM/three/examples/jsm/libs/meshopt_decoder.module.js" "$VENDOR/three-addons/libs/"
# three-mesh-bvh importa 'three' (risolto dall'import map): basta la sorgente ESM.
cp -r "$NM/three-mesh-bvh/src/." "$VENDOR/three-mesh-bvh/" 2>/dev/null \
  || { mkdir -p "$VENDOR/three-mesh-bvh"; cp -r "$NM/three-mesh-bvh/src/." "$VENDOR/three-mesh-bvh/"; }

# Versioni registrate, per riproducibilità.
node -e '
const fs = require("fs");
const pkg = (p) => JSON.parse(fs.readFileSync(p, "utf8")).version;
const out = {
  three: pkg(process.argv[1]),
  "three-mesh-bvh": pkg(process.argv[2]),
  meshoptimizer: pkg(process.argv[3]),
};
fs.writeFileSync(process.argv[4], JSON.stringify(out, null, 2) + "\n");
' "$NM/three/package.json" "$NM/three-mesh-bvh/package.json" "$NM/meshoptimizer/package.json" "$VENDOR/versions.json"

du -sh "$VENDOR"
echo "vendor pronto: $(ls "$VENDOR")"
