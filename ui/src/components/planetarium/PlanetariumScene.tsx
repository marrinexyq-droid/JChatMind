import { useCallback, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import type { ThreeEvent } from "@react-three/fiber";
import { Html, OrbitControls, Sphere, Text } from "@react-three/drei";
import * as THREE from "three";
import { CENTER_LIGHT, CELESTIAL_BODIES, type CelestialBodyData } from "./data";
import type { UniversePipelineState, UniverseReasoningState } from "../../types";

function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function stablePhase(value: string) {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return (hash % 10000) / 10000 * Math.PI * 2;
}

function StarField() {
  const count = 1800;
  const points = useMemo(() => {
    const rand = seededRandom(42);
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const r = 18 + rand() * 40;
      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(2 * rand() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      const warm = rand() > 0.75;
      colors[i * 3] = warm ? 1 : 0.72 + rand() * 0.24;
      colors[i * 3 + 1] = warm ? 0.68 + rand() * 0.2 : 0.86 + rand() * 0.14;
      colors[i * 3 + 2] = warm ? 0.72 : 1;
    }
    return { positions, colors };
  }, []);

  const pointsRef = useRef<THREE.Points>(null);
  useFrame((state) => {
    if (!pointsRef.current) return;
    pointsRef.current.rotation.y = state.clock.elapsedTime * 0.004;
    pointsRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.0015) * 0.04;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[points.positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[points.colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.07} vertexColors transparent opacity={0.9} sizeAttenuation depthWrite={false} />
    </points>
  );
}

function NebulaCloud() {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (meshRef.current) meshRef.current.rotation.z = state.clock.elapsedTime * 0.01;
  });

  return (
    <group>
      <mesh ref={meshRef} position={[0, 0, -25]} rotation={[0, 0, 0.3]}>
        <planeGeometry args={[64, 64]} />
        <meshBasicMaterial color="#17092f" transparent opacity={0.34} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <mesh position={[-13, 7, -22]} rotation={[0.2, 0.5, 0]}>
        <planeGeometry args={[40, 28]} />
        <meshBasicMaterial color="#071d2f" transparent opacity={0.28} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <mesh position={[13, -5, -24]} rotation={[-0.1, -0.3, 0.2]}>
        <planeGeometry args={[36, 34]} />
        <meshBasicMaterial color="#2f081a" transparent opacity={0.22} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}

const phaseBodyId: Partial<Record<UniverseReasoningState, string>> = {
  planning: "planning",
  thinking: "thinking",
  executing: "executing",
  streaming: "streaming",
  done: "done",
};

function bodyActivity(data: CelestialBodyData, pipeline: UniversePipelineState) {
  const activeId = phaseBodyId[pipeline.reasoningState];
  if (data.id === activeId) return 1;
  if (pipeline.reasoningState === "executing" && data.id === "thinking") return 0.45;
  if (pipeline.reasoningState === "streaming" && data.id === "done") return 0.35;
  return 0;
}

function createMaterial(mat: CelestialBodyData["material"], activity: number) {
  const emissive = activity > 0 ? mat.color : mat.emissive ?? "#000000";
  const emissiveIntensity = (mat.emissiveIntensity ?? 0) + activity * 1.5;
  const props = {
    color: mat.color,
    roughness: mat.roughness,
    metalness: mat.metalness,
    transparent: mat.transparent ?? false,
    opacity: mat.opacity ?? 1,
    emissive,
    emissiveIntensity,
  };

  if (mat.type === "glass") {
    return <meshPhysicalMaterial {...props} transmission={0.45} thickness={0.5} ior={1.5} clearcoat={1} clearcoatRoughness={0.1} />;
  }
  if (mat.type === "ceramic" || mat.type === "enamel") {
    return <meshPhysicalMaterial {...props} clearcoat={1} clearcoatRoughness={0.08} />;
  }
  return <meshStandardMaterial {...props} />;
}

function OrbitRing({ radius, tilt, color, active }: { radius: number; tilt: number; color: string; active: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.z = state.clock.elapsedTime * (0.02 + active * 0.18);
  });

  return (
    <mesh ref={ref} rotation={[tilt, 0, 0]}>
      <torusGeometry args={[radius, active > 0 ? 0.026 : 0.012, 8, 128]} />
      <meshBasicMaterial color={color} transparent opacity={0.18 + active * 0.55} />
    </mesh>
  );
}

