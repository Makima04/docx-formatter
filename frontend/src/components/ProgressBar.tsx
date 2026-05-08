import { useState, useEffect, useRef } from 'react';
import { formatDuration } from '../utils/format';
import type { TaskInfo } from '../types';

interface Stage {
  id: string;
  label: string;
  icon: string;
}

const STAGES: Stage[] = [
  { id: 'parse', label: '解析文档', icon: '📄' },
  { id: 'classify', label: '识别结构', icon: '🔬' },
  { id: 'assemble', label: '排版生成', icon: '✨' },
  { id: 'validate', label: '校验修复', icon: '🛡️' },
  { id: 'complete', label: '完成', icon: '✅' },
];

function getStageIndex(status: string, progress: number): number {
  if (status === 'completed') return 4;
  if (status === 'failed') return -1;
  switch (status) {
    case 'pending': return -1;
    case 'processing': return 0;
    case 'classifying': return 1;
    case 'assembling': return 2;
    case 'rendering':
    case 'validating':
    case 'repairing': return 3;
    default:
      if (progress >= 100) return 4;
      if (progress >= 72) return 3;
      if (progress >= 55) return 2;
      if (progress >= 25) return 1;
      return 0;
  }
}

interface Props {
  task: Pick<TaskInfo, 'progress' | 'message' | 'status'>;
  startedAt: number | null;
}

export default function ProgressBar({ task, startedAt }: Props) {
  const { progress, message, status } = task;
  const [elapsed, setElapsed] = useState(0);
  const [displayedProgress, setDisplayedProgress] = useState(0);
  const prevTargetRef = useRef(0);
  const animRef = useRef(0);

  // Elapsed time ticker
  useEffect(() => {
    if (!startedAt || status === 'completed' || status === 'failed') return;
    const tick = () => setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [startedAt, status]);

  // Smooth progress animation
  useEffect(() => {
    const target = progress;
    const start = prevTargetRef.current;
    prevTargetRef.current = target;

    const startTime = performance.now();
    const duration = 500;

    const animate = (now: number) => {
      const t = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setDisplayedProgress(start + (target - start) * eased);
      if (t < 1) animRef.current = requestAnimationFrame(animate);
    };

    cancelAnimationFrame(animRef.current);
    animRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animRef.current);
  }, [progress]);

  const stageIdx = getStageIndex(status, progress);
  const isDone = status === 'completed';
  const isFailed = status === 'failed';
  const isIndeterminate = !isDone && !isFailed && progress === 0;

  return (
    <div style={{ margin: '20px 0' }}>
      {/* Stage Stepper */}
      <div style={stepperContainer}>
        {STAGES.map((stage, i) => {
          const isActive = i === stageIdx;
          const isPast = isDone ? i <= 4 : i < stageIdx;
          const isFailedStage = isFailed && i === Math.max(0, stageIdx);
          const dotBg = isFailedStage ? '#c5221f'
            : isActive || isPast ? '#1a73e8' : '#e8eaed';
          const dotColor = isFailedStage || isActive || isPast ? '#fff' : '#888';
          const labelColor = isFailedStage ? '#c5221f'
            : isActive ? '#1a73e8' : isPast ? '#333' : '#999';

          return (
            <div key={stage.id} style={stepWrapper}>
              {i > 0 && (
                <div style={{
                  ...connectorLine,
                  background: isPast ? '#1a73e8' : '#e8eaed',
                }} />
              )}
              <div style={{
                ...stepDot,
                background: dotBg,
                color: dotColor,
                transform: isActive ? 'scale(1.15)' : 'scale(1)',
                transition: 'all 0.4s ease',
                animation: isActive && !isDone ? 'docfmt-pulse 1.8s ease-in-out infinite' : 'none',
              }}>
                {stage.icon}
              </div>
              <span style={{ ...stepLabel, color: labelColor, fontWeight: isActive ? 600 : 400 }}>
                {isFailedStage ? '失败' : stage.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress Bar */}
      <div style={barContainer}>
        <div style={barTrack}>
          <div style={{
            ...barFill,
            width: isIndeterminate ? '100%' : `${displayedProgress}%`,
            transition: 'none',
            background: isIndeterminate
              ? 'linear-gradient(90deg, #e8eaed 25%, #a8c8fa 50%, #e8eaed 75%)'
              : 'linear-gradient(90deg, #1a73e8, #34a853)',
            backgroundSize: isIndeterminate ? '200% 100%' : '100% 100%',
            animation: isIndeterminate ? 'docfmt-shimmer 1.8s ease-in-out infinite' : 'none',
          }} />
        </div>

        <div style={barMeta}>
          <span style={{
            fontWeight: 600,
            fontSize: 14,
            color: isDone ? '#137333' : isFailed ? '#c5221f' : '#1a73e8',
          }}>
            {isDone ? '100%' : isFailed ? '失败' : `${Math.round(displayedProgress)}%`}
          </span>
          {startedAt && !isDone && !isFailed && (
            <span style={{ fontSize: 13, color: '#999' }}>
              已用时 {formatDuration(elapsed)}
            </span>
          )}
          {isDone && startedAt && (
            <span style={{ fontSize: 13, color: '#999' }}>
              耗时 {formatDuration(elapsed)}
            </span>
          )}
        </div>

        <p style={messageStyle}>{message || '准备中...'}</p>
      </div>

      <style>{keyframes}</style>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────────────

const stepperContainer: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'center',
  gap: 0,
  marginBottom: 18,
  padding: '0 8px',
};

const stepWrapper: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  position: 'relative',
  maxWidth: 80,
};

const connectorLine: React.CSSProperties = {
  position: 'absolute',
  top: 15,
  right: '50%',
  width: '100%',
  height: 3,
  zIndex: 0,
  transition: 'background 0.4s ease',
};

const stepDot: React.CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: 14,
  zIndex: 1,
  position: 'relative',
  lineHeight: 1,
};

const stepLabel: React.CSSProperties = {
  fontSize: 11,
  marginTop: 6,
  textAlign: 'center',
  whiteSpace: 'nowrap',
  transition: 'color 0.3s ease',
};

const barContainer: React.CSSProperties = {
  marginTop: 4,
};

const barTrack: React.CSSProperties = {
  width: '100%',
  height: 8,
  background: '#e8eaed',
  borderRadius: 4,
  overflow: 'hidden',
};

const barFill: React.CSSProperties = {
  height: '100%',
  background: 'linear-gradient(90deg, #1a73e8, #34a853)',
  borderRadius: 4,
  willChange: 'width',
};

const barMeta: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginTop: 8,
};

const messageStyle: React.CSSProperties = {
  fontSize: 13,
  color: '#666',
  textAlign: 'center',
  marginTop: 6,
  marginBottom: 0,
};

const keyframes = `
@keyframes docfmt-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(26, 115, 232, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(26, 115, 232, 0); }
}
@keyframes docfmt-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
`;
