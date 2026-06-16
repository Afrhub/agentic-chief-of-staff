import React, { useId, useRef, useState } from 'react';

export interface TrendPoint {
  label: string;
  value: number;
}

interface TrendChartProps {
  points: TrendPoint[];
  accent?: string;
  height?: number;
  prefix?: string;
  suffix?: string;
}

const VW = 640; // viewBox width (px are scaled responsively)

const TrendChart: React.FC<TrendChartProps> = ({
  points,
  accent = 'var(--violet)',
  height = 210,
  prefix = '',
  suffix = ''
}) => {
  const gid = useId().replace(/:/g, '');
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  const padX = 10;
  const padTop = 18;
  const padBot = 26;
  const innerW = VW - padX * 2;
  const innerH = height - padTop - padBot;

  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const x = (i: number) =>
    padX + (points.length > 1 ? (innerW * i) / (points.length - 1) : innerW / 2);
  const y = (v: number) => padTop + innerH * (1 - (v - min) / span);

  const line = points
    .map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`)
    .join(' ');
  const area = `${line} L${x(points.length - 1).toFixed(1)},${(padTop + innerH).toFixed(
    1
  )} L${x(0).toFixed(1)},${(padTop + innerH).toFixed(1)} Z`;

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const rel = (e.clientX - rect.left) / rect.width;
    const idx = Math.max(0, Math.min(points.length - 1, Math.round(rel * (points.length - 1))));
    setHover(idx);
  };

  const fmt = (v: number) =>
    `${prefix}${v.toLocaleString(undefined, { maximumFractionDigits: 1 })}${suffix}`;

  const hp = hover !== null ? points[hover] : null;

  return (
    <div className="chart">
      {hp && (
        <div
          className="chart__tip"
          style={{ left: `${(hover! / (points.length - 1)) * 100}%` }}
        >
          <span className="chart__tip-v">{fmt(hp.value)}</span>
          <span className="chart__tip-l">{hp.label}</span>
        </div>
      )}
      <svg
        ref={svgRef}
        className="chart__svg"
        viewBox={`0 0 ${VW} ${height}`}
        preserveAspectRatio="none"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        role="img"
        aria-label="Trend chart"
      >
        <defs>
          <linearGradient id={`fill-${gid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.32" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>

        <path d={area} fill={`url(#fill-${gid})`} className="chart__area" />
        <path
          d={line}
          fill="none"
          stroke={accent}
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          className="chart__line"
          vectorEffect="non-scaling-stroke"
        />

        {hover !== null && (
          <g>
            <line
              x1={x(hover)}
              y1={padTop - 6}
              x2={x(hover)}
              y2={padTop + innerH}
              stroke="var(--hair-strong)"
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
            <circle cx={x(hover)} cy={y(points[hover].value)} r={4.5} fill={accent} />
            <circle
              cx={x(hover)}
              cy={y(points[hover].value)}
              r={8}
              fill={accent}
              opacity={0.18}
            />
          </g>
        )}
      </svg>
    </div>
  );
};

export default TrendChart;
