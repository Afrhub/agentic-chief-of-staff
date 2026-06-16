import React, { useId } from 'react';

interface SparklineProps {
  points: number[];
  accent?: string;
  height?: number;
}

const VW = 220;

const Sparkline: React.FC<SparklineProps> = ({
  points,
  accent = 'var(--accent)',
  height = 44
}) => {
  const gid = useId().replace(/:/g, '');
  if (!points.length) return null;

  const padY = 6;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const x = (i: number) => (points.length > 1 ? (VW * i) / (points.length - 1) : VW / 2);
  const y = (v: number) => padY + (height - padY * 2) * (1 - (v - min) / span);

  const line = points
    .map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(' ');
  const area = `${line} L${VW},${height} L0,${height} Z`;
  const lastX = x(points.length - 1);
  const lastY = y(points[points.length - 1]);

  return (
    <svg
      className="spark"
      viewBox={`0 0 ${VW} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`sp-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.28" />
          <stop offset="100%" stopColor={accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#sp-${gid})`} />
      <path
        d={line}
        fill="none"
        stroke={accent}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={lastX} cy={lastY} r={3} fill={accent} vectorEffect="non-scaling-stroke" />
    </svg>
  );
};

export default Sparkline;
