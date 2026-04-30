<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { getPointcloudManifest, type PotreeManifest, type PotreeNode } from "../services/api";

const props = defineProps<{
  baseUrl: string;
  manifestPath: string;
}>();

const viewportRef = ref<HTMLDivElement | null>(null);
const statusText = ref("等待后端服务");
const errorText = ref("");
const loadedNodes = ref(0);
const totalNodes = ref(0);
const loadedPoints = ref(0);
const totalVisiblePoints = ref(0);
const sourcePoints = ref(0);

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;
let pointGroup: THREE.Group | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationFrame = 0;
let abortController: AbortController | null = null;
let activeRunId = 0;
let currentManifest: PotreeManifest | null = null;

watch(
  () => [props.baseUrl, props.manifestPath] as const,
  ([baseUrl]) => {
    if (!baseUrl || !props.manifestPath) {
      statusText.value = "等待后端服务";
      return;
    }
    void loadPointCloud(baseUrl);
  },
  { immediate: true, flush: "post" },
);

onBeforeUnmount(() => {
  activeRunId += 1;
  abortController?.abort();
  disposeScene();
});

async function loadPointCloud(baseUrl: string): Promise<void> {
  const runId = activeRunId + 1;
  activeRunId = runId;
  abortController?.abort();
  abortController = new AbortController();

  errorText.value = "";
  loadedNodes.value = 0;
  totalNodes.value = 0;
  loadedPoints.value = 0;
  totalVisiblePoints.value = 0;
  sourcePoints.value = 0;
  statusText.value = "正在准备点云数据";

  await nextTick();
  if (runId !== activeRunId) {
    return;
  }

  initializeScene();

  try {
    const manifest = await getPointcloudManifest(baseUrl, props.manifestPath, abortController.signal);
    if (runId !== activeRunId) {
      return;
    }

    currentManifest = manifest;
    totalNodes.value = manifest.nodes.length;
    totalVisiblePoints.value = manifest.totalVisiblePoints;
    sourcePoints.value = manifest.source.points;
    fitCameraToBounds(manifest.bounds.min, manifest.bounds.max);
    statusText.value = "正在渐进加载点云";

    const nodes = [...manifest.nodes].sort((a, b) => a.depth - b.depth || a.id.localeCompare(b.id));
    for (const node of nodes) {
      if (runId !== activeRunId || abortController.signal.aborted) {
        return;
      }
      await loadNode(baseUrl, node, abortController.signal);
      loadedNodes.value += 1;
      loadedPoints.value += node.pointCount;
      statusText.value = loadedNodes.value === totalNodes.value ? "点云加载完成" : "正在渐进加载点云";
      await waitForFrame();
    }
  } catch (error) {
    if (abortController.signal.aborted) {
      return;
    }
    errorText.value = error instanceof Error ? error.message : String(error);
    statusText.value = "点云加载失败";
  }
}

function initializeScene(): void {
  const viewport = viewportRef.value;
  if (!viewport) {
    return;
  }

  disposeScene();
  scene = new THREE.Scene();
  scene.background = new THREE.Color("#0b1717");

  camera = new THREE.PerspectiveCamera(50, 1, 0.1, 5000);
  camera.up.set(0, 0, 1);

  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  viewport.appendChild(renderer.domElement);

  pointGroup = new THREE.Group();
  scene.add(pointGroup);
  scene.add(new THREE.AxesHelper(18));

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = false;
  controls.target.set(0, 0, 0);

  resizeObserver = new ResizeObserver(resizeRenderer);
  resizeObserver.observe(viewport);
  resizeRenderer();
  animate();
}

