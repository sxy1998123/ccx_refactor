# CCX Backend

FastAPI backend for the local Electron desktop application.

## Setup

```powershell
conda env create -f backend/environment.yml
conda activate ccx_backend
```

The environment has already been created on this machine as `ccx_backend`.

## Run

```powershell
$env:CCX_HOST = "127.0.0.1"
$env:CCX_PORT = "18080"
$env:CCX_RELOAD = "1"
Push-Location backend
conda run --no-capture-output -n ccx_backend python -m app.run
Pop-Location
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:18080/health
```
