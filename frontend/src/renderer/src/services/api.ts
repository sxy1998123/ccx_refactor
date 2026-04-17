export type AppInfo = {
  app_name: string;
  version: string;
  environment: string;
};

export async function getAppInfo(baseUrl: string): Promise<AppInfo> {
  const response = await fetch(`${baseUrl}/api/app-info`);

  if (!response.ok) {
    throw new Error(`Failed to load app info: ${response.status}`);
  }

  return response.json() as Promise<AppInfo>;
}

