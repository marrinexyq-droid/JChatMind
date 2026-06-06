export interface CelestialBodyData {
  id: string;
  name: string;
  nickname: string;
  description: string;
  radius: number;
  realRadius: string;
  distance: number;
  speed: number;
  tilt: number;
  material: {
    type: "metal" | "ceramic" | "copper" | "glass" | "wood" | "enamel" | "brushed" | "polished";
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
    id: "planning",
    name: "Planner",
    nickname: "Route Mapper",
    description: "Maps the next answer into a workable plan before the model starts moving.",
    radius: 0.34,
    realRadius: "AI_PLANNING phase",
    distance: 2.2,
    speed: 0.55,
    tilt: 0.12,
    material: { type: "enamel", color: "#FFD700", roughness: 0.1, metalness: 0.25, emissive: "#FFD700", emissiveIntensity: 0.2 },
    hasRing: true,
  },
  {
    id: "thinking",
    name: "Cogito",
    nickname: "Reasoning Ring",
    description: "The reasoning lane where the active answer is shaped.",
    radius: 0.42,
    realRadius: "AI_THINKING phase",
    distance: 3.35,
    speed: 0.8,
    tilt: -0.2,
    material: { type: "glass", color: "#00D4AA", roughness: 0.05, metalness: 0.1, transparent: true, opacity: 0.78, emissive: "#00D4AA", emissiveIntensity: 0.15 },
  },
  {
    id: "executing",
    name: "Executor",
    nickname: "Tool Planet",
    description: "Lights up when the backend is executing tools or returning tool data.",
    radius: 0.36,
    realRadius: "AI_EXECUTING phase",
    distance: 4.6,
    speed: 1.05,
    tilt: 0.28,
    material: { type: "brushed", color: "#00B4FF", roughness: 0.35, metalness: 0.9, emissive: "#00B4FF", emissiveIntensity: 0.12 },
    moons: [{ name: "Tool Result", distance: 0.62, speed: 2.4, radius: 0.08 }],
  },
  {
    id: "streaming",
    name: "Responsum",
    nickname: "Answer Beam",
    description: "The output lane that grows as streaming chunks arrive.",
    radius: 0.46,
    realRadius: "AI_STREAMING_CHUNK phase",
    distance: 5.85,
    speed: 0.65,
    tilt: -0.34,
    material: { type: "ceramic", color: "#FF3366", roughness: 0.16, metalness: 0.05, emissive: "#FF3366", emissiveIntensity: 0.18 },
  },
  {
    id: "done",
    name: "Archive",
    nickname: "Done Node",
    description: "The pipeline settles here when the answer is complete.",
    radius: 0.38,
    realRadius: "AI_DONE or final chunk",
    distance: 7.1,
    speed: 0.32,
    tilt: 0.4,
    material: { type: "metal", color: "#C084FC", roughness: 0.18, metalness: 0.8, emissive: "#C084FC", emissiveIntensity: 0.08 },
  },
];

export const CENTER_LIGHT = {
  name: "Solvo",
  nickname: "Pipeline Core",
  description: "The shared chat pipeline state projected into the planetarium.",
  color: "#FFD700",
  intensity: 2.5,
};

export const ORBIT_RING_MATERIAL = {
  color: "#C9A961",
  roughness: 0.4,
  metalness: 0.8,
};

export const BASE_MATERIAL = {
  color: "#3D2B1F",
  roughness: 0.8,
  metalness: 0.1,
};

export const GEAR_MATERIAL = {
  color: "#B8A88A",
  roughness: 0.3,
  metalness: 0.9,
};
