import { app, BrowserWindow, Menu, dialog, ipcMain, net as electronNet, protocol, shell } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { pathToFileURL } from "node:url";

type ApiConfig = {
  baseUrl: string;
  token: string;
};

type AuthSession = {
  username: string;
  displayName: string;
  loginAt: string;
};

type LoginResult =
  | {
      ok: true;
      session: AuthSession;
    }
  | {
      ok: false;
      message: string;
    };

type FileDialogOptions = {
  title: string;
  properties: Array<"openFile" | "openDirectory" | "multiSelections">;
  filters?: Electron.FileFilter[];
};

const NODE_LOG_PREFIX = "[node]";
const PYTHON_LOG_PREFIX = "[python]";

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
let apiConfig: ApiConfig | null = null;
let authSession: AuthSession | null = null;
const imagePreviewPaths = new Map<string, string>();

const localUsers = [
  {
    username: "admin",
    password: "admin123",
    displayName: "系统管理员",
  },
];

protocol.registerSchemesAsPrivileged([
  {
    scheme: "ccx-preview",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
    },
  },
]);

function ensureLogPrefix(prefix: string, line: string): string {
  return line.startsWith(prefix) ? line : `${prefix} ${line}`;
}

function createPrefixedLineWriter(prefix: string, writer: (message: string) => void) {
  let buffered = "";

  return {
    write(chunk: Buffer): void {
      buffered += chunk.toString("utf8");
      const lines = buffered.split(/\r?\n/);
      buffered = lines.pop() ?? "";

      for (const line of lines) {
        if (line.trim()) {
          writer(ensureLogPrefix(prefix, line));
        }
      }
    },
    flush(): void {
      if (buffered.trim()) {
        writer(ensureLogPrefix(prefix, buffered));
      }
      buffered = "";
    },
  };
}

function nodeInfo(message: string): void {
  console.log(ensureLogPrefix(NODE_LOG_PREFIX, message));
}

function nodeError(message: string): void {
  console.error(ensureLogPrefix(NODE_LOG_PREFIX, message));
}

function isDev(): boolean {
  return !app.isPackaged;
}

function getAppIconPath(): string {
  if (isDev()) {
    return path.resolve(app.getAppPath(), "resources", "icon.png");
  }

  return path.join(process.resourcesPath, "resources", "icon.png");
}

function getDemoPointcloudPath(): string {
  const pointCloudFile = path.join("pointcloud_demo", "geomap_20260321_122228.pcd");
  if (isDev()) {
    return path.resolve(app.getAppPath(), "..", "backend", pointCloudFile);
  }

  return path.join(process.resourcesPath, "backend", pointCloudFile);
}

function getCcxSolverRoot(): string {
  if (isDev()) {
    return path.resolve(app.getAppPath(), "..", "backend", "app", "vendor", "ccx");
  }

  return path.join(process.resourcesPath, "backend", "app", "vendor", "ccx");
}

function getHazardDataWorkbookCandidates(): string[] {
  if (isDev()) {
    return [path.resolve(app.getAppPath(), "..", "backend", "app", "db", "excel", "data.xlsx")];
  }

  return [
    path.join(process.resourcesPath, "backend", "app", "db", "excel", "data.xlsx"),
    path.join(process.resourcesPath, "backend", "_internal", "app", "db", "excel", "data.xlsx"),
  ];
}

async function openHazardDataWorkbook(): Promise<{ path: string }> {
  const candidates = getHazardDataWorkbookCandidates();
  const workbookPath = candidates.find((candidate) => fs.existsSync(candidate));
  if (!workbookPath) {
    throw new Error(`历史地质灾害数据文件不存在：${candidates[0]}`);
  }

  const openError = await shell.openPath(workbookPath);
  if (openError) {
    throw new Error(openError);
  }

  return { path: workbookPath };
}

function login(username: unknown, password: unknown): LoginResult {
  const normalizedUsername = typeof username === "string" ? username.trim() : "";
  const normalizedPassword = typeof password === "string" ? password : "";
  const user = localUsers.find(
    (candidate) => candidate.username === normalizedUsername && candidate.password === normalizedPassword,
  );

  if (!user) {
    return {
      ok: false,
      message: "用户名或密码不正确",
    };
  }

  authSession = {
    username: user.username,
    displayName: user.displayName,
    loginAt: new Date().toISOString(),
  };

  return {
    ok: true,
    session: authSession,
  };
}

function logout(): void {
  authSession = null;
}

