import { Suspense, useCallback, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import {
  CaretRightOutlined,
  CloseOutlined,
  FastForwardOutlined,
  InfoCircleOutlined,
  LeftOutlined,
  PauseOutlined,
  StepForwardOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PlanetariumScene from "../planetarium/PlanetariumScene";
import { CELESTIAL_BODIES, type CelestialBodyData } from "../planetarium/data";
import { useUniversePipeline } from "../../contexts/UniversePipelineContext";
import type { UniversePipelineState, UniverseReasoningState } from "../../types";

const SPEED_PRESETS = [
  { label: "Pause", value: 0, icon: <PauseOutlined /> },
  { label: "0.5x", value: 0.5, icon: null },
  { label: "1x", value: 1, icon: <CaretRightOutlined /> },
  { label: "2x", value: 2, icon: <FastForwardOutlined /> },
  { label: "5x", value: 5, icon: <StepForwardOutlined /> },
];

const PHASE_META: Record<UniverseReasoningState, { label: string; color: string; narrative: string }> = {
  idle: { label: "Idle", color: "#94A3B8", narrative: "Waiting for the next chat event." },
  planning: { label: "Planning", color: "#FFD700", narrative: "The core is mapping the answer route." },
  thinking: { label: "Thinking", color: "#00D4AA", narrative: "Reasoning energy is circulating through Cogito." },
  executing: { label: "Executing", color: "#00B4FF", narrative: "Tool and data paths are active." },
  streaming: { label: "Streaming", color: "#FF3366", narrative: "The response beam is extending chunk by chunk." },
  done: { label: "Done", color: "#C084FC", narrative: "The pipeline has settled into its final orbit." },
  error: { label: "Error", color: "#FF3366", narrative: "The pipeline reported a fault." },
};

function LoadingScreen() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-[#03030A]">
      <div className="text-center">
        <div className="mb-4 text-4xl animate-pulse" style={{ textShadow: "0 0 20px #00D4AA" }}>J</div>
        <div className="text-lg font-medium tracking-widest text-[#00D4AA]" style={{ textShadow: "0 0 10px #00D4AA" }}>
          Initializing pipeline planetarium
        </div>
        <div className="mt-2 font-mono text-sm text-[#4ECDC4]/50">UNIVERSE_BRIDGE v1</div>
      </div>
    </div>
  );
}

function InfoCard({ body, currentSpeed, onClose }: {
  body: CelestialBodyData;
  currentSpeed: number;
  onClose: () => void;
}) {
  const period = currentSpeed > 0 ? ((2 * Math.PI) / (body.speed * currentSpeed * 0.35)).toFixed(1) : "paused";
  const neonColor = body.material.color;

  return (
    <div
      className="absolute right-4 top-4 z-10 w-72 overflow-hidden rounded-lg border bg-[#0A0A1A]/90 shadow-2xl backdrop-blur-md"
      style={{ borderColor: `${neonColor}55` }}
    >
      <div className="flex items-center justify-between px-4 py-3" style={{ background: `${neonColor}15`, borderBottom: `1px solid ${neonColor}30` }}>
        <div>
          <div className="text-sm font-bold text-[#E0E0E0]" style={{ textShadow: `0 0 8px ${neonColor}` }}>{body.name}</div>
          <div className="font-mono text-xs" style={{ color: `${neonColor}CC` }}>{body.nickname}</div>
        </div>
        <button onClick={onClose} className="p-1 text-[#E0E0E0]/50 transition-colors hover:text-[#E0E0E0]"><CloseOutlined /></button>
      </div>
      <div className="space-y-3 p-4">
        <p className="text-xs leading-relaxed text-[#B0B0C0]/85">{body.description}</p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg border bg-[#050510]/80 p-2" style={{ borderColor: `${neonColor}25` }}>
            <div className="mb-1 text-[10px] uppercase tracking-wider text-[#808090]">Signal</div>
            <div className="font-mono text-[#E0E0E0]">{body.realRadius}</div>
          </div>
          <div className="rounded-lg border bg-[#050510]/80 p-2" style={{ borderColor: `${neonColor}25` }}>
            <div className="mb-1 text-[10px] uppercase tracking-wider text-[#808090]">Orbit</div>
            <div className="font-mono text-[#E0E0E0]">{period}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SpeedControl({ speed, onChange }: { speed: number; onChange: (v: number) => void }) {
  return (
    <div className="absolute bottom-6 left-1/2 z-10 -translate-x-1/2">
      <div className="flex items-center gap-1 rounded-lg border border-[#00D4AA]/30 bg-[#0A0A1A]/90 px-2 py-2 shadow-2xl backdrop-blur-md">
        <div className="mr-1 border-r border-[#00D4AA]/20 px-2 font-mono text-xs text-[#00D4AA]/60">TIME</div>
        {SPEED_PRESETS.map((preset) => (
          <button
            key={preset.value}
            onClick={() => onChange(preset.value)}
            className={`flex items-center gap-1 rounded px-3 py-1.5 text-xs font-medium transition-all ${
              speed === preset.value ? "text-[#03030A] shadow-lg" : "text-[#00D4AA]/60 hover:bg-[#00D4AA]/10 hover:text-[#00D4AA]"
            }`}
            style={speed === preset.value ? { background: "#00D4AA", boxShadow: "0 0 12px #00D4AA60" } : {}}
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
        className="absolute left-4 top-4 z-10 rounded-lg border border-[#00D4AA]/30 bg-[#0A0A1A]/80 p-3 text-[#00D4AA] shadow-lg backdrop-blur-md transition-all hover:bg-[#0A0A1A]"
        style={{ textShadow: "0 0 8px #00D4AA" }}
      >
        <InfoCircleOutlined className="text-lg" />
      </button>
    );
  }

  return (
    <div className="absolute left-4 top-4 z-10 w-64 overflow-hidden rounded-lg border border-[#00D4AA]/30 bg-[#0A0A1A]/90 shadow-2xl backdrop-blur-md">
      <div className="flex items-center justify-between px-4 py-3" style={{ background: "#00D4AA15", borderBottom: "1px solid #00D4AA30" }}>
        <span className="text-sm font-bold tracking-wider text-[#E0E0E0]" style={{ textShadow: "0 0 8px #00D4AA" }}>Pipeline Bodies</span>
        <button onClick={() => setCollapsed(true)} className="text-[#E0E0E0]/50 transition-colors hover:text-[#E0E0E0]"><CloseOutlined /></button>
      </div>
      <div className="max-h-[60vh] space-y-2 overflow-y-auto p-3">
        {CELESTIAL_BODIES.map((body) => (
          <div key={body.id} className="flex items-center gap-2 text-xs">
            <div className="h-3 w-3 shrink-0 rounded-full border" style={{ backgroundColor: body.material.color, borderColor: `${body.material.color}80`, boxShadow: `0 0 6px ${body.material.color}60` }} />
            <div className="truncate text-[#C0C0D0]/90">{body.name}<span className="ml-1 text-[#808090]/70">({body.nickname})</span></div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PipelineHud({ pipeline }: { pipeline: UniversePipelineState }) {
  const phase = PHASE_META[pipeline.reasoningState];
  const latest = useMemo(() => pipeline.timeline.slice(-5).reverse(), [pipeline.timeline]);

  return (
    <div className="pointer-events-none absolute bottom-20 left-4 z-10 w-80 rounded-lg border bg-[#0A0A1A]/82 p-4 shadow-2xl backdrop-blur-md" style={{ borderColor: `${phase.color}45` }}>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[#94A3B8]">JChatMind Pipeline</div>
          <div className="mt-1 text-lg font-semibold" style={{ color: phase.color, textShadow: `0 0 10px ${phase.color}66` }}>{phase.label}</div>
        </div>
        <div className="h-3 w-3 rounded-full animate-pulse" style={{ background: phase.color, boxShadow: `0 0 14px ${phase.color}` }} />
      </div>
      <div className="mb-3 text-sm leading-relaxed text-[#E2E8F0]">{pipeline.statusText || phase.narrative}</div>
      {pipeline.lastUserMessage && (
        <div className="mb-3 rounded border border-white/10 bg-white/[0.04] p-2 text-xs text-[#CBD5E1]">
          {pipeline.lastUserMessage.slice(0, 140)}
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded border border-white/10 bg-white/[0.04] p-2">
          <div className="text-[#94A3B8]">Stream tokens</div>
          <div className="mt-1 font-mono text-[#E2E8F0]">{pipeline.streamTokenEstimate}</div>
        </div>
        <div className="rounded border border-white/10 bg-white/[0.04] p-2">
          <div className="text-[#94A3B8]">Tool signals</div>
          <div className="mt-1 font-mono text-[#E2E8F0]">{pipeline.toolCallCount}</div>
        </div>
      </div>
      <div className="mt-3 space-y-1">
        {latest.map((node) => (
          <div key={node.id} className="flex items-center gap-2 text-[11px] text-[#94A3B8]">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: PHASE_META[node.reasoningState].color }} />
            <span className="truncate">{node.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PlanetariumView() {
  const [timeSpeed, setTimeSpeed] = useState(1);
  const [selectedBody, setSelectedBody] = useState<CelestialBodyData | null>(null);
  const { state: pipeline } = useUniversePipeline();
  const navigate = useNavigate();

  const handleSelectBody = useCallback((body: CelestialBodyData | null) => {
    setSelectedBody(body);
  }, []);

  return (
    <div className="relative h-screen w-full overflow-hidden bg-[#03030A]">
      <Suspense fallback={<LoadingScreen />}>
        <Canvas
          shadows
          camera={{ position: [0, 8, 15], fov: 55, near: 0.1, far: 100 }}
          gl={{ antialias: true, toneMapping: 3, toneMappingExposure: 1.2 }}
          style={{ width: "100%", height: "100%" }}
        >
          <PlanetariumScene timeSpeed={timeSpeed} onSelectBody={handleSelectBody} selectedBody={selectedBody} pipeline={pipeline} />
        </Canvas>
      </Suspense>

      <div className="pointer-events-none absolute inset-0 z-[5] opacity-[0.03]" style={{ backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, #00D4AA 2px, #00D4AA 4px)", backgroundSize: "100% 4px" }} />

      <button
        onClick={() => navigate("/chat")}
        className="absolute left-1/2 top-4 z-10 flex -translate-x-1/2 items-center gap-2 rounded-full border bg-[#0A0A1A]/80 px-4 py-2 text-sm shadow-lg backdrop-blur-md transition-all hover:bg-[#0A0A1A]"
        style={{ borderColor: "#00D4AA40", color: "#00D4AA", textShadow: "0 0 8px #00D4AA40" }}
      >
        <LeftOutlined /> Back to chat
      </button>

      <LegendPanel />
      <PipelineHud pipeline={pipeline} />
      {selectedBody && <InfoCard body={selectedBody} currentSpeed={timeSpeed} onClose={() => setSelectedBody(null)} />}
      <SpeedControl speed={timeSpeed} onChange={setTimeSpeed} />

      <div className="absolute bottom-6 right-4 z-10 font-mono text-[10px]" style={{ color: "#00D4AA55" }}>
        UNIVERSE_BRIDGE // {pipeline.reasoningState.toUpperCase()}
      </div>

      <div className="pointer-events-none absolute left-0 top-0 z-[5] h-16 w-16" style={{ borderLeft: "1px solid #00D4AA30", borderTop: "1px solid #00D4AA30" }} />
      <div className="pointer-events-none absolute right-0 top-0 z-[5] h-16 w-16" style={{ borderRight: "1px solid #00D4AA30", borderTop: "1px solid #00D4AA30" }} />
      <div className="pointer-events-none absolute bottom-0 left-0 z-[5] h-16 w-16" style={{ borderBottom: "1px solid #00D4AA30", borderLeft: "1px solid #00D4AA30" }} />
      <div className="pointer-events-none absolute bottom-0 right-0 z-[5] h-16 w-16" style={{ borderBottom: "1px solid #00D4AA30", borderRight: "1px solid #00D4AA30" }} />
    </div>
  );
}
