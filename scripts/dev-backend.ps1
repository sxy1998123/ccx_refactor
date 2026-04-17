$ErrorActionPreference = "Stop"

$env:CCX_HOST = "127.0.0.1"
$env:CCX_PORT = "18080"
$env:CCX_RELOAD = "1"

Push-Location "$PSScriptRoot\..\backend"
try {
  conda run --no-capture-output -n ccx_backend python -m app.run
}
finally {
  Pop-Location
}
