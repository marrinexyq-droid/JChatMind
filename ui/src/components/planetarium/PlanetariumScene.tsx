import { useRef, useState, useCallback, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import type { ThreeEvent } from '@react-three/fiber';
import {
  OrbitControls,
  Sphere,
  Html,
  Text,
} from '@react-three/drei';
import * as THREE from 'three';
import { CELESTIAL_BODIES, CENTER_LIGHT, type CelestialBodyData } from './data';

// ─── 工具函数 ───
function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

// ─── 星空背景粒子 ───
function StarField() {
  const count = 3000;
  const points = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 15 + Math.random() * 40;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
      const cc = Math.random();
      if (cc < 0.6) {
        colors[i * 3] = 0.8 + Math.random() * 0.2;
        colors[i * 3 + 1] = 0.9 + Math.random() * 0.1;
        colors[i * 3 + 2] = 1.0;
      } else if (cc < 0.85) {
        colors[i * 3] = 0.9;
        colors[i * 3 + 1] = 0.7 + Math.random() * 0.2;
        colors[i * 3 + 2] = 1.0;
      } else {
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = 0.6 + Math.random() * 0.3;
        colors[i * 3 + 2] = 0.7 + Math.random() * 0.3;
      }
    }
    return { positions, colors };
  }, []);

  const pointsRef = useRef<THREE.Points>(null);
  useFrame((state) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y = state.clock.elapsedTime * 0.005;
      pointsRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.002) * 0.05;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[points.positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[points.colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.08} vertexColors transparent opacity={0.9} sizeAttenuation depthWrite={false} />
    </points>
  );
}

// ─── 故障星星（偶尔闪烁变红/消失）───
function GlitchStars() {
  const count = 50;
  const data = useMemo(() => {
    const rand = seededRandom(999);
    return Array.from({ length: count }, () => ({
      x: (rand() - 0.5) * 60,
      y: (rand() - 0.5) * 60,
      z: (rand() - 0.5) * 30 - 20,
      phase: rand() * Math.PI * 2,
      speed: 2 + rand() * 4,
    }));
  }, []);

  const groupRef = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;
    groupRef.current.children.forEach((child, i) => {
      const d = data[i];
      const glitch = Math.sin(t * d.speed + d.phase);
      const isGlitching = glitch > 0.95;
      (child as THREE.Mesh).visible = !isGlitching;
      if (!isGlitching && glitch > 0.8) {
        ((child as THREE.Mesh).material as THREE.MeshBasicMaterial).color.setHex(0xFF0055);
      } else {
        ((child as THREE.Mesh).material as THREE.MeshBasicMaterial).color.setHex(0xFFFFFF);
      }
    });
  });

  return (
    <group ref={groupRef}>
      {data.map((d, i) => (
        <mesh key={i} position={[d.x, d.y, d.z]}>
          <boxGeometry args={[0.05, 0.05, 0.05]} />
          <meshBasicMaterial color="#FFFFFF" />
        </mesh>
      ))}
    </group>
  );
}

// ─── 星云背景 ───
function NebulaCloud() {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (meshRef.current) meshRef.current.rotation.z = state.clock.elapsedTime * 0.01;
  });
  return (
    <group>
      <mesh ref={meshRef} position={[0, 0, -25]} rotation={[0, 0, 0.3]}>
        <planeGeometry args={[60, 60]} />
        <meshBasicMaterial color="#1a0a2e" transparent opacity={0.4} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <mesh position={[-15, 8, -20]} rotation={[0.2, 0.5, 0]}>
        <planeGeometry args={[40, 30]} />
        <meshBasicMaterial color="#0a1a2e" transparent opacity={0.3} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <mesh position={[12, -5, -22]} rotation={[-0.1, -0.3, 0.2]}>
        <planeGeometry args={[35, 35]} />
        <meshBasicMaterial color="#2e0a1a" transparent opacity={0.25} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}

