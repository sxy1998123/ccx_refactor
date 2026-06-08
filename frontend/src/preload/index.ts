import { contextBridge, ipcRenderer } from "electron";

type ApiConfig = {
  baseUrl: string;
  token: string;
};

type ImageSelectionResult = {
  paths: string[];
  previewUrl: string;
  images?: Array<{
    path: string;
    name: string;
    dataUrl: string;
  }>;
};

type OpenWorkbookResult = {
  path: string;
};

const api = {
  getApiConfig: (): Promise<ApiConfig> => ipcRenderer.invoke("ccx:get-api-config"),
  selectImages: (): Promise<ImageSelectionResult> => ipcRenderer.invoke("ccx:select-images"),
  createImagePreview: (imagePath: string): Promise<string> => ipcRenderer.invoke("ccx:create-image-preview", imagePath),
  openHazardDataWorkbook: (): Promise<OpenWorkbookResult> => ipcRenderer.invoke("ccx:open-hazard-data-workbook"),
  selectTowerSdDirectories: (): Promise<string[]> => ipcRenderer.invoke("ccx:select-tower-sd-directories"),
  selectGroundSdDirectory: (): Promise<string[]> => ipcRenderer.invoke("ccx:select-ground-sd-directory"),
  selectPointCloud: (): Promise<string[]> => ipcRenderer.invoke("ccx:select-point-cloud"),
  selectTxtFile: (title: string): Promise<string[]> => ipcRenderer.invoke("ccx:select-txt-file", title),
};

contextBridge.exposeInMainWorld("ccx", api);