function getFreePort(startPort: number): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();

    server.once("error", (error: NodeJS.ErrnoException) => {
      if (error.code === "EADDRINUSE") {
        getFreePort(startPort + 1).then(resolve).catch(reject);
        return;
      }
      reject(error);
    });

    server.once("listening", () => {
      const address = server.address();
      server.close(() => {
        resolve(typeof address === "object" && address ? address.port : startPort);
      });
    });

    server.listen(startPort, "127.0.0.1");
  });
}

function registerPreviewProtocol(): void {
  protocol.handle("ccx-preview", async (request) => {
    const url = new URL(request.url);

    if (url.hostname !== "image") {
      return new Response("Not found", { status: 404 });
    }

    const previewId = url.pathname.replace(/^\//, "");
    const imagePath = imagePreviewPaths.get(previewId);
    if (!imagePath) {
      return new Response("Not found", { status: 404 });
    }

    try {
      await fs.promises.access(imagePath, fs.constants.R_OK);
      return electronNet.fetch(pathToFileURL(imagePath).toString());
    } catch {
      return new Response("Not found", { status: 404 });
    }
  });
}

function createImagePreviewUrl(imagePath: string): string {
  const previewId = crypto.randomUUID();
  imagePreviewPaths.set(previewId, imagePath);
  return `ccx-preview://image/${previewId}`;
}

function getImageMimeType(imagePath: string): string {
  const ext = path.extname(imagePath).toLowerCase();
  switch (ext) {
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".png":
      return "image/png";
    case ".bmp":
      return "image/bmp";
    case ".webp":
      return "image/webp";
    case ".tif":
    case ".tiff":
      return "image/tiff";
    default:
      return "application/octet-stream";
  }
}

async function createImageDataUrl(imagePath: string): Promise<string> {
  const content = await fs.promises.readFile(imagePath);
  return `data:${getImageMimeType(imagePath)};base64,${content.toString("base64")}`;
}

async function waitForBackend(baseUrl: string, timeoutMs = 30000): Promise<void> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) {
        return;
      }
    } catch {
      // Backend is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  throw new Error(`Backend did not become ready within ${timeoutMs}ms`);
}

async function startBackend(): Promise<ApiConfig> {
  if (apiConfig) {
    return apiConfig;
  }

  const port = await getFreePort(18080);
  const token = crypto.randomUUID();
  const baseUrl = `http://127.0.0.1:${port}`;

  const backendCwd = isDev()
    ? path.resolve(app.getAppPath(), "..", "backend")
    : path.join(process.resourcesPath, "backend");
  const backendDataDir = path.join(backendCwd, "data");
  const env = {
    ...process.env,
    CCX_HOST: "127.0.0.1",
    CCX_PORT: String(port),
    CCX_TOKEN: token,
    CCX_ENV: isDev() ? "development" : "production",
    CCX_RELOAD: isDev() ? "1" : "0",
    CCX_DATA_DIR: backendDataDir,
    CCX_RESULTS_DIR: path.join(backendDataDir, "risk"),
    CCX_DATABASE_PATH: path.join(backendDataDir, "ccx.sqlite3"),
    CCX_SOLVER_ROOT: getCcxSolverRoot(),
    CCX_RAINFALL_DATA_DIR: path.join(getCcxSolverRoot(), "数据"),
    CCX_DEMO_POINTCLOUD: getDemoPointcloudPath(),
    CCX_HAZARD_EXCEL_PATH: getHazardDataWorkbookCandidates()[0],
  };

  nodeInfo(`starting python backend at ${baseUrl}`);

  if (isDev()) {
    backendProcess = spawn(
      "conda",
      ["run", "--no-capture-output", "-n", "ccx_backend", "python", "-m", "app.run"],
      {
        cwd: backendCwd,
        env,
        windowsHide: true,
      },
    );
  } else {
    const backendExe = path.join(process.resourcesPath, "backend", "backend.exe");
    backendProcess = spawn(backendExe, [], {
      cwd: path.dirname(backendExe),
      env,
      windowsHide: true,
    });
  }

  const pythonStdout = createPrefixedLineWriter(PYTHON_LOG_PREFIX, console.log);
  const pythonStderr = createPrefixedLineWriter(PYTHON_LOG_PREFIX, console.error);

  backendProcess.stdout.on("data", (chunk) => {
    pythonStdout.write(chunk);
  });
  backendProcess.stderr.on("data", (chunk) => {
    pythonStderr.write(chunk);
  });
  backendProcess.once("exit", (code, signal) => {
    pythonStdout.flush();
    pythonStderr.flush();
    nodeInfo(`python backend exited code=${code ?? "null"} signal=${signal ?? "null"}`);
    backendProcess = null;
    apiConfig = null;
  });

  await waitForBackend(baseUrl);
  apiConfig = { baseUrl, token };
  nodeInfo(`python backend is ready at ${baseUrl}`);
  return apiConfig;
}

