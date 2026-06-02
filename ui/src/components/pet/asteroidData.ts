export interface AsteroidMorph {
  id: string;
  name: string;
  description: string;
  // 几何参数
  noiseSeed: number;
  noiseFreq: number;
  noiseAmp: number;
  icoDetail: number;
  // 外观
  baseColor: string;
  secondaryColor: string;
  crackColor: string;
  emissiveIntensity: number;
  roughness: number;
  metalness: number;
  // 碎片
  debrisCount: number;
  debrisColor: string;
  // 推进器
  hasThruster: boolean;
  thrusterColor: string;
  // 主题标识
  theme: 'industrial' | 'volcanic' | 'crystal' | 'ice' | 'corrupted';
}

export const ASTEROID_MORPHS: AsteroidMorph[] = [
  {
    id: 'rocky',
    name: '陨石核心',
    description: '编号 AST-001 的深空探测器，表面布满铆钉和焊接缝',
    noiseSeed: 42,
    noiseFreq: 1.5,
    noiseAmp: 0.35,
    icoDetail: 3,
    baseColor: '#5A5A6E',
    secondaryColor: '#3A3A4E',
    crackColor: '#00D4AA',
    emissiveIntensity: 0.8,
    roughness: 0.9,
    metalness: 0.1,
    debrisCount: 4,
    debrisColor: '#6A6A7E',
    hasThruster: true,
    thrusterColor: '#00D4AA',
    theme: 'industrial',
  },
  {
    id: 'magma',
    name: '熔岩之心',
    description: '活体火山天体，岩浆管在表面脉动，随时可能喷发',
    noiseSeed: 13,
    noiseFreq: 1.2,
    noiseAmp: 0.25,
    icoDetail: 4,
    baseColor: '#2D1B1B',
    secondaryColor: '#1A0F0F',
    crackColor: '#FF6B35',
    emissiveIntensity: 2.5,
    roughness: 0.7,
    metalness: 0.3,
    debrisCount: 6,
    debrisColor: '#FF8C42',
    hasThruster: true,
    thrusterColor: '#FF6B35',
    theme: 'volcanic',
  },
  {
    id: 'crystal',
    name: '水晶晶核',
    description: '远古文明留下的能量晶体，表面刻有发光的符文',
    noiseSeed: 88,
    noiseFreq: 2.0,
    noiseAmp: 0.15,
    icoDetail: 4,
    baseColor: '#1A1A3E',
    secondaryColor: '#0F0F2A',
    crackColor: '#C084FC',
    emissiveIntensity: 1.5,
    roughness: 0.1,
    metalness: 0.0,
    debrisCount: 3,
    debrisColor: '#A855F7',
    hasThruster: false,
    thrusterColor: '#C084FC',
    theme: 'crystal',
  },
  {
    id: 'ice',
    name: '永冻彗星',
    description: '来自奥尔特云的冰封幽灵，彗尾如丝绸般飘逸',
    noiseSeed: 77,
    noiseFreq: 1.8,
    noiseAmp: 0.2,
    icoDetail: 3,
    baseColor: '#2A3A4A',
    secondaryColor: '#1A2A3A',
    crackColor: '#00F0FF',
    emissiveIntensity: 1.2,
    roughness: 0.3,
    metalness: 0.1,
    debrisCount: 5,
    debrisColor: '#67E8F9',
    hasThruster: false,
    thrusterColor: '#00F0FF',
    theme: 'ice',
  },
  {
    id: 'dark',
    name: '暗物质球',
    description: 'ERROR: 数据损坏。请勿直视。请勿交互。',
    noiseSeed: 66,
    noiseFreq: 0.8,
    noiseAmp: 0.4,
    icoDetail: 2,
    baseColor: '#0A0A1A',
    secondaryColor: '#050510',
    crackColor: '#FF0055',
    emissiveIntensity: 3.0,
    roughness: 0.95,
    metalness: 0.0,
    debrisCount: 2,
    debrisColor: '#1A1A2E',
    hasThruster: false,
    thrusterColor: '#FF0055',
    theme: 'corrupted',
  },
];

