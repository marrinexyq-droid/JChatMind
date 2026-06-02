import { useRef, useMemo, useCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { ASTEROID_MORPHS, simpleNoise, generateCrackTexture } from './asteroidData';
import type { PetState } from './PetContext';

interface AsteroidPet3DProps {
  state: PetState;
  morphId: string;
  isDragging: boolean;
  onClick: () => void;
}

// ─── 形态专属 Appendages ───

// 工业探测器：天线 + 太阳能板
function IndustrialAppendages({ state }: { state: PetState }) {
  const antennaRef = useRef<THREE.Group>(null);
  const panelRef = useRef<THREE.Mesh>(null);

  useFrame((state_frame) => {
    const t = state_frame.clock.elapsedTime;
    if (antennaRef.current) {
      antennaRef.current.rotation.y = t * (state === 'happy' ? 8 : state === 'sleep' ? 0 : 1);
      if (state === 'sleep') {
        antennaRef.current.rotation.x = Math.PI * 0.4;
      } else {
        antennaRef.current.rotation.x = Math.sin(t) * 0.1;
      }
    }
    if (panelRef.current) {
      panelRef.current.rotation.y = Math.sin(t * 0.5) * 0.3 + (state === 'sleep' ? 0 : 0.5);
    }
  });

  return (
    <group>
      {/* 天线 */}
      <group ref={antennaRef} position={[0, 0.9, 0]}>
        <cylinderGeometry args={[0.02, 0.02, 0.6, 8]} />
        <meshStandardMaterial color="#8B9CF7" emissive="#8B9CF7" emissiveIntensity={1} metalness={0.9} roughness={0.2} />
      </group>
      <group ref={antennaRef} position={[0.3, 0.7, 0]} rotation={[0, 0, -0.3]}>
        <cylinderGeometry args={[0.015, 0.015, 0.4, 8]} />
        <meshStandardMaterial color="#8B9CF7" emissive="#8B9CF7" emissiveIntensity={0.8} metalness={0.9} roughness={0.2} />
      </group>
      {/* 太阳能板 */}
      <mesh ref={panelRef} position={[-0.5, 0.2, 0]}>
        <boxGeometry args={[0.4, 0.02, 0.3]} />
        <meshStandardMaterial color="#1a1a3e" emissive="#00D4AA" emissiveIntensity={0.3} metalness={0.8} roughness={0.3} />
      </mesh>
      {/* 铆钉 */}
      {[[0.3, 0.3, 0.3], [-0.3, -0.2, 0.4], [0.2, -0.4, -0.3]].map((pos, i) => (
        <mesh key={i} position={pos as [number, number, number]}>
          <sphereGeometry args={[0.04, 8, 8]} />
          <meshStandardMaterial color="#5A5A6E" metalness={0.9} roughness={0.4} />
        </mesh>
      ))}
    </group>
  );
}

// 火山：岩浆柱
function VolcanicAppendages({ state }: { state: PetState }) {
  const columnsRef = useRef<THREE.Group>(null);

  const columns = useMemo(() => [
    { pos: [0.5, 0.6, 0.3] as [number, number, number], height: 0.4, phase: 0 },
    { pos: [-0.4, 0.5, 0.4] as [number, number, number], height: 0.3, phase: 1 },
    { pos: [0.2, 0.7, -0.4] as [number, number, number], height: 0.5, phase: 2 },
  ], []);

  useFrame((state_frame) => {
    const t = state_frame.clock.elapsedTime;
    if (columnsRef.current) {
      columnsRef.current.children.forEach((child, i) => {
        const col = columns[i];
        const pulse = state === 'happy' ? 1.5 : state === 'sleep' ? 0.3 : 1 + Math.sin(t * 2 + col.phase) * 0.2;
        child.scale.y = pulse;
        child.position.y = col.pos[1] + (pulse - 1) * col.height * 0.5;
      });
    }
  });

  return (
    <group>
      <group ref={columnsRef}>
        {columns.map((col, i) => (
          <mesh key={i} position={col.pos}>
            <cylinderGeometry args={[0.06, 0.08, col.height, 8]} />
            <meshStandardMaterial
              color="#FF6B35"
              emissive="#FF6B35"
              emissiveIntensity={state === 'happy' ? 4 : 2}
              roughness={0.4}
              metalness={0.3}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// 水晶：尖刺簇
function CrystalAppendages({ state }: { state: PetState }) {
  const spikesRef = useRef<THREE.Group>(null);

  const spikes = useMemo(() => Array.from({ length: 8 }, (_, i) => ({
    angle: (i / 8) * Math.PI * 2,
    height: 0.3 + Math.random() * 0.4,
    radius: 0.05 + Math.random() * 0.03,
    tilt: Math.random() * 0.3,
  })), []);

  useFrame((state_frame) => {
    const t = state_frame.clock.elapsedTime;
    if (spikesRef.current) {
      spikesRef.current.children.forEach((child, i) => {
        const s = spikes[i];
        const resonance = state === 'happy' ? Math.sin(t * 10 + i) * 0.1 : 0;
        child.rotation.z = s.tilt + resonance;
        (child as THREE.Mesh).material = new THREE.MeshStandardMaterial({
          color: '#C084FC',
          emissive: '#C084FC',
          emissiveIntensity: state === 'sleep' ? 0.1 : 1.5 + Math.sin(t * 2 + i) * 0.5,
          roughness: 0.1,
          metalness: 0,
          transparent: true,
          opacity: 0.9,
        });
      });
    }
  });

  return (
    <group ref={spikesRef}>
      {spikes.map((s, i) => (
        <mesh
          key={i}
          position={[
            Math.cos(s.angle) * 0.7,
            0,
            Math.sin(s.angle) * 0.7,
          ]}
          rotation={[0, -s.angle, s.tilt]}
        >
          <coneGeometry args={[s.radius, s.height, 6]} />
          <meshStandardMaterial
            color="#C084FC"
            emissive="#C084FC"
            emissiveIntensity={1.5}
            roughness={0.1}
            metalness={0}
            transparent
            opacity={0.9}
          />
        </mesh>
      ))}
    </group>
  );
}

// 彗星：冰晶尾迹
function IceAppendages({ state }: { state: PetState }) {
  const tailRef = useRef<THREE.Points>(null);
  const count = 40;

  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 0.5;
      pos[i * 3 + 1] = -0.8 - i * 0.08;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 0.5;
    }
    return pos;
  }, []);

  useFrame(() => {
    if (!tailRef.current) return;
    const posAttr = tailRef.current.geometry.attributes.position;
    const speed = state === 'happy' ? 0.05 : state === 'sleep' ? 0.005 : 0.02;
    for (let i = 0; i < count; i++) {
      let y = posAttr.getY(i);
      y -= speed;
      if (y < -4) {
        y = -0.8;
        posAttr.setX(i, (Math.random() - 0.5) * 0.5);
        posAttr.setZ(i, (Math.random() - 0.5) * 0.5);
      }
      posAttr.setY(i, y);
    }
    posAttr.needsUpdate = true;
  });

  return (
    <points ref={tailRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        color="#67E8F9"
        transparent
        opacity={0.6}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

// 暗物质：事件视界环
function CorruptedAppendages({ state }: { state: PetState }) {
  const ringRef = useRef<THREE.Mesh>(null);

  useFrame((state_frame) => {
    const t = state_frame.clock.elapsedTime;
    if (ringRef.current) {
      ringRef.current.rotation.z = t * 0.1;
      const scale = state === 'happy' ? 1.3 + Math.sin(t * 5) * 0.2 :
        state === 'sleep' ? 0.8 : 1 + Math.sin(t) * 0.05;
      ringRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group>
      {/* 事件视界环 */}
      <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.2, 0.03, 16, 64]} />
        <meshBasicMaterial color="#FF0055" transparent opacity={0.4} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.15, 0.06, 16, 64]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.8} />
      </mesh>
      {/* 扭曲效果粒子 */}
      <mesh position={[1.3, 0, 0]}>
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshBasicMaterial color="#FF0055" />
      </mesh>
      <mesh position={[-1.3, 0, 0]}>
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshBasicMaterial color="#FF0055" />
      </mesh>
    </group>
  );
}

// ─── 根据主题渲染 Appendages ───
function ThemeAppendages({ theme, state }: { theme: string; state: PetState }) {
  switch (theme) {
    case 'industrial': return <IndustrialAppendages state={state} />;
    case 'volcanic': return <VolcanicAppendages state={state} />;
    case 'crystal': return <CrystalAppendages state={state} />;
    case 'ice': return <IceAppendages state={state} />;
    case 'corrupted': return <CorruptedAppendages state={state} />;
    default: return null;
  }
}

// ─── 岩石本体 ───
function AsteroidBody({ morph, state }: { morph: (typeof ASTEROID_MORPHS)[0]; state: PetState }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial>(null);

  const geometry = useMemo(() => {
    const geo = new THREE.IcosahedronGeometry(1, morph.icoDetail);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
      const noise = simpleNoise(x * morph.noiseFreq, y * morph.noiseFreq, z * morph.noiseFreq, morph.noiseSeed);
      const scale = 1 + noise * morph.noiseAmp;
      pos.setXYZ(i, x * scale, y * scale, z * scale);
    }
    geo.computeVertexNormals();
    return geo;
  }, [morph]);

  const crackTexture = useMemo(() => {
    const canvas = generateCrackTexture(morph.crackColor, morph.emissiveIntensity, morph.noiseSeed);
    return new THREE.CanvasTexture(canvas);
  }, [morph]);

  useFrame((state_frame) => {
    const t = state_frame.clock.elapsedTime;
    if (meshRef.current) {
      if (state !== 'sleep') {
        meshRef.current.rotation.y += 0.005;
      }
      // 差异化自转
      switch (state) {
        case 'happy':
          meshRef.current.rotation.z = Math.sin(t * 6) * 0.2;
          meshRef.current.position.y = Math.sin(t * 8) * 0.15;
          break;
        case 'excite':
          meshRef.current.position.x = Math.sin(t * 20) * 0.02;
          meshRef.current.position.y = Math.abs(Math.sin(t * 10)) * 0.1;
          break;
        case 'think':
          meshRef.current.rotation.y += 0.02;
          meshRef.current.position.y = Math.sin(t * 2) * 0.05;
          break;
        case 'curious':
          meshRef.current.rotation.x = Math.sin(t * 1.5) * 0.15;
          break;
        case 'sleep':
          meshRef.current.position.y = Math.sin(t * 0.5) * 0.02;
          break;
        default:
          meshRef.current.position.set(0, 0, 0);
      }
    }
    if (materialRef.current) {
      let targetIntensity = morph.emissiveIntensity;
      switch (state) {
        case 'happy': targetIntensity = morph.emissiveIntensity * 3; break;
        case 'excite': targetIntensity = morph.emissiveIntensity * 2.5; break;
        case 'think': targetIntensity = morph.emissiveIntensity * 1.5 + Math.sin(t * 3) * 0.5; break;
        case 'sleep': targetIntensity = morph.emissiveIntensity * 0.2; break;
        default: targetIntensity = morph.emissiveIntensity;
      }
      materialRef.current.emissiveIntensity = THREE.MathUtils.lerp(
        materialRef.current.emissiveIntensity, targetIntensity, 0.1
      );
    }
  });

  // 主题化材质属性
  const materialProps = useMemo(() => {
    switch (morph.theme) {
      case 'volcanic':
        return { roughness: 0.7, metalness: 0.3, clearcoat: 0.3 };
      case 'crystal':
        return { roughness: 0.1, metalness: 0, transparent: true, opacity: 0.9, transmission: 0.4 };
      case 'ice':
        return { roughness: 0.2, metalness: 0.1, clearcoat: 0.8 };
      case 'corrupted':
        return { roughness: 0.95, metalness: 0 };
      default:
        return { roughness: morph.roughness, metalness: morph.metalness };
    }
  }, [morph.theme]);

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        ref={materialRef}
        color={morph.baseColor}
        emissive={morph.crackColor}
        emissiveIntensity={morph.emissiveIntensity}
        emissiveMap={crackTexture}
        {...materialProps}
      />
    </mesh>
  );
}

// ─── 环绕碎片 ───
function OrbitingDebris({ morph, state }: { morph: (typeof ASTEROID_MORPHS)[0]; state: PetState }) {
  const groupRef = useRef<THREE.Group>(null);
  const debrisData = useMemo(() =>
    Array.from({ length: morph.debrisCount }, (_, i) => ({
      angle: (i / morph.debrisCount) * Math.PI * 2,
      distance: 1.4 + Math.random() * 0.4,
      size: 0.08 + Math.random() * 0.12,
      speed: 0.3 + Math.random() * 0.5,
    })), [morph.debrisCount]);

  useFrame((_, delta) => {
    if (!groupRef.current) return;
    const speedMult = state === 'happy' ? 3 : state === 'excite' ? 5 : state === 'sleep' ? 0.1 : 1;
    groupRef.current.children.forEach((child, i) => {
      const d = debrisData[i];
      d.angle += d.speed * delta * speedMult;
      child.position.x = Math.cos(d.angle) * d.distance;
      child.position.z = Math.sin(d.angle) * d.distance;
      child.position.y = Math.sin(d.angle * 2) * 0.2;
      child.rotation.x += delta * d.speed;
    });
  });

  return (
    <group ref={groupRef}>
      {debrisData.map((d, i) => (
        <mesh key={i}>
          {morph.theme === 'crystal' ? (
            <>
              <octahedronGeometry args={[d.size, 0]} />
              <meshStandardMaterial color={morph.debrisColor} emissive={morph.debrisColor} emissiveIntensity={1} roughness={0.1} metalness={0} />
            </>
          ) : morph.theme === 'ice' ? (
            <>
              <icosahedronGeometry args={[d.size, 0]} />
              <meshStandardMaterial color={morph.debrisColor} emissive={morph.debrisColor} emissiveIntensity={0.5} roughness={0.1} metalness={0} transparent opacity={0.8} />
            </>
          ) : (
            <>
              <dodecahedronGeometry args={[d.size, 0]} />
              <meshStandardMaterial color={morph.debrisColor} emissive={morph.debrisColor} emissiveIntensity={0.5} roughness={0.8} metalness={0.2} />
            </>
          )}
        </mesh>
      ))}
    </group>
  );
}

// ─── 推进器尾焰 ───
function ThrusterTrail({ morph, state }: { morph: (typeof ASTEROID_MORPHS)[0]; state: PetState }) {
  if (!morph.hasThruster) return null;
  const particlesRef = useRef<THREE.Points>(null);
  const count = 30;
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 0.3;
      pos[i * 3 + 1] = -1.2 - Math.random() * 1.5;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 0.3;
    }
    return pos;
  }, []);

  useFrame(() => {
    if (!particlesRef.current) return;
    const posAttr = particlesRef.current.geometry.attributes.position;
    const intensity = state === 'happy' ? 2 : state === 'excite' ? 3 : state === 'sleep' ? 0.3 : 1;
    for (let i = 0; i < count; i++) {
      let y = posAttr.getY(i);
      y -= 0.02 * intensity;
      if (y < -2.5) {
        y = -1.2;
        posAttr.setX(i, (Math.random() - 0.5) * 0.3);
        posAttr.setZ(i, (Math.random() - 0.5) * 0.3);
      }
      posAttr.setY(i, y);
    }
    posAttr.needsUpdate = true;
  });

  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.06} color={morph.thrusterColor} transparent opacity={0.8} sizeAttenuation depthWrite={false} />
    </points>
  );
}