// ─── 断裂霓虹轨道（故障艺术）───
function GlitchOrbit({ radius, tilt, color, seed }: { radius: number; tilt: number; color: string; seed: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const rand = useMemo(() => seededRandom(seed), [seed]);

  // 生成断裂弧段
  const segments = useMemo(() => {
    const segs: { start: number; end: number; width: number }[] = [];
    let angle = 0;
    while (angle < Math.PI * 2) {
      const gap = 0.1 + rand() * 0.4;
      const len = 0.3 + rand() * 1.2;
      if (angle + len > Math.PI * 2) break;
      segs.push({ start: angle, end: angle + len, width: 0.01 + rand() * 0.02 });
      angle += len + gap;
    }
    return segs;
  }, [radius, seed]);

  // Glitch 状态
  const [glitchOffset, setGlitchOffset] = useState({ x: 0, y: 0, z: 0 });
  const [glitchColor, setGlitchColor] = useState(color);
  const [isGlitching, setIsGlitching] = useState(false);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (groupRef.current) {
      groupRef.current.rotation.z = t * 0.02;
    }

    // 随机触发 glitch
    const glitchTrigger = Math.sin(t * 3 + seed) * 0.5 + 0.5;
    if (glitchTrigger > 0.998 && !isGlitching) {
      setIsGlitching(true);
      setGlitchOffset({
        x: (Math.random() - 0.5) * 0.3,
        y: (Math.random() - 0.5) * 0.3,
        z: (Math.random() - 0.5) * 0.1,
      });
      setGlitchColor(Math.random() > 0.5 ? '#FFFFFF' : '#FF0055');
      setTimeout(() => {
        setIsGlitching(false);
        setGlitchOffset({ x: 0, y: 0, z: 0 });
        setGlitchColor(color);
      }, 100 + Math.random() * 150);
    }
  });

  return (
    <group ref={groupRef} rotation={[tilt, 0, 0]} position={[glitchOffset.x, glitchOffset.y, glitchOffset.z]}>
      {/* 断裂弧段 */}
      {segments.map((seg, i) => {
        const midAngle = (seg.start + seg.end) / 2;
        const arcLength = seg.end - seg.start;
        const tubeRadius = seg.width;
        const segmentsCount = Math.max(8, Math.floor(arcLength * 30));
        return (
          <mesh key={i} rotation={[0, 0, midAngle]} position={[Math.cos(midAngle) * radius * 0, Math.sin(midAngle) * radius * 0, 0]}>
            <torusGeometry args={[radius, tubeRadius, 6, segmentsCount, arcLength]} />
            <meshBasicMaterial color={glitchColor} transparent opacity={isGlitching ? 1 : 0.8} />
          </mesh>
        );
      })}

      {/* 电弧连接（断点之间的跳跃光线）*/}
      {segments.length > 1 && segments.slice(0, -1).map((seg, i) => {
        const nextSeg = segments[i + 1];
        const startAngle = seg.end;
        const endAngle = nextSeg.start;
        const midAngle = (startAngle + endAngle) / 2;
        const x1 = Math.cos(startAngle) * radius;
        const z1 = Math.sin(startAngle) * radius;
        const x2 = Math.cos(endAngle) * radius;
        const z2 = Math.sin(endAngle) * radius;
        return (
          <group key={`arc-${i}`}>
            <mesh position={[(x1 + x2) / 2, 0, (z1 + z2) / 2]}>
              <cylinderGeometry args={[0.005, 0.005, Math.sqrt((x2 - x1) ** 2 + (z2 - z1) ** 2), 4]} />
              <meshBasicMaterial color={color} transparent opacity={0.3 + Math.sin(midAngle * 3) * 0.2} />
            </mesh>
          </group>
        );
      })}

      {/* 霓虹 glow 外晕 */}
      <mesh>
        <torusGeometry args={[radius, 0.06, 8, 64]} />
        <meshBasicMaterial color={color} transparent opacity={0.06} />
      </mesh>
    </group>
  );
}

