import { useState, useCallback } from 'react';
import { Canvas } from '@react-three/fiber';
import { Suspense } from 'react';
import PlanetariumScene from '../planetarium/PlanetariumScene';
import { CELESTIAL_BODIES, type CelestialBodyData } from '../planetarium/data';
import { LeftOutlined, PauseOutlined, CaretRightOutlined, FastForwardOutlined, StepForwardOutlined, CloseOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const SPEED_PRESETS = [
  { label: '暂停', value: 0, icon: <PauseOutlined /> },
  { label: '0.5x', value: 0.5, icon: null },
  { label: '1x', value: 1, icon: <CaretRightOutlined /> },
  { label: '2x', value: 2, icon: <FastForwardOutlined /> },
  { label: '5x', value: 5, icon: <StepForwardOutlined /> },
];

const MATERIAL_NAMES: Record<string, string> = {
  metal: '镜面金属',
  ceramic: '青瓷釉面',
  copper: '紫铜锻打',
  glass: '水晶玻璃',
  wood: '黑胡桃木纹',
  enamel: '高温珐琅',
  brushed: '磨砂拉丝不锈钢',
  polished: '黑曜石抛光',
};

const CYBER_COLORS: Record<string, string> = {
  overtime: '#00F0FF',
  slack: '#00FF88',
  coffee: '#FF6B35',
  buggy: '#FF0055',
  bald: '#C084FC',
  blessing: '#FFD700',
  kpi: '#E0E0E0',
  deadline: '#FF00FF',
};

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center h-full w-full bg-[#03030A]">
      <div className="text-center">
        <div className="text-4xl mb-4 animate-pulse" style={{ textShadow: '0 0 20px #00D4AA' }}>🌌</div>
        <div className="text-[#00D4AA] text-lg font-medium tracking-widest" style={{ textShadow: '0 0 10px #00D4AA' }}>
          正在初始化宇宙...
        </div>
        <div className="text-[#4ECDC4]/50 text-sm mt-2 font-mono">LOADING CYBER_SYSTEM v2.996</div>
      </div>
    </div>
  );
}

