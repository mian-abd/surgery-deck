import { useEffect, useRef } from "react";
import { Detection, HandPoint } from "../lib/live";
import { Zone } from "../lib/api";

interface Props {
  frame: string | null; // data URL of the latest relayed JPEG
  detections: Detection[];
  hands: HandPoint[][];
  zones: Zone[];
  editing?: boolean;
  draftPolygon?: number[][];
  onAddPoint?: (x: number, y: number) => void;
}

const ZONE_COLORS: Record<string, string> = {
  sterile: "#22c55e",
  nonsterile: "#ef4444",
  tray: "#3b82f6",
  sink: "#06b6d4",
  patient: "#a855f7",
  entry: "#eab308",
};

export default function ViewerStage({
  frame,
  detections,
  hands,
  zones,
  editing,
  draftPolygon,
  onAddPoint,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(new Image());
  const readyRef = useRef(false);

  // keep the latest frame decoded into an Image
  useEffect(() => {
    if (!frame) return;
    const img = imgRef.current;
    img.onload = () => (readyRef.current = true);
    img.src = frame;
  }, [frame]);

  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const img = imgRef.current;
      if (canvas && readyRef.current && img.naturalWidth) {
        const W = img.naturalWidth;
        const H = img.naturalHeight;
        if (canvas.width !== W) canvas.width = W;
        if (canvas.height !== H) canvas.height = H;
        const ctx = canvas.getContext("2d")!;
        ctx.drawImage(img, 0, 0, W, H);

        const drawPoly = (poly: number[][], color: string, label?: string) => {
          if (poly.length < 2) return;
          ctx.beginPath();
          poly.forEach(([x, y], i) => {
            const px = x * W;
            const py = y * H;
            i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
          });
          if (poly.length > 2) ctx.closePath();
          ctx.lineWidth = 2;
          ctx.strokeStyle = color;
          ctx.fillStyle = color + "22";
          if (poly.length > 2) ctx.fill();
          ctx.stroke();
          if (label && poly[0]) {
            ctx.fillStyle = color;
            ctx.font = "600 14px system-ui";
            ctx.fillText(label, poly[0][0] * W + 4, poly[0][1] * H - 6);
          }
        };

        zones.forEach((z) =>
          drawPoly(z.polygon, ZONE_COLORS[z.zone_type] || "#64748b", z.name)
        );
        if (draftPolygon && draftPolygon.length) {
          drawPoly(draftPolygon, "#f8fafc", "drawing…");
          draftPolygon.forEach(([x, y]) => {
            ctx.beginPath();
            ctx.arc(x * W, y * H, 4, 0, Math.PI * 2);
            ctx.fillStyle = "#f8fafc";
            ctx.fill();
          });
        }

        detections.forEach((d) => {
          const [x1, y1, x2, y2] = d.bbox;
          const critical = d.state === "potentially_contaminated";
          ctx.lineWidth = 2;
          ctx.strokeStyle = critical ? "#ef4444" : "#38bdf8";
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
          const tag = `${d.label}${d.track_id != null ? " #" + d.track_id : ""}`;
          ctx.font = "600 13px system-ui";
          const tw = ctx.measureText(tag).width + 8;
          ctx.fillStyle = critical ? "#ef4444" : "#38bdf8";
          ctx.fillRect(x1, Math.max(0, y1 - 18), tw, 18);
          ctx.fillStyle = "#04121f";
          ctx.fillText(tag, x1 + 4, Math.max(11, y1 - 5));
        });

        ctx.fillStyle = "#f472b6";
        hands.forEach((pts) =>
          pts.forEach((p) => {
            ctx.beginPath();
            ctx.arc(p.x * W, p.y * H, 3, 0, Math.PI * 2);
            ctx.fill();
          })
        );
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [detections, hands, zones, draftPolygon]);

  const handleClick = (e: React.MouseEvent) => {
    if (!editing || !onAddPoint) return;
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    onAddPoint((e.clientX - rect.left) / rect.width, (e.clientY - rect.top) / rect.height);
  };

  return (
    <div className="relative bg-black rounded-xl overflow-hidden border border-edge aspect-video">
      <canvas
        ref={canvasRef}
        onClick={handleClick}
        className={`w-full h-full object-contain ${editing ? "cursor-crosshair" : ""}`}
      />
      {!frame && (
        <div className="absolute inset-0 grid place-items-center text-sm text-slate-500">
          Waiting for camera feed…
        </div>
      )}
    </div>
  );
}