// ─── 全息笼 ───
function HologramCage({ radius, color, isSelected }: { radius: number; color: string; isSelected: boolean }) {
  const outerRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (outerRef.current) {
      outerRef.current.rotation.y = t * 0.3;
      outerRef.current.rotation.x = Math.sin(t * 0.2) * 0.1;
    }
    if (innerRef.current) {
      innerRef.current.rotation.y = -t * 0.5;
      innerRef.current.rotation.z = Math.cos(t * 0.15) * 0.1;
    }
  });

  return (
    <group>
      {/* 外层二十面体 */}
      <mesh ref={outerRef}>
        <icosahedronGeometry args={[radius * 1.6, 0]} />
        <meshBasicMaterial color={color} transparent opacity={isSelected ? 0.25 : 0.12} wireframe />
      </mesh>
      {/* 内层八面体 */}
      <mesh ref={innerRef}>
        <octahedronGeometry args={[radius * 1.3, 0]} />
        <meshBasicMaterial color={color} transparent opacity={isSelected ? 0.4 : 0.2} wireframe />
      </mesh>
      {/* 选中时的能量线 */}
      {isSelected && (
        <mesh>
          <icosahedronGeometry args={[radius * 1.5, 0]} />
          <meshBasicMaterial color="#FFFFFF" transparent opacity={0.08} wireframe />
        </mesh>
      )}
    </group>
  );
}

// ─── 扫描线 ───
function ScanLine({ radius, color }: { radius: number; color: string }) {
  const lineRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!lineRef.current) return;
    const t = state.clock.elapsedTime;
    lineRef.current.position.y = Math.sin(t * 2) * radius * 1.2;
    lineRef.current.rotation.x = Math.PI / 2;
  });

  return (
    <mesh ref={lineRef}>
      <planeGeometry args={[radius * 2.5, 0.02]} />
      <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
    </mesh>
  );
}

// ─── 冲击波 ───
function ShockWave() {
  const ringRef = useRef<THREE.Mesh>(null);
  const [active, setActive] = useState(false);
  const progressRef = useRef(0);
  const lastTriggerRef = useRef(0);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    // 每10秒触发一次
    if (t - lastTriggerRef.current >= 10) {
      lastTriggerRef.current = t;
      setActive(true);
      progressRef.current = 0;
      setTimeout(() => setActive(false), 2000);
    }

    if (active && ringRef.current) {
      progressRef.current += 0.008;
      const p = progressRef.current;
      const scale = p * 25;
      ringRef.current.scale.setScalar(scale);
      (ringRef.current.material as THREE.MeshBasicMaterial).opacity = (1 - p) * 0.3;
    }
  });

  if (!active) return null;

  return (
    <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
      <ringGeometry args={[0.95, 1.0, 64]} />
      <meshBasicMaterial color="#00D4AA" transparent opacity={0.3} side={THREE.DoubleSide} />
    </mesh>
  );
}

// ─── 数据卡片 ───
function DataCards() {
  const cards = useMemo(() => {
    const rand = seededRandom(777);
    return Array.from({ length: 5 }, (_, i) => ({
      id: i,
      startBody: Math.floor(rand() * CELESTIAL_BODIES.length),
      endBody: Math.floor(rand() * CELESTIAL_BODIES.length),
      speed: 0.1 + rand() * 0.2,
      offset: rand() * Math.PI * 2,
      height: 1 + rand() * 2,
    }));
  }, []);

  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;

    groupRef.current.children.forEach((child, i) => {
      const card = cards[i];
      const progress = ((t * card.speed + card.offset) % (Math.PI * 2)) / (Math.PI * 2);
      const startBody = CELESTIAL_BODIES[card.startBody];
      const endBody = CELESTIAL_BODIES[card.endBody];

      const sx = Math.cos(card.offset) * startBody.distance;
      const sz = Math.sin(card.offset) * startBody.distance;
      const ex = Math.cos(card.offset + Math.PI) * endBody.distance;
      const ez = Math.sin(card.offset + Math.PI) * endBody.distance;

      child.position.x = sx + (ex - sx) * progress;
      child.position.z = sz + (ez - sz) * progress;
      child.position.y = Math.sin(progress * Math.PI) * card.height;
      child.rotation.y = t * 2;
    });
  });

  return (
    <group ref={groupRef}>
      {cards.map((card) => (
        <mesh key={card.id}>
          <planeGeometry args={[0.3, 0.2]} />
          <meshBasicMaterial color="#00D4AA" transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      ))}
    </group>
  );
}