function stopBackend(): void {
  if (!backendProcess?.pid) {
    return;
  }

  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(backendProcess.pid), "/t", "/f"], {
      windowsHide: true,
    });
  } else {
    backendProcess.kill("SIGTERM");
  }

  backendProcess = null;
  apiConfig = null;
}

async function selectInputFiles(options: FileDialogOptions): Promise<string[]> {
  const dialogOptions = {
    title: options.title,
    properties: options.properties,
    filters: options.filters,
  };
  const result = mainWindow
    ? await dialog.showOpenDialog(mainWindow, dialogOptions)
    : await dialog.showOpenDialog(dialogOptions);

  if (result.canceled) {
    return [];
  }

  return result.filePaths;
}

async function createWindow(): Promise<void> {
  const config = await startBackend();

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1100,
    minHeight: 720,
    show: false,
    icon: getAppIconPath(),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--ccx-api-base=${config.baseUrl}`, `--ccx-api-token=${config.token}`],
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.setMenuBarVisibility(false);
    mainWindow?.show();
  });

  if (isDev() && process.env.ELECTRON_RENDERER_URL) {
    await mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    await mainWindow.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
}

const gotLock = app.requestSingleInstanceLock();

if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.focus();
    }
  });

  app
    .whenReady()
    .then(async () => {
      // 隐藏控制台和menubar
      // Menu.setApplicationMenu(null);
      registerPreviewProtocol();

      ipcMain.handle("ccx:login", async (_event, username: unknown, password: unknown) => {
        return login(username, password);
      });
      ipcMain.handle("ccx:logout", async () => {
        logout();
      });
      ipcMain.handle("ccx:get-auth-session", async () => {
        return authSession;
      });
      ipcMain.handle("ccx:get-api-config", async () => {
        return apiConfig ?? startBackend();
      });
      ipcMain.handle("ccx:select-images", async () => {
        const imagePaths = await selectInputFiles({
          title: "选择航拍或手机图片",
          properties: ["openFile", "multiSelections"],
          filters: [
            {
              name: "图片文件",
              extensions: ["jpg", "jpeg", "png", "bmp", "tif", "tiff", "webp"],
            },
          ],
        });
        const images = [];
        for (const imagePath of imagePaths) {
          try {
            images.push({
              path: imagePath,
              name: path.basename(imagePath),
              dataUrl: await createImageDataUrl(imagePath),
            });
          } catch (error) {
            nodeError(
              `failed to encode image as base64 path=${imagePath} error=${
                error instanceof Error ? error.message : String(error)
              }`,
            );
          }
        }

        return {
          paths: imagePaths,
          previewUrl: images[0]?.dataUrl ?? "",
          images,
        };
      });
      ipcMain.handle("ccx:create-image-preview", async (_event, imagePath: unknown) => {
        if (typeof imagePath !== "string" || !imagePath.trim()) {
          return "";
        }

        return createImagePreviewUrl(imagePath);
      });
      ipcMain.handle("ccx:open-hazard-data-workbook", async () => {
        return openHazardDataWorkbook();
      });
      ipcMain.handle("ccx:select-tower-sd-directories", async () => {
        return selectInputFiles({
          title: "选择塔基端 SD 卡目录",
          properties: ["openDirectory", "multiSelections"],
        });
      });
      ipcMain.handle("ccx:select-ground-sd-directory", async () => {
        return selectInputFiles({
          title: "选择探地端 SD 卡目录",
          properties: ["openDirectory"],
        });
      });
      ipcMain.handle("ccx:select-point-cloud", async () => {
        return selectInputFiles({
          title: "选择点云文件",
          properties: ["openFile"],
          filters: [
            {
              name: "点云文件",
              extensions: ["pcd"],
            },
          ],
        });
      });
      ipcMain.handle("ccx:select-txt-file", async (_event, title: unknown) => {
        return selectInputFiles({
          title: typeof title === "string" && title.trim() ? title : "选择 TXT 文件",
          properties: ["openFile"],
          filters: [
            {
              name: "TXT 文件",
              extensions: ["txt"],
            },
          ],
        });
      });

      await createWindow();

      app.on("activate", async () => {
        if (BrowserWindow.getAllWindows().length === 0) {
          await createWindow();
        }
      });
    })
    .catch((error: unknown) => {
      nodeError(error instanceof Error ? error.stack ?? error.message : String(error));
      app.quit();
    });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  app.on("before-quit", () => {
    stopBackend();
  });
}
