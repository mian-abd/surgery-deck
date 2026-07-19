// Live pipeline glue: capture webcam frames, stream JPEGs to /ws/ingest,
// and receive overlay + alert messages from /ws/session.

export interface Detection {
  bbox: [number, number, number, number]; // x1,y1,x2,y2 in pixels
  label: string;
  track_id?: number | null;
  conf: number;
  zone?: string | null;
  state?: string | null;
}

export interface HandPoint {
  x: number;
  y: number;
}

export interface FrameMessage {
  type: "frame" | "ack";
  camera_id?: string;
  w?: number;
  h?: number;
  frame?: number;
  fps?: number;
  image?: string; // data:image/jpeg;base64,... (relayed to viewers)
  detections?: Detection[];
  hands?: HandPoint[][];
  alerts?: unknown[];
}

export interface AlertMessage {
  type: "alert";
  event_type: string;
  severity: string;
  title: string;
  description?: string;
  confidence?: number;
  evidence_path?: string | null;
  occurred_at?: string;
  id?: string;
}

import { WS_BASE } from "./config";

const wsBase = () => WS_BASE;

export class LiveClient {
  private ingest?: WebSocket;
  private stream?: MediaStream;
  private timer?: number;
  private canvas = document.createElement("canvas");
  private lastFps = 0;

  constructor(
    private cameraId: string,
    private opts: {
      video: HTMLVideoElement;
      fps?: number;
      maxWidth?: number;
      onFrame?: (m: FrameMessage) => void;
    }
  ) {}

  get fps() {
    return this.lastFps;
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    this.opts.video.srcObject = this.stream;
    await this.opts.video.play();

    this.ingest = new WebSocket(`${wsBase()}/ws/ingest/${this.cameraId}`);
    this.ingest.binaryType = "arraybuffer";
    this.ingest.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data) as FrameMessage;
        if (m.fps) this.lastFps = m.fps;
        this.opts.onFrame?.(m);
      } catch {
        /* ignore */
      }
    };

    const interval = 1000 / (this.opts.fps ?? 8);
    await new Promise<void>((resolve) => {
      this.ingest!.onopen = () => resolve();
    });
    this.timer = window.setInterval(() => this.sendFrame(), interval);
  }

  private sendFrame() {
    if (!this.ingest || this.ingest.readyState !== WebSocket.OPEN) return;
    const v = this.opts.video;
    if (!v.videoWidth) return;
    const maxW = this.opts.maxWidth ?? 640;
    const scale = Math.min(1, maxW / v.videoWidth);
    const w = Math.round(v.videoWidth * scale);
    const h = Math.round(v.videoHeight * scale);
    this.canvas.width = w;
    this.canvas.height = h;
    const ctx = this.canvas.getContext("2d")!;
    ctx.drawImage(v, 0, 0, w, h);
    this.canvas.toBlob(
      (blob) => {
        if (blob && this.ingest?.readyState === WebSocket.OPEN)
          blob.arrayBuffer().then((buf) => this.ingest!.send(buf));
      },
      "image/jpeg",
      0.7
    );
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.ingest?.close();
    this.stream?.getTracks().forEach((t) => t.stop());
  }
}

// Dashboard-side receiver for alerts/frames broadcast to a whole session.
export class SessionSocket {
  private ws?: WebSocket;
  constructor(
    private sessionId: string,
    private handlers: {
      onFrame?: (m: FrameMessage) => void;
      onAlert?: (m: AlertMessage) => void;
    }
  ) {}

  start() {
    this.ws = new WebSocket(`${wsBase()}/ws/session/${this.sessionId}`);
    this.ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "alert") this.handlers.onAlert?.(m as AlertMessage);
        else if (m.type === "frame") this.handlers.onFrame?.(m as FrameMessage);
      } catch {
        /* ignore */
      }
    };
    // keep-alive ping
    this.ws.onopen = () => this.ws?.send("hello");
  }

  stop() {
    this.ws?.close();
  }
}
