#!/usr/bin/env bash
# Esporta porta_dell_inferno.blend negli asset del gioco (game/public/).
#
#   game/tools/export_map.sh [argomenti per export_map.py]
#
# Cerca, nell'ordine: $BLENDER_PYTHON, blender (CLI), .venv/bin/python con bpy.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SCRIPT="$HERE/export_map.py"

run_with_runpy() {
  # bpy come modulo ha un bug noto: eseguito come file chiama InitGoogleLogging
  # due volte e abortisce. Passare da runpy.run_path lo evita.
  "$1" -c "import runpy, sys; sys.argv = ['export_map.py'] + sys.argv[1:]; runpy.run_path('$SCRIPT', run_name='__main__')" "${@:2}"
}

if [[ -n "${BLENDER_PYTHON:-}" ]]; then
  run_with_runpy "$BLENDER_PYTHON" "$@"
elif command -v blender >/dev/null 2>&1; then
  blender --background --python "$SCRIPT" -- "$@"
elif [[ -x "$ROOT/.venv/bin/python" ]] && "$ROOT/.venv/bin/python" -c 'import bpy' 2>/dev/null; then
  run_with_runpy "$ROOT/.venv/bin/python" "$@"
else
  echo "Serve un Python con il modulo bpy 4.5 (pip install bpy==4.5.0)" >&2
  echo "oppure la CLI di Blender. Imposta BLENDER_PYTHON per forzare un interprete." >&2
  exit 1
fi
