import { useCallback, useEffect, useRef, useState } from "react";
import type { VHEState } from "../types/api";

const INITIAL_STATE: VHEState = {
  connected: false,
  mode: "paper",
  source: "simulated",
  phase: 0,
  server_time: "",
  portfolio: {
    cash: 0,
    equity: 0,
    gross_exposure: 0,
    gross_exposure_pct: 0,
    positions: {},
  },
  controls: {
    kill_switch: false,
    automation_paused: false,
    last_risk_reject: null,
    kill_switch_reason: null,
  },
  quotes: {},
  plans: {},
  fills: [],
  events: [],
};

export function useWebSocket() {
  const [state, setState] = useState<VHEState>(INITIAL_STATE);
  const ws = useRef<WebSocket | null>(null);
  const destroyed = useRef(false);

  const connect = useCallback(() => {
    if (destroyed.current) return;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${proto}://${window.location.host}/ws/state`);
    ws.current = socket;

    socket.onmessage = (ev) => {
      try {
        setState(JSON.parse(ev.data) as VHEState);
      } catch {
        // ignore malformed frames
      }
    };

    socket.onclose = () => {
      if (destroyed.current) return;
      setState((prev) => ({ ...prev, connected: false }));
      setTimeout(connect, 1200);
    };

    socket.onerror = () => socket.close();
  }, []);

  useEffect(() => {
    destroyed.current = false;
    connect();
    return () => {
      destroyed.current = true;
      ws.current?.close();
    };
  }, [connect]);

  const postControl = useCallback(async (endpoint: string) => {
    const resp = await fetch(endpoint, { method: "POST" });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ detail: "Request failed" }));
      throw new Error((body as { detail?: string }).detail ?? "Request failed");
    }
    setState(await resp.json() as VHEState);
  }, []);

  return { state, postControl };
}
