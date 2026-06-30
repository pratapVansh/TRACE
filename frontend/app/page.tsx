import { BackendStatus } from "@/components/common/backend-status";

export default function Home() {
  return (
    <div className="flex min-h-full flex-1 flex-col items-center justify-center bg-background px-6 py-16">
      <main className="flex w-full max-w-lg flex-col items-center gap-8 text-center">
        <div className="space-y-3">
          <h1 className="text-4xl font-bold tracking-tight text-foreground">
            TRACE
          </h1>
          <p className="text-lg text-muted-foreground">
            Industrial Knowledge Intelligence Platform
          </p>
        </div>

        <div className="w-full">
          <BackendStatus />
        </div>
      </main>
    </div>
  );
}