function PipelineFlow({ pipeline }: { pipeline: UniversePipelineState }) {
  const groupRef = useRef<THREE.Group>(null);
  const active = pipeline.reasoningState !== "idle";
  const color = pipeline.reasoningState === "streaming" ? "#FF3366" : pipeline.reasoningState === "executing" ? "#00B4FF" : "#00D4AA";
  const distance = pipeline.reasoningState === "streaming" ? 6.7 : pipeline.reasoningState === "executing" ? 4.6 : 3.2;

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;
    groupRef.current.children.forEach((child, i) => {
      const progress = (t * (0.35 + i * 0.04) + i * 0.18) % 1;
      child.position.set(Math.cos(progress * Math.PI * 2) * distance, Math.sin(progress * Math.PI) * 0.7, Math.sin(progress * Math.PI * 2) * distance);
      child.scale.setScalar(0.7 + Math.sin(t * 4 + i) * 0.25);
    });
  });

  if (!active) return null;

  return (
    <group ref={groupRef}>
      {Array.from({ length: pipeline.reasoningState === "streaming" ? 9 : 5 }, (_, i) => (
        <mesh key={i}>
          <sphereGeometry args={[0.055, 12, 12]} />
          <meshBasicMaterial color={color} transparent opacity={0.78} />
        </mesh>
      ))}
    </group>
  );
}

function CyberCore({ pipeline, onClick }: { pipeline: UniversePipelineState; onClick: () => void }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const load = pipeline.reasoningState === "idle" ? 0 : pipeline.reasoningState === "done" ? 0.4 : 1;

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (meshRef.current) {
      meshRef.current.rotation.y = t * (0.2 + load * 0.25);
      meshRef.current.rotation.x = Math.sin(t * 0.3) * 0.1;
    }
    if (glowRef.current) glowRef.current.scale.setScalar(1 + Math.sin(t * (2.4 + load * 4)) * (0.07 + load * 0.07));
    if (ringRef.current) ringRef.current.rotation.z = t * (0.18 + load * 0.65);
  });

  return (
    <group onClick={onClick}>
      <Sphere ref={meshRef} args={[0.5, 40, 40]}>
        <meshStandardMaterial color={CENTER_LIGHT.color} emissive={CENTER_LIGHT.color} emissiveIntensity={3 + load * 2.5} roughness={0.1} metalness={0.9} />
      </Sphere>
      <Sphere ref={glowRef} args={[0.9 + load * 0.12, 32, 32]}>
        <meshBasicMaterial color={pipeline.reasoningState === "error" ? "#FF3366" : "#FF6B00"} transparent opacity={0.12 + load * 0.1} />
      </Sphere>
      <mesh ref={ringRef}>
        <torusGeometry args={[1.0, 0.025 + load * 0.015, 8, 96]} />
        <meshBasicMaterial color={pipeline.reasoningState === "streaming" ? "#FF3366" : "#FFD700"} transparent opacity={0.55 + load * 0.28} />
      </mesh>
      <pointLight color="#FFD700" intensity={4 + load * 4} distance={25} decay={2} />
      <pointLight color="#00D4AA" intensity={0.4 + load * 1.5} distance={22} decay={2} />
    </group>
  );
}

function CelestialBody({
  data,
  timeSpeed,
  onSelect,
  isSelected,
  activity,
}: {
  data: CelestialBodyData;
  timeSpeed: number;
  onSelect: (body: CelestialBodyData | null) => void;
  isSelected: boolean;
  activity: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const bodyRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const angleRef = useRef(stablePhase(data.id));

  useFrame((state, delta) => {
    angleRef.current += data.speed * (timeSpeed + activity * 1.6) * delta * 0.35;
    if (groupRef.current) {
      groupRef.current.position.set(Math.cos(angleRef.current) * data.distance, Math.sin(angleRef.current * 0.8) * 0.15, Math.sin(angleRef.current) * data.distance);
      const pulse = 1 + Math.sin(state.clock.elapsedTime * (3 + activity * 5)) * activity * 0.12;
      groupRef.current.scale.setScalar(pulse);
    }
    if (bodyRef.current) bodyRef.current.rotation.y += delta * (0.55 + activity * 1.8);
    if (glowRef.current) glowRef.current.scale.setScalar(1.08 + Math.sin(state.clock.elapsedTime * 4) * (0.06 + activity * 0.12));
  });

  const handleClick = useCallback((event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(data);
  }, [data, onSelect]);

  const glowOpacity = 0.08 + activity * 0.28 + (isSelected ? 0.12 : 0);

  return (
    <group ref={groupRef} onClick={handleClick}>
      <Sphere ref={bodyRef} args={[data.radius, 32, 32]}>
        {createMaterial(data.material, activity)}
      </Sphere>
      <Sphere ref={glowRef} args={[data.radius * (1.35 + activity * 0.7), 32, 32]}>
        <meshBasicMaterial color={data.material.color} transparent opacity={glowOpacity} />
      </Sphere>
      {(isSelected || activity > 0.2) && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[data.radius * 1.7, 0.018, 8, 64]} />
          <meshBasicMaterial color={data.material.color} transparent opacity={0.4 + activity * 0.35} />
        </mesh>
      )}
      {data.moons?.map((moon, index) => (
        <Moon key={index} data={moon} timeSpeed={timeSpeed + activity} />
      ))}
      <Text position={[0, data.radius + 0.58, 0]} fontSize={0.2} color={activity > 0 ? data.material.color : "#E0E0E0"} anchorX="center" anchorY="middle" outlineWidth={0.01} outlineColor="#000000">
        {data.name}
      </Text>
    </group>
  );
}