// ─── 中心核心 ───
function CyberCore({ onClick }: { onClick: () => void }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const innerRingRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    if (meshRef.current) {
      meshRef.current.rotation.y = t * 0.2;
      meshRef.current.rotation.x = Math.sin(t * 0.3) * 0.1;
    }
    if (glowRef.current) {
      glowRef.current.scale.setScalar(1 + Math.sin(t * 3) * 0.08);
    }
    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.15;
      ringRef.current.rotation.x = Math.sin(t * 0.2) * 0.3;
    }
    if (innerRingRef.current) {
      innerRingRef.current.rotation.z = -t * 0.25;
      innerRingRef.current.rotation.y = Math.cos(t * 0.15) * 0.2;
    }
  });

  return (
    <group onClick={onClick}>
      <Sphere ref={meshRef} args={[0.5, 32, 32]}>
        <meshStandardMaterial color={CENTER_LIGHT.color} emissive={CENTER_LIGHT.color} emissiveIntensity={4} roughness={0.1} metalness={0.9} />
      </Sphere>
      <Sphere ref={glowRef} args={[0.8, 32, 32]}>
        <meshBasicMaterial color="#FF6B00" transparent opacity={0.12} />
      </Sphere>
      <Sphere args={[0.65, 32, 32]}>
        <meshBasicMaterial color="#FFD700" transparent opacity={0.2} />
      </Sphere>
      <mesh ref={ringRef}>
        <torusGeometry args={[1.0, 0.02, 8, 64]} />
        <meshBasicMaterial color="#FF6B00" transparent opacity={0.6} />
      </mesh>
      <mesh ref={innerRingRef}>
        <torusGeometry args={[0.75, 0.015, 8, 64]} />
        <meshBasicMaterial color="#FFD700" transparent opacity={0.8} />
      </mesh>
      <pointLight color="#FFD700" intensity={5} distance={25} decay={2} />
      <pointLight color="#FF6B00" intensity={2} distance={15} decay={2} />
      <pointLight color="#00D4AA" intensity={0.5} distance={20} decay={2} />
    </group>
  );
}

// ─── 材质生成器 ───
function createMaterial(mat: CelestialBodyData['material']) {
  const props = {
    color: mat.color,
    roughness: mat.roughness,
    metalness: mat.metalness,
    transparent: mat.transparent ?? false,
    opacity: mat.opacity ?? 1,
    emissive: mat.emissive ?? '#000000',
    emissiveIntensity: mat.emissiveIntensity ?? 0,
  };

  switch (mat.type) {
    case 'glass':
      return (
        <meshPhysicalMaterial
          {...props}
          transmission={0.6}
          thickness={0.5}
          ior={1.5}
          clearcoat={1}
          clearcoatRoughness={0.1}
        />
      );
    case 'ceramic':
      return <meshPhysicalMaterial {...props} clearcoat={0.8} clearcoatRoughness={0.2} />;
    case 'enamel':
      return <meshPhysicalMaterial {...props} clearcoat={1} clearcoatRoughness={0.05} />;
    default:
      return <meshStandardMaterial {...props} />;
  }
}

