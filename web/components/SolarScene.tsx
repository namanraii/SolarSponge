export function PanelArray({ className = "" }: { className?: string }) {
  return (
    <div className={`h-56 rounded-3xl card overflow-hidden relative ${className}`} aria-hidden>
      <div
        className="absolute inset-0"
        style={{
          background: "radial-gradient(circle at 82% 12%, #f6d58a 0%, #ead7b4 48%, #d9c196 100%)",
        }}
      />
      <div className="sun-orb" style={{ top: "16px", right: "20px" }} />
      <div
        style={{
          position: "absolute",
          left: "9%",
          bottom: "18%",
          width: "82%",
          height: 118,
          display: "grid",
          gridTemplateColumns: "repeat(6, 1fr)",
          gridTemplateRows: "1fr 1fr",
          gap: 7,
          transform: "rotateX(58deg) rotateZ(-14deg)",
          transformOrigin: "center bottom",
        }}
      >
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            style={{
              borderRadius: 3,
              border: "1px solid rgba(255,255,255,0.45)",
              boxShadow: "0 10px 16px rgba(31,24,16,0.28)",
              background:
                "linear-gradient(135deg, rgba(255,255,255,0.32) 0 10%, transparent 18%), repeating-linear-gradient(90deg, #163052 0 23%, #c9a227 23% 25%), repeating-linear-gradient(0deg, #163052 0 45%, #c9a227 45% 48%)",
            }}
          />
        ))}
      </div>
      <p className="absolute left-3 bottom-3 text-[11px] uppercase tracking-[0.18em] text-ink/80 font-semibold bg-cream/70 rounded-full px-2 py-0.5">
        Feeder array
      </p>
    </div>
  );
}

export function SolarScene({ className = "" }: { className?: string }) {
  return (
    <div className={`relative h-56 md:h-64 ${className}`} aria-hidden>
      <div className="hero-tilt absolute inset-0 rounded-3xl overflow-hidden shadow-lift">
        <img
          src="/art/panel-3d.jpg"
          alt=""
          className="absolute inset-0 w-full h-full object-cover scale-[1.08]"
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-transparent to-sun/20" />
        <div className="scene-3d absolute inset-0">
          <div className="sun-orb" style={{ top: "16px", right: "18px" }} />
        </div>
        <p className="absolute left-3 bottom-3 text-[11px] uppercase tracking-[0.18em] text-ink/80 font-semibold bg-cream/75 rounded-full px-2 py-0.5">
          3D PV module
        </p>
      </div>
    </div>
  );
}