// 简单的伪随机噪声函数（基于种子）
export function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// 3D Simplex-like noise (simplified for vertex displacement)
export function simpleNoise(x: number, y: number, z: number, seed: number): number {
  const rand = seededRandom(seed);
  let value = 0;
  let amplitude = 1;
  let frequency = 1;
  let maxValue = 0;

  for (let i = 0; i < 4; i++) {
    const nx = x * frequency;
    const ny = y * frequency;
    const nz = z * frequency;
    const ix = Math.floor(nx);
    const iy = Math.floor(ny);
    const iz = Math.floor(nz);
    const fx = nx - ix;
    const fy = ny - iy;
    const fz = nz - iz;
    const sx = fx * fx * (3 - 2 * fx);
    const sy = fy * fy * (3 - 2 * fy);
    const sz = fz * fz * (3 - 2 * fz);

    const c000 = rand();
    const c001 = rand();
    const c010 = rand();
    const c011 = rand();
    const c100 = rand();
    const c101 = rand();
    const c110 = rand();
    const c111 = rand();

    const v00 = c000 * (1 - sx) + c100 * sx;
    const v01 = c001 * (1 - sx) + c101 * sx;
    const v10 = c010 * (1 - sx) + c110 * sx;
    const v11 = c011 * (1 - sx) + c111 * sx;
    const v0 = v00 * (1 - sy) + v10 * sy;
    const v1 = v01 * (1 - sy) + v11 * sy;

    value += (v0 * (1 - sz) + v1 * sz - 0.5) * amplitude;
    maxValue += amplitude;
    amplitude *= 0.5;
    frequency *= 2;
  }

  return value / maxValue;
}

// 生成裂缝纹理 (Canvas-based)
export function generateCrackTexture(
  color: string,
  intensity: number,
  seed: number
): HTMLCanvasElement {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const rand = seededRandom(seed);

  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, size, size);

  // 主题化裂缝图案
  ctx.strokeStyle = color;
  ctx.lineCap = 'round';

  if (seed % 5 === 0) {
    // 工业主题：规整的网格线
    const gridSize = 64;
    for (let x = 0; x < size; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, size);
      ctx.lineWidth = 1 * intensity;
      ctx.globalAlpha = 0.2;
      ctx.stroke();
    }
    for (let y = 0; y < size; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size, y);
      ctx.lineWidth = 1 * intensity;
      ctx.globalAlpha = 0.2;
      ctx.stroke();
    }
  }

  // 主裂缝
  const numCracks = 8 + Math.floor(rand() * 12);
  for (let i = 0; i < numCracks; i++) {
    const startX = rand() * size;
    const startY = rand() * size;
    const segments = 3 + Math.floor(rand() * 5);

    ctx.beginPath();
    ctx.moveTo(startX, startY);

    let cx = startX;
    let cy = startY;
    for (let j = 0; j < segments; j++) {
      cx += (rand() - 0.5) * size * 0.3;
      cy += (rand() - 0.5) * size * 0.3;
      ctx.lineTo(cx, cy);
    }

    ctx.lineWidth = (1 + rand() * 3) * intensity;
    ctx.globalAlpha = 0.3 + rand() * 0.7;
    ctx.stroke();

    if (rand() > 0.5) {
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + (rand() - 0.5) * 80, cy + (rand() - 0.5) * 80);
      ctx.lineWidth = 1 * intensity;
      ctx.globalAlpha = 0.2 + rand() * 0.3;
      ctx.stroke();
    }
  }

  // Glow spots
  const numSpots = 5 + Math.floor(rand() * 8);
  for (let i = 0; i < numSpots; i++) {
    const sx = rand() * size;
    const sy = rand() * size;
    const sr = 5 + rand() * 20;
    const gradient = ctx.createRadialGradient(sx, sy, 0, sx, sy, sr);
    gradient.addColorStop(0, color + '80');
    gradient.addColorStop(1, 'transparent');
    ctx.fillStyle = gradient;
    ctx.globalAlpha = 0.5 + rand() * 0.5;
    ctx.beginPath();
    ctx.arc(sx, sy, sr, 0, Math.PI * 2);
    ctx.fill();
  }

  // 腐败主题：添加错误文字
  if (seed % 5 === 1) {
    ctx.font = '20px monospace';
    ctx.fillStyle = '#FF0055';
    ctx.globalAlpha = 0.3;
    ctx.fillText('ERROR', rand() * size * 0.8, rand() * size);
    ctx.fillText('CORRUPTED', rand() * size * 0.7, rand() * size);
  }

  return canvas;
}
