import { fetchHealth } from "@/lib/api/health";

export async function BackendStatus() {
  const health = await fetchHealth();
  const isOnline = health?.status === "ok";

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
      <p className="text-sm font-medium text-muted-foreground">Backend Status</p>
      <p className="mt-2 text-lg font-semibold text-foreground">
        {isOnline ? (
          <>
            <span aria-hidden="true">🟢</span> Online
          </>
        ) : (
          <>
            <span aria-hidden="true">🔴</span> Offline
          </>
        )}
      </p>
      {health?.service && (
        <p className="mt-1 text-sm text-muted-foreground">{health.service}</p>
      )}
    </div>
  );
}
