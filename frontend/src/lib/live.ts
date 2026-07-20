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

// Detection overlays arrive on their own channel (decoupled from the raw frame
// relay) so smooth video isn't gated on CPU inference speed.
export interface DetectionsMessage {
  type: "detections";
  camera_id?: string;
  detections?: Detection[];
  hands?: HandPoint[][];
}

// Gemini's narration + visual second opinion for one safety event.
export interface GeminiInsight {
  explanation?: string;
  recommended_action?: string;
  agrees?: boolean;
  verification_reason?: string;
  visual_confidence?: number;
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
  gemini?: GeminiInsight; // filled in later via event_update
}

// Arrives a beat after the alert, once Gemini has analysed the evidence frame.
export interface EventUpdateMessage {
  type: "event_update";
  id: string;
  gemini: GeminiInsight;
}

import { WS_BASE } from "./config";

const wsBase = () => WS_BASE;

export class LiveClient {
  private ingest?: WebSocket;
  private stream?: MediaStream;
  private objectUrl?: string;
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

  // Live webcam source.
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    this.opts.video.srcObject = this.stream;
    await this.opts.video.play();
    await this.run();
  }

  // Uploaded-video source: stream a local file through the exact same pipeline.
  async startFile(file: File, opts?: { loop?: boolean; muted?: boolean }) {
    const v = this.opts.video;
    this.objectUrl = URL.createObjectURL(file);
    v.srcObject = null;
    v.src = this.objectUrl;
    v.loop = opts?.loop ?? true;
    v.muted = opts?.muted ?? true;
    await new Promise<void>((resolve, reject) => {
      v.onloadeddata = () => resolve();
      v.onerror = () => reject(new Error("could not load video file"));
    });
    await v.play();
    await this.run();
  }

  private async run() {
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

    const interval = 1000 / (this.opts.fps ?? 15);
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
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = undefined;
    }
    const v = this.opts.video;
    v.pause?.();
    v.removeAttribute("src");
    v.srcObject = null;
  }
}

// Dashboard-side receiver for alerts/frames broadcast to a whole session.
export class SessionSocket {
  private ws?: WebSocket;
  private closed = false;
  private retry = 0;
  constructor(
    private sessionId: string,
    private handlers: {
      onFrame?: (m: FrameMessage) => void;
      onDetections?: (m: DetectionsMessage) => void;
      onAlert?: (m: AlertMessage) => void;
      onEventUpdate?: (m: EventUpdateMessage) => void;
      onStatus?: (connected: boolean) => void;
    }
  ) {}

  start() {
    this.closed = false;
    this.connect();
  }

  private connect() {
    this.ws = new WebSocket(`${wsBase()}/ws/session/${this.sessionId}`);
    this.ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === "alert") this.handlers.onAlert?.(m as AlertMessage);
        else if (m.type === "frame") this.handlers.onFrame?.(m as FrameMessage);
        else if (m.type === "detections")
          this.handlers.onDetections?.(m as DetectionsMessage);
        else if (m.type === "event_update")
          this.handlers.onEventUpdate?.(m as EventUpdateMessage);
      } catch {
        /* ignore */
      }
    };
    this.ws.onopen = () => {
      this.retry = 0;
      this.handlers.onStatus?.(true);
      this.ws?.send("hello"); // keep-alive ping
    };
    this.ws.onclose = () => {
      this.handlers.onStatus?.(false);
      if (this.closed) return;
      // exponential-ish backoff reconnect so a viewer survives backend restarts
      const delay = Math.min(5000, 500 * 2 ** this.retry++);
      setTimeout(() => !this.closed && this.connect(), delay);
    };
  }

  stop() {
    this.closed = true;
    this.ws?.close();
  }
}
