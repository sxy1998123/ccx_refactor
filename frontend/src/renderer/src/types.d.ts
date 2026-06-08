declare module "*.jpeg" {
  const src: string;
  export default src;
}

interface Window {
  ccx: {
    login: (
      username: string,
      password: string,
    ) => Promise<
      | {
          ok: true;
          session: {
            username: string;
            displayName: string;
            loginAt: string;
          };
        }
      | {
          ok: false;
          message: string;
        }
    >;
    logout: () => Promise<void>;
    getAuthSession: () => Promise<{
      username: string;
      displayName: string;
      loginAt: string;
    } | null>;
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
    openHazardDataWorkbook: () => Promise<{
      path: string;
    }>;
    selectTowerSdDirectories: () => Promise<string[]>;
    selectGroundSdDirectory: () => Promise<string[]>;
    selectPointCloud: () => Promise<string[]>;
    selectTxtFile: (title: string) => Promise<string[]>;
  };
}
