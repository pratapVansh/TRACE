export interface ComponentHealth {
  /** ok | degraded | unavailable | off */
  status: string;
  /** live | startup — a startup reading may be stale. */
  checked: string;
  required: boolean;
  detail: string | null;
}

export interface HealthResponse {
  /** ok | degraded | unavailable */
  status: string;
  service: string;
  /** Names of components that are not ok. Empty when healthy. */
  degraded: string[];
  components: Record<string, ComponentHealth>;
}