// ─── 传感器眼 ───
function SensorEye({ morph, state }: { morph: (typeof ASTEROID_MORPHS)[0]; state: PetState }) {
  const eyeRef = useRef<THREE.Mesh>(null);
  const { viewport } = useThree();

  useFrame((state_frame) => {
    if (!eyeRef.current || state !== 'curious') return;
    const mouse = state_frame.pointer;
    eyeRef.current.lookAt(mouse.x * viewport.width, mouse.y * viewport.height, 5);
  });

  if (state !== 'curious') return null;

  return (
    <group>
      <mesh ref={eyeRef} position={[0, 0.3, 0.9]} scale={[0.3, 0.3, 0.1]}>
        <circleGeometry args={[0.5, 16]} />
        <meshStandardMaterial color="#FFFFFF" emissive={morph.crackColor} emissiveIntensity={3} />
      </mesh>
      <mesh position={[0, 0.3, 2]} rotation={[0, 0, 0]}>
        <coneGeometry args={[0.1, 3, 8, 1, true]} />
        <meshBasicMaterial color={morph.crackColor} transparent opacity={0.1} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

// ─── 扫描光束 ───
function ScanBeam({ morph, state }: { morph: (typeof ASTEROID_MORPHS)[0]; state: PetState }) {
  const beamRef = useRef<THREE.Mesh>(null);
  useFrame((state_frame) => {
    if (!beamRef.current || state !== 'think') return;
    beamRef.current.rotation.y = state_frame.clock.elapsedTime * 2;
  });
  if (state !== 'think') return null;
  return (
    <mesh ref={beamRef}>
      <ringGeometry args={[1.8, 1.85, 64]} />
      <meshBasicMaterial color={morph.crackColor} transparent opacity={0.3} side={THREE.DoubleSide} />
    </mesh>
  );
}

// ─── 主组件 ───
export default function AsteroidPet3D({ state, morphId, isDragging, onClick }: AsteroidPet3DProps) {
  const morph = useMemo(() => {
    return ASTEROID_MORPHS.find(m => m.id === morphId) || ASTEROID_MORPHS[0];
  }, [morphId]);

  const handleClick = useCallback((e: any) => {
    e.stopPropagation?.();
    onClick();
  }, [onClick]);

  return (
    <group onClick={handleClick}>
      <pointLight color={morph.crackColor} intensity={2} distance={5} decay={2} />
      <pointLight color="#FFFFFF" intensity={0.5} distance={3} decay={2} />

      <AsteroidBody morph={morph} state={state} />
      <ThemeAppendages theme={morph.theme} state={state} />
      <OrbitingDebris morph={morph} state={state} />
      <ThrusterTrail morph={morph} state={state} />
      <SensorEye morph={morph} state={state} />
      <ScanBeam morph={morph} state={state} />

      {isDragging && (
        <mesh>
          <sphereGeometry args={[1.3, 16, 16]} />
          <meshBasicMaterial color={morph.crackColor} transparent opacity={0.05} wireframe />
        </mesh>
      )}
    </group>
  );
}
