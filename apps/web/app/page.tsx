import { HealthStatus } from "@/components/HealthStatus";

export default function HomePage() {
  return (
    <main>
      <p className="brand">LearnLens AI</p>
      <h1>Infrastructure connectivity</h1>
      <p className="lede">
        Minimal shell that polls the FastAPI readiness probe for Neon Postgres and
        Qdrant Cloud. No auth or business features in this phase.
      </p>
      <HealthStatus />
    </main>
  );
}
