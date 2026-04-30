declare module "*.jpeg" {
  const src: string;
  export default src;
}

interface Window {
  ccx: {
    getApiConfig: () => Promise<{
      baseUrl: string;
      token: string;
    }>;
    selectImages: () => Promise<{
      paths: string[];
      previewUrl: string;
      images?: Array<{
        path: string;
        name: string;
        dataUrl: string;
      }>;
    }>;
    createImagePreview: (imagePath: string) => Promise<string>;
    selectTowerSdDirectories: () => Promise<string[]>;
    selectGroundSdDirectory: () => Promise<string[]>;
    selectPointCloud: () => Promise<string[]>;
    selectTxtFile: (title: string) => Promise<string[]>;
  };
}
