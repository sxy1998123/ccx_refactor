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

const api = {
  getApiConfig: (): Promise<ApiConfig> => ipcRenderer.invoke("ccx:get-api-config"),
  selectImages: (): Promise<ImageSelectionResult> => ipcRenderer.invoke("ccx:select-images"),
  createImagePreview: (imagePath: string): Promise<string> => ipcRenderer.invoke("ccx:create-image-preview", imagePath),
  selectTowerSdDirectories: (): Promise<string[]> => ipcRenderer.invoke("ccx:select-tower-sd-directories"),
  selectGroundSdDirectory: (): Promise<string[]> => ipcRenderer.invoke("ccx:select-ground-sd-directory"),
  selectPointCloud: (): Promise<string[]> => ipcRenderer.invoke("ccx:select-point-cloud"),
};

contextBridge.exposeInMainWorld("ccx", api);
