export type AppInfo = {
  app_name: string;
  version: string;
  environment: string;
};

export type PotreeNode = {
  id: string;
  depth: number;
  pointCount: number;
  sourcePointCount: number;
  byteSize: number;
  bounds: {
    min: [number, number, number];
    max: [number, number, number];
  };
  url: string;
};

export type PotreeManifest = {
  version: number;
  name: string;
  source: {
    file: string;
    size: number;
    mtime_ns: number;
    points: number;
    fields: string[];
    data: string;
  };
  pointFormat: "float32x3+uint32rgb";
  pointStrideBytes: number;
  bounds: {
    min: [number, number, number];
    max: [number, number, number];
  };
  nodes: PotreeNode[];
  totalVisiblePoints: number;
};

export type DemoAnalysisTaskResponse = {
  status: "completed";
  route_id: string;
  message: string;
};

export async function getAppInfo(baseUrl: string): Promise<AppInfo> {
  const response = await fetch(`${baseUrl}/api/app-info`);

  if (!response.ok) {
    throw new Error(`Failed to load app info: ${response.status}`);
  }

  return response.json() as Promise<AppInfo>;
}

export async function getDemoPointcloudManifest(baseUrl: string, signal?: AbortSignal): Promise<PotreeManifest> {
  const response = await fetch(`${baseUrl}/api/demo/pointcloud/potree/manifest`, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load point cloud manifest: ${response.status}`);
  }

  return response.json() as Promise<PotreeManifest>;
}

export async function submitDemoAnalysisTask(baseUrl: string, routeId: string): Promise<DemoAnalysisTaskResponse> {
  const response = await fetch(`${baseUrl}/api/demo/analysis-tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ route_id: routeId }),
  });

  if (!response.ok) {
    throw new Error(`Failed to submit demo analysis task: ${response.status}`);
  }

  return response.json() as Promise<DemoAnalysisTaskResponse>;
}
