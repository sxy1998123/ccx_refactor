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

export type DatabaseField = {
  name: string;
  display_name: string;
  type: string;
  description: string;
  required: boolean;
  primary_key: boolean;
};

export type DatabaseSchema = {
  database_path: string;
  tables: Record<
    string,
    {
      fields: DatabaseField[];
    }
  >;
};

export type CreateDatabaseRecordResponse = {
  table_name: string;
  rowid: number;
  message: string;
};

export type DeleteDatabaseRecordResponse = {
  table_name: string;
  rowid: number;
  message: string;
};

export type DatabaseRecordValue = string | number | null;

export type DatabaseRecord = {
  rowid: number;
  [key: string]: DatabaseRecordValue;
};

export type DatabaseRecordList = {
  table_name: string;
  records: DatabaseRecord[];
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

export async function getDatabaseSchema(baseUrl: string): Promise<DatabaseSchema> {
  const response = await fetch(`${baseUrl}/api/database/schema`);

  if (!response.ok) {
    throw new Error(`Failed to load database schema: ${response.status}`);
  }

  return response.json() as Promise<DatabaseSchema>;
}

export async function listDatabaseRecords(baseUrl: string, tableName: string): Promise<DatabaseRecordList> {
  const response = await fetch(`${baseUrl}/api/database/${tableName}/records?limit=20`);

  if (!response.ok) {
    throw new Error(`Failed to load database records: ${response.status}`);
  }

  return response.json() as Promise<DatabaseRecordList>;
}

export async function createDatabaseRecord(
  baseUrl: string,
  tableName: string,
  values: Record<string, string>,
): Promise<CreateDatabaseRecordResponse> {
  const response = await fetch(`${baseUrl}/api/database/${tableName}/records`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ values }),
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Failed to create database record: ${response.status}`);
  }

  return response.json() as Promise<CreateDatabaseRecordResponse>;
}

export async function deleteDatabaseRecord(
  baseUrl: string,
  tableName: string,
  rowid: number,
): Promise<DeleteDatabaseRecordResponse> {
  const response = await fetch(`${baseUrl}/api/database/${tableName}/records/${rowid}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Failed to delete database record: ${response.status}`);
  }

  return response.json() as Promise<DeleteDatabaseRecordResponse>;
}
