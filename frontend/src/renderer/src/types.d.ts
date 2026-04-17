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
    }>;
    selectTowerSdDirectories: () => Promise<string[]>;
    selectGroundSdDirectory: () => Promise<string[]>;
    selectPointCloud: () => Promise<string[]>;
  };
}
