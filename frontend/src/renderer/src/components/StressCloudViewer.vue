<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { getStressCloud, type StressCloud } from "../services/api";

const props = defineProps<{
  baseUrl: string;
  taskId?: string;
}>();

const viewportRef = ref<HTMLDivElement | null>(null);
const statusText = ref("等待后端服务");
const errorText = ref("");
const elementCount = ref(0);
const maxStressText = ref("--");
const maxElementText = ref("--");

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.PerspectiveCamera | null = null;
let controls: OrbitControls | null = null;
let lineSegments: THREE.LineSegments | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationFrame = 0;
let abortController: AbortController | null = null;

watch(
  () => [props.baseUrl, props.taskId] as const,
  ([baseUrl, taskId]) => {
    if (!baseUrl) {
      statusText.value = "等待后端服务";
      return;
    }
    void loadStressCloud(baseUrl, taskId);
  },
  { immediate: true, flush: "post" },
);

onBeforeUnmount(() => {
  abortController?.abort();
  disposeScene();
});

async function loadStressCloud(baseUrl: string, taskId?: string): Promise<void> {
  abortController?.abort();
  abortController = new AbortController();
  statusText.value = taskId ? "正在读取风险 h5" : "正在读取 base h5";
  errorText.value = "";

  await nextTick();
  initializeScene();

  try {
    const cloud = await getStressCloud(baseUrl, taskId, abortController.signal);
    renderCloud(cloud);
    elementCount.value = cloud.elements.length;
    maxStressText.value = formatStress(cloud.max_stress.value);
    maxElementText.value = cloud.max_stress.element_label ? String(cloud.max_stress.element_label) : "--";
    statusText.value = "base 应力云图";
  } catch (error) {
    if (abortController.signal.aborted) {
      return;
    }
    errorText.value = error instanceof Error ? error.message : String(error);
    statusText.value = "应力云图加载失败";
  }
}

function initializeScene(): void {
  const viewport = viewportRef.value;
  if (!viewport) {
    return;
  }

  disposeScene();
  scene = new THREE.Scene();
  scene.background = new THREE.Color("#f7fbfa");

  camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
  camera.up.set(0, 0, 1);

  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  viewport.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight("#ffffff", 1));

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = false;

  resizeObserver = new ResizeObserver(resizeRenderer);
  resizeObserver.observe(viewport);
  resizeRenderer();
  animate();
}

function renderCloud(cloud: StressCloud): void {
  if (!scene || !camera || !controls) {
    return;
  }

  lineSegments?.geometry.dispose();
  const material = lineSegments?.material;
  if (material instanceof THREE.Material) {
    material.dispose();
  }
  if (lineSegments) {
    scene.remove(lineSegments);
  }

  const center = new THREE.Vector3(
    (cloud.bounds.min[0] + cloud.bounds.max[0]) / 2,
    (cloud.bounds.min[1] + cloud.bounds.max[1]) / 2,
    (cloud.bounds.min[2] + cloud.bounds.max[2]) / 2,
  );
  const positions = new Float32Array(cloud.elements.length * 2 * 3);
  const colors = new Float32Array(cloud.elements.length * 2 * 3);

  for (let index = 0; index < cloud.elements.length; index += 1) {
    const [startIndex, endIndex] = cloud.elements[index];
    const start = cloud.nodes[startIndex];
    const end = cloud.nodes[endIndex];
    const stress = cloud.stress.values[index] ?? 0;
    const color = stressToColor(stress, cloud.stress.min, cloud.stress.max);
    writePosition(positions, index * 6, start, center);
    writePosition(positions, index * 6 + 3, end, center);
    writeColor(colors, index * 6, color);
    writeColor(colors, index * 6 + 3, color);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geometry.computeBoundingSphere();

  const lineMaterial = new THREE.LineBasicMaterial({ vertexColors: true });
  lineSegments = new THREE.LineSegments(geometry, lineMaterial);
  scene.add(lineSegments);

  const min = new THREE.Vector3(...cloud.bounds.min);
  const max = new THREE.Vector3(...cloud.bounds.max);
  const size = new THREE.Vector3().subVectors(max, min);
  const radius = Math.max(size.length() * 0.5, 1);
  camera.near = Math.max(radius / 1000, 0.01);
  camera.far = radius * 20;
  camera.position.set(radius * 0.9, -radius * 1.55, radius * 0.86);
  camera.lookAt(0, 0, 0);
  camera.updateProjectionMatrix();
  controls.target.set(0, 0, 0);
  controls.update();
}

function writePosition(target: Float32Array, offset: number, point: [number, number, number], center: THREE.Vector3): void {
  target[offset] = point[0] - center.x;
  target[offset + 1] = point[1] - center.y;
  target[offset + 2] = point[2] - center.z;
}

function writeColor(target: Float32Array, offset: number, color: THREE.Color): void {
  target[offset] = color.r;
  target[offset + 1] = color.g;
  target[offset + 2] = color.b;
}

function stressToColor(value: number, min: number, max: number): THREE.Color {
  const t = max <= min ? 0 : Math.min(1, Math.max(0, (value - min) / (max - min)));
  const stops = [
    new THREE.Color("#2b6cb0"),
    new THREE.Color("#22c7a9"),
    new THREE.Color("#f2c94c"),
    new THREE.Color("#d94f45"),
  ];
  if (t < 1 / 3) {
    return stops[0].clone().lerp(stops[1], t * 3);
  }
  if (t < 2 / 3) {
    return stops[1].clone().lerp(stops[2], (t - 1 / 3) * 3);
  }
  return stops[2].clone().lerp(stops[3], (t - 2 / 3) * 3);
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

  lineSegments?.geometry.dispose();
  const material = lineSegments?.material;
  if (material instanceof THREE.Material) {
    material.dispose();
  }
  renderer?.dispose();
  renderer?.domElement.remove();

  renderer = null;
  scene = null;
  camera = null;
  controls = null;
  lineSegments = null;
}

function formatStress(value: number): string {
  if (!Number.isFinite(value)) {
    return "--";
  }
  return `${(value / 1_000_000).toFixed(2)} MPa`;
}
</script>

<template>
  <div class="stress-cloud-viewer">
    <div ref="viewportRef" class="stress-cloud-viewport"></div>

    <div class="stress-cloud-hud">
      <span>{{ statusText }}</span>
      <strong>{{ maxStressText }}</strong>
      <small>杆件 {{ elementCount }}，最大应力单元 {{ maxElementText }}</small>
    </div>

    <div class="stress-cloud-legend">
      <span>低</span>
      <div></div>
      <span>高</span>
    </div>

    <div v-if="errorText" class="stress-cloud-error">
      <strong>云图加载失败</strong>
      <span>{{ errorText }}</span>
    </div>
  </div>
</template>
