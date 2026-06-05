$ErrorActionPreference = "Stop"

$root = (Resolve-Path "$PSScriptRoot\..").Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$backendDist = Join-Path $backend "dist"
$backendBuild = Join-Path $backend "build"
$backendPackage = Join-Path $backendDist "backend"
function Remove-WorkspaceItem([string]$PathToRemove) {
  if (-not (Test-Path -LiteralPath $PathToRemove)) {
    return
  }

  $resolved = (Resolve-Path -LiteralPath $PathToRemove).Path
  if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove outside workspace: $resolved"
  }

  Remove-Item -LiteralPath $resolved -Recurse -Force
}

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Description failed with exit code $LASTEXITCODE"
  }
}

Push-Location $backend
try {
  Invoke-Checked { conda run --no-capture-output -n ccx_backend python -m PyInstaller --version | Out-Null } "Checking PyInstaller"
}
catch {
  Invoke-Checked { conda run --no-capture-output -n ccx_backend pip install pyinstaller } "Installing PyInstaller"
}
finally {
  Pop-Location
}

Remove-WorkspaceItem $backendBuild
Remove-WorkspaceItem $backendDist

Push-Location $backend
try {
  Invoke-Checked { conda run --no-capture-output -n ccx_backend python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name backend `
    --paths . `
    --add-data "app/db/schema.sql;app/db" `
    --add-data "app/vendor/ccx;app/vendor/ccx" `
    --hidden-import app.main `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    app/run.py } "Building backend executable"
}
finally {
  Pop-Location
}

# Ensure vendor/ccx is also available alongside backend.exe (not only inside _internal/)
$backendVendorCcx = Join-Path $backend "app\vendor\ccx"
$packagedVendorCcx = Join-Path $backendPackage "app\vendor\ccx"
Remove-WorkspaceItem (Join-Path $backendPackage "app")
New-Item -ItemType Directory -Path $packagedVendorCcx -Force | Out-Null
Copy-Item -LiteralPath $backendVendorCcx -Destination $packagedVendorCcx\.. -Recurse -Force

if (-not (Test-Path -LiteralPath (Join-Path $backendPackage "backend.exe"))) {
  throw "Backend executable was not generated: $backendPackage\backend.exe"
}

Push-Location $frontend
try {
  Invoke-Checked { npm run package:win-unpacked } "Building win-unpacked package"
}
finally {
  Pop-Location
}

$winUnpacked = Join-Path $frontend "dist\win-unpacked"
if (-not (Test-Path -LiteralPath $winUnpacked)) {
  throw "win-unpacked package was not generated: $winUnpacked"
}

Write-Host "win-unpacked package generated at: $winUnpacked"
