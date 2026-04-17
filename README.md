# CCX Refactor

Desktop scaffold for the Yuxi transmission tower risk assessment software.

## Layout

```text
backend/   FastAPI local service
frontend/  Electron + Vite + Vue desktop client
scripts/   Development helper scripts
```

## Backend

The backend uses the conda environment `ccx_backend`.

```powershell
conda activate ccx_backend
$env:CCX_HOST = "127.0.0.1"
$env:CCX_PORT = "18080"
$env:CCX_RELOAD = "1"
cd backend
python -m app.run
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

In development, Electron starts the FastAPI backend automatically through:

```powershell
conda run --no-capture-output -n ccx_backend python -m app.run
```

## Smoke Checks

```powershell
.\scripts\dev-backend.ps1
Invoke-RestMethod http://127.0.0.1:18080/health
cd frontend
npm run build
```
