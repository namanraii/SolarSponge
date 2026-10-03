export function BrandMark({ className = "w-9 h-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <radialGradient id="sunCore" cx="35%" cy="30%">
          <stop offset="0%" stopColor="#fff6d6" />
          <stop offset="55%" stopColor="#e8a317" />
          <stop offset="100%" stopColor="#c45c26" />
        </radialGradient>
      </defs>
      {Array.from({ length: 10 }).map((_, i) => {
        const a = (i * Math.PI * 2) / 10;
        const x1 = 32 + Math.cos(a) * 18;
        const y1 = 26 + Math.sin(a) * 18;
        const x2 = 32 + Math.cos(a) * 24;
        const y2 = 26 + Math.sin(a) * 24;
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#c48a1a" strokeWidth="2.2" strokeLinecap="round" />;
      })}
      <circle cx="32" cy="26" r="11" fill="url(#sunCore)" />
      <path
        d="M18 46c8-12 20-12 28 0-8 2-12 8-14 14-2-8-8-12-14-14z"
        fill="#3d6b45"
      />
      <path d="M32 46c2 4 4 8 4 14" stroke="#2a4f32" strokeWidth="1.4" fill="none" />
    </svg>
  );
}
