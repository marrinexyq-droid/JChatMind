import { useState, useRef, useCallback, useEffect, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import AsteroidPet3D from './AsteroidPet3D';
import { usePet, petActions } from './usePet';
import { ASTEROID_MORPHS } from './asteroidData';
import { SettingOutlined, CloseOutlined } from '@ant-design/icons';

interface Position {
  x: number;
  y: number;
}

const initialPosition = (): Position => {
  if (typeof window === 'undefined') return { x: 0, y: 0 };
  return {
    x: window.innerWidth - 120,
    y: window.innerHeight - 120,
  };
};

function PetPanel({
  morphId,
  onMorphChange,
  onClose,
}: {
  morphId: string;
  onMorphChange: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <div className="absolute bottom-20 right-4 z-20 w-64 bg-[#0A0A1A]/95 backdrop-blur-md rounded-lg border border-[#00D4AA]/30 shadow-2xl overflow-hidden pointer-events-auto">
      <div className="flex items-center justify-between px-4 py-3" style={{ background: '#00D4AA15', borderBottom: '1px solid #00D4AA30' }}>
        <span className="text-[#E0E0E0] font-bold text-sm" style={{ textShadow: '0 0 8px #00D4AA' }}>
          🪐 形态切换
        </span>
        <button onClick={onClose} className="text-[#E0E0E0]/40 hover:text-[#E0E0E0] transition-colors">
          <CloseOutlined />
        </button>
      </div>
      <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
        {ASTEROID_MORPHS.map((morph) => (
          <button
            key={morph.id}
            onClick={() => {
              onMorphChange(morph.id);
              onClose();
            }}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left ${
              morphId === morph.id
                ? 'bg-[#00D4AA]/20 border border-[#00D4AA]/40'
                : 'bg-[#050510]/50 border border-transparent hover:bg-[#00D4AA]/10'
            }`}
          >
            <div
              className="w-8 h-8 rounded-full shrink-0"
              style={{
                background: `radial-gradient(circle, ${morph.crackColor}40 0%, ${morph.baseColor} 100%)`,
                boxShadow: `0 0 8px ${morph.crackColor}40`,
              }}
            />
            <div>
              <div className="text-[#E0E0E0] text-sm font-medium">{morph.name}</div>
              <div className="text-[#808090] text-xs">{morph.description}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function PetOverlay() {
  const { state, triggerAction, morphId, setMorphId } = usePet();
  const [position, setPosition] = useState<Position>(initialPosition);
  const [isDragging, setIsDragging] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const dragStart = useRef<Position>({ x: 0, y: 0 });
  const posStart = useRef<Position>({ x: 0, y: 0 });
  const dragMoved = useRef(false);

  // 窗口大小变化时调整
  useEffect(() => {
    const handleResize = () => {
      setPosition((prev) => ({
        x: Math.min(prev.x, window.innerWidth - 100),
        y: Math.min(prev.y, window.innerHeight - 100),
      }));
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 悬浮行为：缓慢漂向边缘
  useEffect(() => {
    if (isDragging) return;

    let rafId: number;
    const float = () => {
      if (isDragging) return;

      setPosition((prev) => {
        const margin = 80;
        let tx = prev.x;
        let ty = prev.y;

        // 吸引向最近边缘
        const distLeft = prev.x;
        const distRight = window.innerWidth - prev.x;
        const distTop = prev.y;
        const distBottom = window.innerHeight - prev.y;
        const minDist = Math.min(distLeft, distRight, distTop, distBottom);

        if (minDist > margin) {
          const speed = 0.3;
          if (minDist === distLeft) tx -= speed;
          else if (minDist === distRight) tx += speed;
          else if (minDist === distTop) ty -= speed;
          else if (minDist === distBottom) ty += speed;
        }

        // 正弦波漂浮
        const t = Date.now() * 0.001;
        tx += Math.sin(t * 0.5 + prev.y * 0.01) * 0.15;
        ty += Math.cos(t * 0.3 + prev.x * 0.01) * 0.1;

        // 边界限制
        tx = Math.max(60, Math.min(window.innerWidth - 60, tx));
        ty = Math.max(60, Math.min(window.innerHeight - 60, ty));

        return { x: tx, y: ty };
      });

      rafId = requestAnimationFrame(float);
    };

    rafId = requestAnimationFrame(float);
    return () => cancelAnimationFrame(rafId);
  }, [isDragging]);

  // 拖拽开始
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragMoved.current = false;
    setIsDragging(true);
    dragStart.current = { x: e.clientX, y: e.clientY };
    posStart.current = { ...position };
    (e.target as Element).setPointerCapture(e.pointerId);
  }, [position]);

  // 拖拽移动
  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.current.x;
    const dy = e.clientY - dragStart.current.y;

    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      dragMoved.current = true;
    }

    setPosition({
      x: posStart.current.x + dx,
      y: posStart.current.y + dy,
    });
  }, [isDragging]);

  // 拖拽结束
  const handlePointerUp = useCallback(() => {
    setIsDragging(false);
    if (!dragMoved.current) {
      // 点击（没有移动）→ 触发 happy
      triggerAction(petActions.setHappy());
    }
  }, [triggerAction]);

  // 右键菜单：切换面板
  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setShowPanel((prev) => !prev);
  }, []);

  // 安装 window.petActions
  useEffect(() => {
    window.petActions = {
      setHappy: () => triggerAction(petActions.setHappy()),
      setThink: () => triggerAction(petActions.setThink()),
      setCurious: () => triggerAction(petActions.setCurious()),
      setExcite: () => triggerAction(petActions.setExcite()),
    };
  }, [triggerAction]);

  return (
    <div className="fixed inset-0 pointer-events-none z-[9999]" style={{ touchAction: 'none' }}>
      {/* 3D Canvas 容器 */}
      <div
        className="absolute pointer-events-auto"
        style={{
          left: position.x - 60,
          top: position.y - 60,
          width: 120,
          height: 120,
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onContextMenu={handleContextMenu}
      >
        <Canvas
          camera={{ position: [0, 0, 4], fov: 50, near: 0.1, far: 20 }}
          gl={{ antialias: true, alpha: true }}
          style={{ width: '100%', height: '100%', background: 'transparent' }}
        >
          <Suspense fallback={null}>
            <AsteroidPet3D
              state={state}
              morphId={morphId}
              isDragging={isDragging}
              onClick={() => {}}
            />
          </Suspense>
        </Canvas>
      </div>

      {/* 设置按钮 */}
      <button
        onClick={() => setShowPanel((prev) => !prev)}
        className="absolute pointer-events-auto z-20 p-2 rounded-lg bg-[#0A0A1A]/80 border border-[#00D4AA]/30 text-[#00D4AA] hover:bg-[#0A0A1A] transition-all"
        style={{
          left: position.x + 45,
          top: position.y - 45,
          textShadow: '0 0 8px #00D4AA',
        }}
      >
        <SettingOutlined />
      </button>

      {/* 形态切换面板 */}
      {showPanel && (
        <PetPanel
          morphId={morphId}
          onMorphChange={setMorphId}
          onClose={() => setShowPanel(false)}
        />
      )}
    </div>
  );
}
