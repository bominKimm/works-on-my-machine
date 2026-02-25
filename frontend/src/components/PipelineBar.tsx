import { motion } from 'framer-motion';
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import { useAppStore } from '@/store/app';
import type { StepStatus } from '@/types/api';

const STEPS = [
  { id: 'upload', label: 'Upload', x: 80, y: 80, color: '#3b82f6' },
  { id: 'preprocessing', label: 'Preprocess', x: 240, y: 80, color: '#3b82f6' },
  { id: 'bicep', label: 'BiCep', x: 400, y: 80, color: '#3b82f6' },
  { id: 'policy', label: 'Policy', x: 560, y: 40, color: '#8b5cf6' },
  { id: 'redteam', label: 'RedTeam', x: 560, y: 120, color: '#10b981' },
  { id: 'result', label: 'Result', x: 720, y: 80, color: '#f59e0b' },
];

const getStepStatus = (stepId: string, steps: StepStatus[]): StepStatus['status'] => {
  const stepMap: Record<string, string> = {
    upload: '파일 업로드',
    preprocessing: '파일 전처리',
    bicep: 'BiCep 변환',
    policy: 'Policy 검증',
    redteam: 'RedTeam 분석',
    result: '결과 종합',
  };

  const step = steps.find((s) => s.step === stepMap[stepId]);
  return step?.status || 'pending';
};

const StepIcon = ({ status, size = 16 }: { status: StepStatus['status']; size?: number }) => {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="text-white" style={{ width: size, height: size }} />;
    case 'in_progress':
      return <Loader2 className="text-white animate-spin" style={{ width: size, height: size }} />;
    case 'error':
      return <XCircle className="text-red-500" style={{ width: size, height: size }} />;
    default:
      return <Circle className="text-gray-300" style={{ width: size, height: size }} />;
  }
};

// Hexagon path for SVG
const getHexagonPath = (cx: number, cy: number, size: number) => {
  const points = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 2;
    const x = cx + size * Math.cos(angle);
    const y = cy + size * Math.sin(angle);
    points.push(`${x},${y}`);
  }
  return `M ${points.join(' L ')} Z`;
};

export function PipelineBar() {
  const { analysisResult } = useAppStore();
  const steps = analysisResult?.steps || [];

  return (
    <div className="w-full overflow-x-auto pb-4">
      <div className="flex items-center justify-center min-w-[800px]">
        <svg width="800" height="180" viewBox="0 0 800 180" className="mx-auto">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="#d1d5db" />
            </marker>
            <marker
              id="arrowhead-active"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="#1f2937" />
            </marker>
          </defs>

          {/* Connection lines */}
          {/* Upload → Preprocess */}
          <motion.line
            x1="120" y1="80" x2="200" y2="80"
            stroke={getStepStatus('upload', steps) === 'completed' ? '#1f2937' : '#d1d5db'}
            strokeWidth="2"
            markerEnd={getStepStatus('upload', steps) === 'completed' ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5 }}
          />

          {/* Preprocess → BiCep */}
          <motion.line
            x1="280" y1="80" x2="360" y2="80"
            stroke={getStepStatus('preprocessing', steps) === 'completed' ? '#1f2937' : '#d1d5db'}
            strokeWidth="2"
            markerEnd={getStepStatus('preprocessing', steps) === 'completed' ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          />

          {/* BiCep → Policy (upper branch) */}
          <motion.path
            d="M 440 80 L 480 80 L 520 40"
            stroke={getStepStatus('bicep', steps) === 'completed' ? '#1f2937' : '#d1d5db'}
            strokeWidth="2"
            fill="none"
            markerEnd={getStepStatus('bicep', steps) === 'completed' ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          />

          {/* BiCep → RedTeam (lower branch) */}
          <motion.path
            d="M 440 80 L 480 80 L 520 120"
            stroke={getStepStatus('bicep', steps) === 'completed' ? '#1f2937' : '#d1d5db'}
            strokeWidth="2"
            fill="none"
            markerEnd={getStepStatus('bicep', steps) === 'completed' ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          />

          {/* Policy → Result (merge upper) */}
          <motion.path
            d="M 600 40 L 640 40 L 680 80"
            stroke={getStepStatus('policy', steps) === 'completed' ? '#1f2937' : '#d1d5db'}
            strokeWidth="2"
            fill="none"
            markerEnd={getStepStatus('policy', steps) === 'completed' ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          />

          {/* RedTeam → Result (merge lower) */}
          <motion.path
            d="M 600 120 L 640 120 L 680 80"
            stroke={getStepStatus('redteam', steps) === 'completed' ? '#1f2937' : '#d1d5db'}
            strokeWidth="2"
            fill="none"
            markerEnd={getStepStatus('redteam', steps) === 'completed' ? 'url(#arrowhead-active)' : 'url(#arrowhead)'}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          />

          {/* Step nodes */}
          {STEPS.map((step, index) => {
            const status = getStepStatus(step.id, steps);
            const isActive = status === 'in_progress' || status === 'completed';
            
            return (
              <g key={step.id}>
                {/* Hexagon background */}
                <motion.path
                  d={getHexagonPath(step.x, step.y, 28)}
                  fill={isActive ? step.color : '#e5e7eb'}
                  stroke={isActive ? step.color : '#d1d5db'}
                  strokeWidth="2"
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: index * 0.1, type: 'spring', stiffness: 200 }}
                />
                
                {/* Icon */}
                <foreignObject
                  x={step.x - 8}
                  y={step.y - 8}
                  width="16"
                  height="16"
                >
                  <div className="flex items-center justify-center w-full h-full">
                    <StepIcon status={status} size={16} />
                  </div>
                </foreignObject>

                {/* Label */}
                <text
                  x={step.x}
                  y={step.y + 45}
                  textAnchor="middle"
                  className="text-xs font-medium"
                  fill={isActive ? '#1f2937' : '#9ca3af'}
                >
                  {step.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
