export type RunStreamEvent =
  | { type: 'log'; data: string; raw: MessageEvent }
  | { type: 'status'; data: unknown; raw: MessageEvent }
  | { type: 'heartbeat'; data: string; raw: MessageEvent }
  | { type: 'error'; data: Event };

export type RunStreamHandlers = {
  onEvent: (event: RunStreamEvent) => void;
};

function parseStatus(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

export function openRunLogStream(runId: string | number, handlers: RunStreamHandlers): EventSource {
  const source = new EventSource(`/api/runs/${runId}/logs/stream?tail_lines=800`);

  source.addEventListener('log', (raw) => {
    handlers.onEvent({ type: 'log', data: raw.data, raw });
  });

  source.addEventListener('status', (raw) => {
    handlers.onEvent({ type: 'status', data: parseStatus(raw.data), raw });
  });

  source.addEventListener('heartbeat', (raw) => {
    handlers.onEvent({ type: 'heartbeat', data: raw.data, raw });
  });

  source.onerror = (event) => {
    handlers.onEvent({ type: 'error', data: event });
  };

  return source;
}