function InfoCard({ body, currentSpeed, onClose }: {
  body: CelestialBodyData;
  currentSpeed: number;
  onClose: () => void;
}) {
  const period = ((2 * Math.PI) / (body.speed * currentSpeed * 0.3)).toFixed(1);
  const actualSpeed = (body.speed * currentSpeed * 0.3).toFixed(3);
  const neonColor = CYBER_COLORS[body.id] || '#00D4AA';

  return (
    <div
      className="absolute top-4 right-4 z-10 w-72 bg-[#0A0A1A]/90 backdrop-blur-md rounded-lg border shadow-2xl overflow-hidden"
      style={{ borderColor: `${neonColor}40` }}
    >
      <div className="flex items-center justify-between px-4 py-3" style={{ background: `${neonColor}15`, borderBottom: `1px solid ${neonColor}30` }}>
        <div className="flex items-center gap-2">
          <span className="text-lg">🪐</span>
          <div>
            <div className="text-[#E0E0E0] font-bold text-sm" style={{ textShadow: `0 0 8px ${neonColor}` }}>{body.name}</div>
            <div className="text-xs font-mono" style={{ color: `${neonColor}AA` }}>{body.nickname}</div>
          </div>
        </div>
        <button onClick={onClose} className="text-[#E0E0E0]/40 hover:text-[#E0E0E0] transition-colors p-1"><CloseOutlined /></button>
      </div>
      <div className="p-4 space-y-3">
        <p className="text-[#B0B0C0]/80 text-xs leading-relaxed italic">"{body.description}"</p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-[#050510]/80 rounded-lg p-2 border" style={{ borderColor: `${neonColor}20` }}>
            <div className="text-[#808090] mb-1 text-[10px] uppercase tracking-wider">半径</div>
            <div className="text-[#E0E0E0] font-mono">{body.realRadius}</div>
          </div>
          <div className="bg-[#050510]/80 rounded-lg p-2 border" style={{ borderColor: `${neonColor}20` }}>
            <div className="text-[#808090] mb-1 text-[10px] uppercase tracking-wider">材质</div>
            <div className="text-[#E0E0E0]">{MATERIAL_NAMES[body.material.type] || body.material.type}</div>
          </div>
          <div className="bg-[#050510]/80 rounded-lg p-2 border" style={{ borderColor: `${neonColor}20` }}>
            <div className="text-[#808090] mb-1 text-[10px] uppercase tracking-wider">轨道距离</div>
            <div className="text-[#E0E0E0] font-mono">{body.distance.toFixed(1)} AU</div>
          </div>
          <div className="bg-[#050510]/80 rounded-lg p-2 border" style={{ borderColor: `${neonColor}20` }}>
            <div className="text-[#808090] mb-1 text-[10px] uppercase tracking-wider">当前转速</div>
            <div className="font-mono" style={{ color: neonColor }}>{actualSpeed} rad/s</div>
          </div>
          <div className="bg-[#050510]/80 rounded-lg p-2 col-span-2 border" style={{ borderColor: `${neonColor}20` }}>
            <div className="text-[#808090] mb-1 text-[10px] uppercase tracking-wider">当前周期</div>
            <div className="text-[#E0E0E0] font-mono">{currentSpeed > 0 ? `${period} 秒/圈` : '∞ (已暂停)'}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-1">
          <div className="text-[#808090] text-xs">材质色:</div>
          <div className="w-5 h-5 rounded border" style={{ backgroundColor: body.material.color, borderColor: `${neonColor}60`, boxShadow: `0 0 8px ${body.material.color}40` }} />
          <span className="text-[#808090]/60 text-xs font-mono">{body.material.color}</span>
        </div>
      </div>
    </div>
  );
}

function SpeedControl({ speed, onChange }: { speed: number; onChange: (v: number) => void; }) {
  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10">
      <div className="flex items-center gap-1 bg-[#0A0A1A]/90 backdrop-blur-md rounded-lg border border-[#00D4AA]/30 px-2 py-2 shadow-2xl">
        <div className="text-[#00D4AA]/60 text-xs px-2 border-r border-[#00D4AA]/20 mr-1 font-mono">TIME_SPEED</div>
        {SPEED_PRESETS.map((preset) => (
          <button
            key={preset.value}
            onClick={() => onChange(preset.value)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs font-medium transition-all ${
              speed === preset.value
                ? 'text-[#03030A] shadow-lg'
                : 'text-[#00D4AA]/60 hover:text-[#00D4AA] hover:bg-[#00D4AA]/10'
            }`}
            style={speed === preset.value ? { background: '#00D4AA', boxShadow: '0 0 12px #00D4AA60' } : {}}
          >
            {preset.icon && <span>{preset.icon}</span>}
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function LegendPanel() {
  const [collapsed, setCollapsed] = useState(true);

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="absolute top-4 left-4 z-10 bg-[#0A0A1A]/80 backdrop-blur-md rounded-lg border border-[#00D4AA]/30 p-3 text-[#00D4AA] hover:bg-[#0A0A1A] transition-all shadow-lg"
        style={{ textShadow: '0 0 8px #00D4AA' }}
      >
        <InfoCircleOutlined className="text-lg" />
      </button>
    );
  }

  return (
    <div className="absolute top-4 left-4 z-10 w-56 bg-[#0A0A1A]/90 backdrop-blur-md rounded-lg border border-[#00D4AA]/30 shadow-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3" style={{ background: '#00D4AA15', borderBottom: '1px solid #00D4AA30' }}>
        <span className="text-[#E0E0E0] font-bold text-sm tracking-wider" style={{ textShadow: '0 0 8px #00D4AA' }}>🌌 天体图鉴</span>
        <button onClick={() => setCollapsed(true)} className="text-[#E0E0E0]/40 hover:text-[#E0E0E0] transition-colors"><CloseOutlined /></button>
      </div>
      <div className="p-3 space-y-2 max-h-[60vh] overflow-y-auto">
        <div className="flex items-center gap-2 text-xs">
          <div className="w-3 h-3 rounded-full" style={{ background: '#FFD700', boxShadow: '0 0 8px #FFD700' }} />
          <span className="text-[#FFD700]">老板之眼 (核心)</span>
        </div>
        {CELESTIAL_BODIES.map((body) => (
          <div key={body.id} className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full border shrink-0" style={{ backgroundColor: body.material.color, borderColor: `${CYBER_COLORS[body.id]}60`, boxShadow: `0 0 6px ${CYBER_COLORS[body.id]}40` }} />
            <div className="text-[#C0C0D0]/80 truncate">{body.name}<span className="text-[#808090]/50 ml-1">({body.nickname})</span></div>
          </div>
        ))}
        <div className="pt-2 border-t border-[#00D4AA]/10 text-[10px] text-[#606070] leading-relaxed">
          提示：点击任意天体查看详情<br />拖拽旋转视角，滚轮缩放
        </div>
      </div>
    </div>
  );
}

export default function PlanetariumView() {
  const [timeSpeed, setTimeSpeed] = useState(1);
  const [selectedBody, setSelectedBody] = useState<CelestialBodyData | null>(null);
  const navigate = useNavigate();

  const handleSelectBody = useCallback((body: CelestialBodyData | null) => {
    setSelectedBody(body);
  }, []);

  return (
    <div className="relative w-full h-screen bg-[#03030A] overflow-hidden">
      <Suspense fallback={<LoadingScreen />}>
        <Canvas
          shadows
          camera={{ position: [0, 8, 15], fov: 55, near: 0.1, far: 100 }}
          gl={{ antialias: true, toneMapping: 3, toneMappingExposure: 1.2 }}
          style={{ width: '100%', height: '100%' }}
        >
          <PlanetariumScene timeSpeed={timeSpeed} onSelectBody={handleSelectBody} selectedBody={selectedBody} />
        </Canvas>
      </Suspense>

      {/* 扫描线 */}
      <div className="absolute inset-0 pointer-events-none z-[5] opacity-[0.03]"
        style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #00D4AA 2px, #00D4AA 4px)', backgroundSize: '100% 4px' }}
      />

      {/* 返回按钮 */}
      <button onClick={() => navigate('/chat')}
        className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 px-4 py-2 bg-[#0A0A1A]/80 backdrop-blur-md rounded-full border text-sm hover:bg-[#0A0A1A] transition-all shadow-lg"
        style={{ borderColor: '#00D4AA40', color: '#00D4AA', textShadow: '0 0 8px #00D4AA40' }}
      >
        <LeftOutlined />返回聊天
      </button>

      <LegendPanel />
      {selectedBody && <InfoCard body={selectedBody} currentSpeed={timeSpeed} onClose={() => setSelectedBody(null)} />}
      <SpeedControl speed={timeSpeed} onChange={setTimeSpeed} />

      <div className="absolute bottom-6 right-4 z-10 text-[10px] font-mono" style={{ color: '#00D4AA40' }}>
        CYBER_SYSTEM v2.996 // UNIVERSE_MODE
      </div>

      {/* 四角装饰 */}
      <div className="absolute top-0 left-0 w-16 h-16 pointer-events-none z-[5]" style={{ borderTop: '1px solid #00D4AA30', borderLeft: '1px solid #00D4AA30' }} />
      <div className="absolute top-0 right-0 w-16 h-16 pointer-events-none z-[5]" style={{ borderTop: '1px solid #00D4AA30', borderRight: '1px solid #00D4AA30' }} />
      <div className="absolute bottom-0 left-0 w-16 h-16 pointer-events-none z-[5]" style={{ borderBottom: '1px solid #00D4AA30', borderLeft: '1px solid #00D4AA30' }} />
      <div className="absolute bottom-0 right-0 w-16 h-16 pointer-events-none z-[5]" style={{ borderBottom: '1px solid #00D4AA30', borderRight: '1px solid #00D4AA30' }} />
    </div>
  );
}
