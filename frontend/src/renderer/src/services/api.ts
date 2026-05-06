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

export type StressCloud = {
  source: string;
  unit: string;
  nodes: Array<[number, number, number]>;
  elements: Array<[number, number]>;
  element_labels: number[];
  stress: {
    values: number[];
    min: number;
    max: number;
  };
  bounds: {
    min: [number, number, number];
    max: [number, number, number];
  };
  max_stress: {
    value: number;
    element_index: number;
    element_label: number | null;
  };
};

export type DemoAnalysisTaskResponse = {
  status: "completed";
  route_id: string;
  message: string;
};

export type PreprocessTaskStatus = "queued" | "running" | "completed" | "failed";

export type PreprocessTaskRequest = {
  route_id: string;
  tower_type: string;
  inp_file: string;
  tower_txt_files: Record<"tower1" | "tower2" | "tower3" | "tower4", string>;
  env_txt_file: string;
  image_files: string[];
  point_cloud_files: string[];
};

export type PreprocessTaskResponse = {
  task_id: string;
  status: PreprocessTaskStatus;
  route_id: string;
  tower_type: string;
  inp_file: string;
  created_at: string;
  updated_at: string;
  message: string;
  result_url: string;
};

export type PreprocessMetric = {
  value: number;
  unit: string;
  count?: number;
};

export type PreprocessTowerResult = {
  source_file: string;
  file_name: string;
  target_date: string;
  gnss: {
    valid_count: number;
    mean_lat: number | null;
    mean_lon: number | null;
    mean_alt_m: number | null;
  };
  imu: {
    valid_data_count: number;
    duration_minutes: number;
    x_drift_m?: number | null;
    y_drift_m?: number | null;
    z_drift_m?: number | null;
    total_drift_m?: number | null;
    x_drift_mm: number | null;
    y_drift_mm: number | null;
    z_drift_mm: number | null;
    total_drift_mm: number | null;
  };
};

export type PreprocessResult = {
  task_id: string;
  status: PreprocessTaskStatus;
  message: string;
  route_id: string;
  tower_type: string;
  inp_file: string;
  inputs?: {
    tower_txt_files: Record<string, string>;
    env_txt_file: string;
    image_files: string[];
    point_cloud_files: string[];
  };
  environment?: {
    source_file: string;
    start_time: string;
    end_time: string;
    record_count: number;
    metrics: Record<string, PreprocessMetric>;
  };
  tower_results?: Record<string, PreprocessTowerResult>;
  tower_summary?: {
    tower_count: number;
    mean_lat: number | null;
    mean_lon: number | null;
    mean_alt_m: number | null;
    max_total_drift_mm: number | null;
    max_drift_source: string;
    max_drift_slot: string;
    ccx_displacement_m?: {
      x: number | null;
      y: number | null;
      z: number | null;
    };
    ccx_displacement_mm?: {
      x: number | null;
      y: number | null;
      z: number | null;
    };
  };
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

export async function getPointcloudManifest(
  baseUrl: string,
  manifestPath: string,
  signal?: AbortSignal,
): Promise<PotreeManifest> {
  const response = await fetch(`${baseUrl}${manifestPath}`, { signal });

  if (!response.ok) {
    throw new Error(`Failed to load point cloud manifest: ${response.status}`);
  }

  return response.json() as Promise<PotreeManifest>;
}

export async function getStressCloud(baseUrl: string, signal?: AbortSignal): Promise<StressCloud> {
  const response = await fetch(`${baseUrl}/api/risk/base-stress-cloud`, { signal });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Failed to load stress cloud: ${response.status}`);
  }

  return response.json() as Promise<StressCloud>;
}

export async function submitPreprocessTask(
  baseUrl: string,
  request: PreprocessTaskRequest,
): Promise<PreprocessTaskResponse> {
  const response = await fetch(`${baseUrl}/api/preprocess/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Failed to submit preprocess task: ${response.status}`);
  }

  return response.json() as Promise<PreprocessTaskResponse>;
}

export async function getPreprocessTask(baseUrl: string, taskId: string): Promise<PreprocessTaskResponse> {
  const response = await fetch(`${baseUrl}/api/preprocess/tasks/${taskId}`);

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Failed to load preprocess task: ${response.status}`);
  }

  return response.json() as Promise<PreprocessTaskResponse>;
}

export async function getPreprocessResult(baseUrl: string, taskId: string): Promise<PreprocessResult> {
  const response = await fetch(`${baseUrl}/api/preprocess/tasks/${taskId}/result`);

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Failed to load preprocess result: ${response.status}`);
  }

  return response.json() as Promise<PreprocessResult>;
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