// ─── 单个天体 ───
function CelestialBody({
  data,
  timeSpeed,
  onSelect,
  isSelected,
}: {
  data: CelestialBodyData;
  timeSpeed: number;
  onSelect: (body: CelestialBodyData | null) => void;
  isSelected: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const bodyRef = useRef<THREE.Mesh>(null);
  const angleRef = useRef(Math.random() * Math.PI * 2);
  const glowRef = useRef<THREE.Mesh>(null);

  const cyberColors: Record<string, string> = {
    overtime: '#00F0FF', slack: '#00FF88', coffee: '#FF6B35',
    buggy: '#FF0055', bald: '#C084FC', blessing: '#FFD700',
    kpi: '#E0E0E0', deadline: '#FF00FF',
  };
  const neonColor = cyberColors[data.id] || '#00D4AA';

  useFrame((_, delta) => {
    angleRef.current += data.speed * timeSpeed * delta * 0.3;
    if (groupRef.current) {
      groupRef.current.position.set(
        Math.cos(angleRef.current) * data.distance,
        0,
        Math.sin(angleRef.current) * data.distance
      );
    }
    if (bodyRef.current) bodyRef.current.rotation.y += delta * 0.5;
    if (glowRef.current) {
      glowRef.current.scale.setScalar(1 + Math.sin(performance.now() * 0.003) * 0.1);
    }
  });

  const handleClick = useCallback((e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    onSelect(data);
  }, [data, onSelect]);

  return (
    <group ref={groupRef} onClick={handleClick}>
      {/* 全息笼 */}
      <HologramCage radius={data.radius} color={neonColor} isSelected={isSelected} />

      {/* 天体本体 */}
      <Sphere ref={bodyRef} args={[data.radius, 32, 32]}>
        {createMaterial(data.material)}
      </Sphere>

      {/* 扫描线 */}
      <ScanLine radius={data.radius} color={neonColor} />

      {/* 霓虹外发光 */}
      <Sphere ref={glowRef} args={[data.radius * 1.15, 32, 32]}>
        <meshBasicMaterial color={neonColor} transparent opacity={0.1} />
      </Sphere>

      {/* 选中高亮 */}
      {isSelected && (
        <>
          <Sphere args={[data.radius * 1.4, 32, 32]}>
            <meshBasicMaterial color={neonColor} transparent opacity={0.08} wireframe />
          </Sphere>
          <mesh position={[data.radius * 1.5, 0, 0]}>
            <sphereGeometry args={[0.04, 8, 8]} />
            <meshBasicMaterial color={neonColor} />
          </mesh>
          <mesh position={[-data.radius * 1.5, 0, 0]}>
            <sphereGeometry args={[0.04, 8, 8]} />
            <meshBasicMaterial color={neonColor} />
          </mesh>
        </>
      )}

      {/* 行星环 */}
      {data.hasRing && (
        <group>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[data.radius * 1.6, 0.025, 8, 64]} />
            <meshStandardMaterial color="#FFD700" emissive="#FFD700" emissiveIntensity={0.5} metalness={0.9} roughness={0.1} transparent opacity={0.7} />
          </mesh>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[data.radius * 1.8, 0.012, 8, 64]} />
            <meshStandardMaterial color="#FFA500" emissive="#FFA500" emissiveIntensity={0.3} metalness={0.8} roughness={0.2} transparent opacity={0.4} />
          </mesh>
        </group>
      )}

      {/* 卫星 */}
      {data.moons?.map((moon, idx) => (
        <Moon key={idx} data={moon} timeSpeed={timeSpeed} />
      ))}

      {/* 全息标签 */}
      <Text
        position={[0, data.radius + 0.8, 0]}
        fontSize={0.25}
        color={isSelected ? neonColor : '#E0E0E0'}
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.01}
        outlineColor="#000000"
      >
        {data.name}
      </Text>

      {/* 悬浮 HTML 标签 */}
      <Html position={[0, data.radius + 0.5, 0]} center distanceFactor={10} style={{ pointerEvents: 'none', userSelect: 'none' }}>
        <div style={{
          fontSize: '12px',
          color: isSelected ? neonColor : '#E0E0E0',
          fontWeight: isSelected ? 'bold' : 'normal',
          textShadow: isSelected ? `0 0 8px ${neonColor}` : '0 0 4px rgba(0,0,0,0.9)',
          whiteSpace: 'nowrap',
          fontFamily: 'Inter, sans-serif',
          letterSpacing: '0.05em',
        }}>
          {data.name}
        </div>
      </Html>
    </group>
  );
}