function Moon({ data, timeSpeed }: { data: { distance: number; speed: number; radius: number }; timeSpeed: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const angleRef = useRef(stablePhase(`${data.distance}-${data.speed}-${data.radius}`));
  useFrame((_, delta) => {
    angleRef.current += data.speed * timeSpeed * delta * 0.45;
    if (ref.current) ref.current.position.set(Math.cos(angleRef.current) * data.distance, 0, Math.sin(angleRef.current) * data.distance);
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[data.radius, 16, 16]} />
      <meshStandardMaterial color="#6080A0" emissive="#405070" emissiveIntensity={0.3} roughness={0.6} metalness={0.5} />
    </mesh>
  );
}

function DoneBurst({ pipeline }: { pipeline: UniversePipelineState }) {
  const groupRef = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;
    groupRef.current.children.forEach((child, i) => {
      const angle = (i / groupRef.current!.children.length) * Math.PI * 2;
      const radius = 1.3 + Math.sin(t * 2 + i) * 0.25;
      child.position.set(Math.cos(angle) * radius, Math.sin(t * 3 + i) * 0.4, Math.sin(angle) * radius);
    });
  });

  if (pipeline.reasoningState !== "done") return null;

  return (
    <group ref={groupRef}>
      {Array.from({ length: 18 }, (_, i) => (
        <mesh key={i}>
          <sphereGeometry args={[0.045, 10, 10]} />
          <meshBasicMaterial color={i % 2 ? "#FFD700" : "#FF3366"} transparent opacity={0.72} />
        </mesh>
      ))}
    </group>
  );
}

function Environment() {
  return (
    <>
      <ambientLight intensity={0.15} color="#1a0a2e" />
      <directionalLight position={[5, 10, 5]} intensity={0.4} color="#4ECDC4" />
      <directionalLight position={[-3, -5, -3]} intensity={0.2} color="#FF0055" />
      <pointLight position={[10, 2, -5]} intensity={1} distance={30} color="#C084FC" />
    </>
  );
}

export default function PlanetariumScene({
  timeSpeed,
  onSelectBody,
  selectedBody,
  pipeline,
}: {
  timeSpeed: number;
  onSelectBody: (body: CelestialBodyData | null) => void;
  selectedBody: CelestialBodyData | null;
  pipeline: UniversePipelineState;
}) {
  const [centerSelected, setCenterSelected] = useState(false);
  const selectedId = selectedBody?.id ?? null;

  const handleCenterClick = useCallback(() => {
    setCenterSelected(true);
    onSelectBody(null);
    window.setTimeout(() => setCenterSelected(false), 2400);
  }, [onSelectBody]);

  return (
    <>
      <color attach="background" args={["#03030A"]} />
      <fog attach="fog" args={["#03030A", 20, 52]} />

      <Environment />
      <StarField />
      <NebulaCloud />
      <PipelineFlow pipeline={pipeline} />
      <CyberCore pipeline={pipeline} onClick={handleCenterClick} />
      <DoneBurst pipeline={pipeline} />

      {CELESTIAL_BODIES.map((body) => {
        const activity = bodyActivity(body, pipeline);
        return (
          <OrbitRing key={`orbit-${body.id}`} radius={body.distance} tilt={body.tilt} color={body.material.color} active={activity} />
        );
      })}

      {CELESTIAL_BODIES.map((body) => (
        <CelestialBody
          key={body.id}
          data={body}
          timeSpeed={timeSpeed}
          onSelect={onSelectBody}
          isSelected={selectedId === body.id}
          activity={bodyActivity(body, pipeline)}
        />
      ))}

      <OrbitControls enablePan enableZoom enableRotate minDistance={2} maxDistance={30} maxPolarAngle={Math.PI} minPolarAngle={0} target={[0, 0, 0]} autoRotate={pipeline.reasoningState === "idle"} autoRotateSpeed={0.2} />

      {centerSelected && (
        <Html center position={[0, 1.75, 0]}>
          <div style={{
            background: "rgba(0,0,0,0.78)",
            border: "1px solid #FF6B00",
            color: "#FFD700",
            padding: "10px 18px",
            borderRadius: 6,
            fontSize: 13,
            fontFamily: "Inter, sans-serif",
            pointerEvents: "none",
            textShadow: "0 0 8px #FF6B00",
            boxShadow: "0 0 20px rgba(255,107,0,0.3)",
            whiteSpace: "nowrap",
          }}>
            {CENTER_LIGHT.name}: {pipeline.statusText}
          </div>
        </Html>
      )}
    </>
  );
}
