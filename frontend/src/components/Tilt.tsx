import React, { useRef } from 'react';

interface TiltProps {
  className?: string;
  max?: number; // max rotation in degrees
  lift?: number; // px the element rises on hover
  scale?: number;
  children: React.ReactNode;
}

const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Cursor-tracking 3D tilt + pop-out + spotlight.
 * Sets --mx/--my (pointer position) and --tilt-on for the CSS spotlight,
 * and drives a perspective transform. rAF-batched; transform/opacity only.
 */
const Tilt: React.FC<TiltProps> = ({
  className = '',
  max = 5,
  lift = 6,
  scale = 1.015,
  children
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useRef<number | null>(null);

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduceMotion) return;
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    if (frame.current) cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const rx = (0.5 - py) * max * 2;
      const ry = (px - 0.5) * max * 2;
      el.style.transform = `perspective(1000px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(
        2
      )}deg) translateY(-${lift}px) scale(${scale})`;
      el.style.setProperty('--mx', `${(px * 100).toFixed(1)}%`);
      el.style.setProperty('--my', `${(py * 100).toFixed(1)}%`);
      el.style.setProperty('--tilt-on', '1');
    });
  };

  const onLeave = () => {
    const el = ref.current;
    if (!el) return;
    if (frame.current) cancelAnimationFrame(frame.current);
    el.style.transform = '';
    el.style.setProperty('--tilt-on', '0');
  };

  return (
    <div ref={ref} className={`tilt ${className}`} onMouseMove={onMove} onMouseLeave={onLeave}>
      {children}
    </div>
  );
};

export default Tilt;
