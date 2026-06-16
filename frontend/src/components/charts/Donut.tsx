import React, { useState } from 'react';

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

interface DonutProps {
  segments: DonutSegment[];
  size?: number;
  thickness?: number;
}

const Donut: React.FC<DonutProps> = ({ segments, size = 150, thickness = 16 }) => {
  const [active, setActive] = useState<number | null>(null);

  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const cx = size / 2;

  let acc = 0;
  const arcs = segments.map((seg, i) => {
    const frac = seg.value / total;
    const dash = frac * c;
    const arc = {
      seg,
      i,
      dash,
      gap: c - dash,
      offset: -acc * c,
      pct: Math.round(frac * 100)
    };
    acc += frac;
    return arc;
  });

  const center =
    active !== null
      ? { big: `${arcs[active].pct}%`, small: segments[active].label }
      : { big: String(total), small: total === 1 ? 'signal' : 'signals' };

  return (
    <div className="donut">
      <svg
        className="donut__svg"
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label="Signal mix"
      >
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke="var(--ring-track)"
          strokeWidth={thickness}
        />
        {arcs.map((a) => (
          <circle
            key={a.i}
            cx={cx}
            cy={cx}
            r={r}
            fill="none"
            stroke={a.seg.color}
            strokeWidth={active === a.i ? thickness + 4 : thickness}
            strokeDasharray={`${a.dash} ${a.gap}`}
            strokeDashoffset={a.offset}
            strokeLinecap="butt"
            transform={`rotate(-90 ${cx} ${cx})`}
            className="donut__arc"
            opacity={active === null || active === a.i ? 1 : 0.32}
            onMouseEnter={() => setActive(a.i)}
            onMouseLeave={() => setActive(null)}
          />
        ))}
      </svg>
      <div className="donut__center">
        <span className="donut__big">{center.big}</span>
        <span className="donut__small">{center.small}</span>
      </div>
    </div>
  );
};

export default Donut;
