export interface CelestialBodyData {
  id: string;
  name: string;
  nickname: string;
  description: string;
  radius: number; // 3D 场景中的半径
  realRadius: string; // 显示用的趣味半径
  distance: number; // 轨道半径
  speed: number; // 基础轨道速度
  tilt: number; // 轨道倾斜角 (弧度)
  material: {
    type: 'metal' | 'ceramic' | 'copper' | 'glass' | 'wood' | 'enamel' | 'brushed' | 'polished';
    color: string;
    roughness: number;
    metalness: number;
    transparent?: boolean;
    opacity?: number;
    emissive?: string;
    emissiveIntensity?: number;
  };
  hasRing?: boolean;
  moons?: { name: string; distance: number; speed: number; radius: number }[];
}

export const CELESTIAL_BODIES: CelestialBodyData[] = [
  {
    id: 'overtime',
    name: '加班星',
    nickname: 'Overtime',
    description: '永远跑得最快的社畜之星，24小时不停转，但 nobody cares',
    radius: 0.18,
    realRadius: '0.3 根头发丝的直径',
    distance: 1.8,
    speed: 2.5,
    tilt: 0.15,
    material: {
      type: 'brushed',
      color: '#8C9A9E',
      roughness: 0.6,
      metalness: 0.9,
    },
  },
  {
    id: 'slack',
    name: '摸鱼星',
    nickname: 'Slack',
    description: '转得比乌龟还慢，表面平静如镜，内心已经在想晚上吃啥',
    radius: 0.35,
    realRadius: '0.8 个键盘按键',
    distance: 2.6,
    speed: 0.4,
    tilt: -0.2,
    material: {
      type: 'ceramic',
      color: '#4ECDC4',
      roughness: 0.15,
      metalness: 0.0,
    },
    moons: [
      { name: '微博卫星', distance: 0.55, speed: 3.0, radius: 0.08 },
    ],
  },
  {
    id: 'coffee',
    name: '咖啡星',
    nickname: 'Coffee',
    description: '程序员的生命之源，表面温度常年保持在 65°C（烫嘴但还是要喝）',
    radius: 0.28,
    realRadius: '1.2 个咖啡杯底',
    distance: 3.4,
    speed: 0.8,
    tilt: 0.1,
    material: {
      type: 'copper',
      color: '#B87333',
      roughness: 0.3,
      metalness: 1.0,
    },
  },
  {
    id: 'buggy',
    name: 'Bug 星',
    nickname: 'Buggy',
    description: '透明的红色玻璃球，里面似乎有无数小虫子在爬。你盯着它看，它也在盯着你',
    radius: 0.22,
    realRadius: '0.5 个报错弹窗',
    distance: 4.2,
    speed: 1.2,
    tilt: -0.35,
    material: {
      type: 'glass',
      color: '#FF4757',
      roughness: 0.0,
      metalness: 0.1,
      transparent: true,
      opacity: 0.75,
    },
  },
  {
    id: 'bald',
    name: '脱发星',
    nickname: 'Bald',
    description: '木纹质感的温柔星球，每转一圈就少几根木纹——别看了，说的就是你',
    radius: 0.45,
    realRadius: '3.14 个脱发面积单位',
    distance: 5.2,
    speed: 0.5,
    tilt: 0.25,
    material: {
      type: 'wood',
      color: '#8B6F47',
      roughness: 0.9,
      metalness: 0.0,
    },
  },
  {
    id: 'blessing',
    name: '福报星',
    nickname: 'Blessing',
    description: '金光闪闪的珐琅大球，996 的终极奖励。表面刻着看不见的"奋斗"二字',
    radius: 0.55,
    realRadius: '9.9 个福报值',
    distance: 6.4,
    speed: 0.25,
    tilt: -0.15,
    material: {
      type: 'enamel',
      color: '#FFD700',
      roughness: 0.1,
      metalness: 0.3,
      emissive: '#FFD700',
      emissiveIntensity: 0.15,
    },
    hasRing: true,
  },
  {
    id: 'kpi',
    name: 'KPI 星',
    nickname: 'KPI',
    description: '银色冷面杀手，转速精确到小数点后三位，完不成指标就给你颜色看',
    radius: 0.3,
    realRadius: '100% 达成率（理论上）',
    distance: 7.6,
    speed: 0.6,
    tilt: 0.4,
    material: {
      type: 'metal',
      color: '#C0C0C0',
      roughness: 0.2,
      metalness: 1.0,
    },
  },
  {
    id: 'deadline',
    name: 'Deadline',
    nickname: 'DDL',
    description: '黑色抛光金属球，表面光滑如镜，能照出你熬夜的黑眼圈。它不会说话，但它一直在逼近',
    radius: 0.38,
    realRadius: '23:59 之前的最后 1 分钟',
    distance: 8.8,
    speed: 1.8,
    tilt: -0.3,
    material: {
      type: 'polished',
      color: '#1A1A2E',
      roughness: 0.05,
      metalness: 1.0,
    },
  },
];

export const CENTER_LIGHT = {
  name: '老板之眼',
  nickname: 'The Eye',
  description: '金色的全视之眼，它不说话，但总觉得它在看你是不是在摸鱼',
  color: '#FFD700',
  intensity: 2.5,
};

// 轨道环材质
export const ORBIT_RING_MATERIAL = {
  color: '#C9A961',
  roughness: 0.4,
  metalness: 0.8,
};

// 底座材质
export const BASE_MATERIAL = {
  color: '#3D2B1F',
  roughness: 0.8,
  metalness: 0.1,
};

// 齿轮材质
export const GEAR_MATERIAL = {
  color: '#B8A88A',
  roughness: 0.3,
  metalness: 0.9,
};