async function loadNode(baseUrl: string, node: PotreeNode, signal: AbortSignal): Promise<void> {
  if (!pointGroup) {
    return;
  }

  const response = await fetch(resolveUrl(baseUrl, node.url), { signal });
  if (!response.ok) {
    throw new Error(`Failed to load point cloud node ${node.id}: ${response.status}`);
  }

  const buffer = await response.arrayBuffer();
  const pointCount = Math.floor(buffer.byteLength / 16);
  const positions = new Float32Array(pointCount * 3);
  const colors = new Uint8Array(pointCount * 3);
  const view = new DataView(buffer);

  for (let index = 0; index < pointCount; index += 1) {
    const sourceOffset = index * 16;
    const targetOffset = index * 3;
    positions[targetOffset] = view.getFloat32(sourceOffset, true);
    positions[targetOffset + 1] = view.getFloat32(sourceOffset + 4, true);
    positions[targetOffset + 2] = view.getFloat32(sourceOffset + 8, true);

    const rgb = view.getUint32(sourceOffset + 12, true);
    colors[targetOffset] = (rgb >> 16) & 255;
    colors[targetOffset + 1] = (rgb >> 8) & 255;
    colors[targetOffset + 2] = rgb & 255;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3, true));
  geometry.computeBoundingSphere();

  const material = new THREE.PointsMaterial({
    size: 0.34,
    sizeAttenuation: true,
    vertexColors: true,
  });
  material.toneMapped = false;

  const points = new THREE.Points(geometry, material);
  points.name = `pointcloud-node-${node.id}`;
  pointGroup.add(points);
}

function fitCameraToBounds(min: [number, number, number], max: [number, number, number]): void {
  if (!camera || !controls || !pointGroup) {
    return;
  }

  const minVector = new THREE.Vector3(min[0], min[1], min[2]);
  const maxVector = new THREE.Vector3(max[0], max[1], max[2]);
  const center = new THREE.Vector3().addVectors(minVector, maxVector).multiplyScalar(0.5);
  const size = new THREE.Vector3().subVectors(maxVector, minVector);
  const radius = Math.max(size.length() * 0.5, 1);

  pointGroup.position.set(-center.x, -center.y, -center.z);
  camera.near = Math.max(radius / 1000, 0.01);
  camera.far = radius * 10;
  camera.position.set(radius * 1.15, -radius * 1.35, radius * 0.82);
  camera.lookAt(0, 0, 0);
  camera.updateProjectionMatrix();

  controls.target.set(0, 0, 0);
  controls.update();
}

function resetCameraView(): void {
  if (currentManifest) {
    fitCameraToBounds(currentManifest.bounds.min, currentManifest.bounds.max);
  }
}

function reloadPointCloud(): void {
  if (props.baseUrl) {
    void loadPointCloud(props.baseUrl);
  }
}

function resizeRenderer(): void {
  const viewport = viewportRef.value;
  if (!viewport || !renderer || !camera) {
    return;
  }

  const width = Math.max(viewport.clientWidth, 1);
  const height = Math.max(viewport.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate(): void {
  if (!renderer || !scene || !camera) {
    return;
  }

  animationFrame = window.requestAnimationFrame(animate);
  controls?.update();
  renderer.render(scene, camera);
}

function disposeScene(): void {
  if (animationFrame) {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = 0;
  }

  resizeObserver?.disconnect();
  resizeObserver = null;

  pointGroup?.traverse((object) => {
    if (object instanceof THREE.Points) {
      object.geometry.dispose();
      const material = object.material;
      if (Array.isArray(material)) {
        material.forEach((item) => item.dispose());
      } else {
        material.dispose();
      }
    }
  });

  renderer?.dispose();
  renderer?.domElement.remove();
  renderer = null;
  scene = null;
  camera = null;
  controls = null;
  pointGroup = null;
}

function resolveUrl(baseUrl: string, path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${baseUrl}${path}`;
}

function waitForFrame(): Promise<void> {
  return new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}
</script>

<template>
  <div class="pointcloud-viewer">
    <div ref="viewportRef" class="pointcloud-viewport"></div>

    <div class="pointcloud-hud">
      <span>{{ statusText }}</span>
      <strong>{{ formatCount(loadedPoints) }} / {{ formatCount(totalVisiblePoints) }} 点</strong>
      <small>原始点数 {{ formatCount(sourcePoints) }}，节点 {{ loadedNodes }} / {{ totalNodes }}</small>
    </div>

    <div class="pointcloud-tools">
      <button type="button" @click="resetCameraView">重置视角</button>
      <button type="button" @click="reloadPointCloud">重新加载</button>
    </div>

    <div v-if="errorText" class="pointcloud-error">
      <strong>点云加载失败</strong>
      <span>{{ errorText }}</span>
    </div>
  </div>
</template>
