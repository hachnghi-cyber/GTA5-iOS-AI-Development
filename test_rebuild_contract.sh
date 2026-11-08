#!/usr/bin/env bash
set -euo pipefail

source_file='DynamicVehicleFirstPersonIOS.2.cs'
test -s "$source_file"
test -s 'DFPV_Camera.ini'
test -s 'refs/ScriptHookVDotNet2.dll'
test -s 'refs/System.Windows.Forms.dll'

# Two in-vehicle views only; no scripted exterior camera and no old R7-R10 code.
rg -Fq 'StockFirstPersonView = 4' "$source_file"
rg -Fq 'private bool _customSelected;' "$source_file"
rg -Fq 'private void ToggleView()' "$source_file"
rg -Fq 'GET_GAMEPLAY_CAM_COORD' "$source_file"
rg -Fq 'GET_OFFSET_FROM_ENTITY_GIVEN_WORLD_COORDS' "$source_file"
rg -Fq 'CameraOffsets()' "$source_file"
rg -Fq 'RepositionCamera()' "$source_file"
rg -Fq 'SET_PED_RESET_FLAG' "$source_file"
rg -Fq '120f, 0.05f, -0.09f, 0f, -40.30f' "$source_file"
rg -Fq 'Pitch=-40.3000' DFPV_Camera.ini

if rg -n 'CREATE_CAM_WITH_PARAMS|CameraPreset\[\]|case 6:|case 7:' "$source_file"; then
    echo 'Unexpected old-camera or Windows-ASI code' >&2
    exit 1
fi

echo 'Contract: two in-vehicle views, stock-eye anchor, bike video preset verified.'