// ─── 卫星 ───
function Moon({ data, timeSpeed }: { data: { name: string; distance: number; speed: number; radius: number }; timeSpeed: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const angleRef = useRef(Math.random() * Math.PI * 2);

  useFrame((_, delta) => {
    angleRef.current += data.speed * timeSpeed * delta * 0.5;
    if (ref.current) {
      ref.current.position.set(
        Math.cos(angleRef.current) * data.distance,
        0,
        Math.sin(angleRef.current) * data.distance
      );
    }
  });

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[data.radius, 16, 16]} />
      <meshStandardMaterial color="#6080A0" emissive="#405070" emissiveIntensity={0.3} roughness={0.6} metalness={0.5} />
    </mesh>
  );
}

// ─── 环境光 ───
function CyberEnvironment() {
  return (
    <>
      <ambientLight intensity={0.15} color="#1a0a2e" />
      <directionalLight position={[5, 10, 5]} intensity={0.4} color="#4ECDC4" />
      <directionalLight position={[-3, -5, -3]} intensity={0.2} color="#FF0055" />
      <pointLight position={[10, 2, -5]} intensity={1} distance={30} color="#C084FC" />
      <pointLight position={[-8, -2, 8]} intensity={0.8} distance={25} color="#00D4AA" />
    </>
  );
}

// ─── 主场景 ───
export default function PlanetariumScene({
  timeSpeed,
  onSelectBody,
  selectedBody,
}: {
  timeSpeed: number;
  onSelectBody: (body: CelestialBodyData | null) => void;
  selectedBody: CelestialBodyData | null;
}) {
  const [centerSelected, setCenterSelected] = useState(false);

  const handleCenterClick = useCallback(() => {
    setCenterSelected(true);
    onSelectBody(null);
    setTimeout(() => setCenterSelected(false), 3000);
  }, [onSelectBody]);

  const selectedId = selectedBody?.id ?? null;
  const orbitColors = ['#00D4AA', '#00F0FF', '#C084FC', '#FF0055', '#FF6B35', '#FFD700', '#E0E0E0', '#FF00FF'];

  return (
    <>
      <color attach="background" args={['#03030A']} />
      <fog attach="fog" args={['#03030A', 20, 50]} />

      <CyberEnvironment />

      {/* 背景 */}
      <StarField />
      <NebulaCloud />
      <GlitchStars />

      {/* 特效 */}
      <ShockWave />
      <DataCards />

      {/* 中心核心 */}
      <CyberCore onClick={handleCenterClick} />

      {/* 断裂霓虹轨道 */}
      {CELESTIAL_BODIES.map((body, i) => (
        <GlitchOrbit
          key={`orbit-${body.id}`}
          radius={body.distance}
          tilt={body.tilt}
          color={orbitColors[i % orbitColors.length]}
          seed={i * 100}
        />
      ))}

      {/* 天体 */}
      {CELESTIAL_BODIES.map((body) => (
        <CelestialBody
          key={body.id}
          data={body}
          timeSpeed={timeSpeed}
          onSelect={onSelectBody}
          isSelected={selectedId === body.id}
        />
      ))}

      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={2}
        maxDistance={30}
        maxPolarAngle={Math.PI}
        minPolarAngle={0}
        target={[0, 0, 0]}
        autoRotate={false}
      />

      {centerSelected && (
        <Html center position={[0, 1.8, 0]}>
          <div style={{
            background: 'rgba(0,0,0,0.8)',
            border: '1px solid #FF6B00',
            color: '#FFD700',
            padding: '10px 20px',
            borderRadius: '4px',
            fontSize: '14px',
            fontFamily: 'Inter, sans-serif',
            pointerEvents: 'none',
            textShadow: '0 0 8px #FF6B00',
            boxShadow: '0 0 20px rgba(255,107,0,0.3)',
          }}>
            👁️ 老板之眼正在注视着你...
          </div>
        </Html>
      )}
    </>
  );
}
