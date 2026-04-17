import { app, BrowserWindow, Menu, dialog, ipcMain, net as electronNet, protocol } from "electron";
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
const imagePreviewPaths = new Map<string, string>();

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
  const env = {
    ...process.env,
    CCX_HOST: "127.0.0.1",
    CCX_PORT: String(port),
    CCX_TOKEN: token,
    CCX_ENV: isDev() ? "development" : "production",
    CCX_RELOAD: isDev() ? "1" : "0",
    CCX_DATA_DIR: app.getPath("userData"),
    CCX_DEMO_POINTCLOUD: getDemoPointcloudPath(),
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
      Menu.setApplicationMenu(null);
      registerPreviewProtocol();

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
        return {
          paths: imagePaths,
          previewUrl: imagePaths.length ? createImagePreviewUrl(imagePaths[0]) : "",
        };
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
              extensions: ["las", "laz", "pcd", "ply", "xyz", "pts", "e57"],
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
