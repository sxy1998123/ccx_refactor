# CCX Frontend

Electron + Vite + Vue desktop frontend.

## Install

```powershell
cd frontend
npm install
```

## Development

```powershell
cd frontend
npm run dev
```

The Electron main process starts the FastAPI backend through the `ccx_backend` conda environment.

## Build

```powershell
cd frontend
npm run build
```

Executable packaging is intentionally left out of the first development scaffold. Add it after the backend executable layout is fixed.
