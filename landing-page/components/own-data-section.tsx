import { ScrollReveal } from "./scroll-reveal"

export function OwnDataSection() {
  return (
    <section className="relative flex flex-col md:flex-row border-b-4 border-primary bg-background">
      <div className="flex flex-1 flex-col justify-center border-r-0 md:border-r-2 border-border p-12 md:p-24 overflow-hidden">
        <ScrollReveal delay={100}>
          <div className="inline-block bg-primary text-primary-foreground font-mono text-xs uppercase tracking-widest px-2 py-1 mb-6 w-max">
            Privacy First
          </div>
        </ScrollReveal>
        <ScrollReveal delay={200}>
          <h2 className="mb-6 max-w-lg font-sans text-4xl font-black uppercase leading-tight text-foreground md:text-5xl lg:text-6xl">
            Stored Locally.<br />
            Stay Secure.
          </h2>
        </ScrollReveal>
        <ScrollReveal delay={300}>
          <p className="mb-8 max-w-md font-mono text-sm leading-relaxed text-muted-foreground">
            Your code never leaves your machine. Flow runs locally and stores distilled context using Mem0 + Qdrant vector memory. Local storage, zero telemetry.
          </p>
        </ScrollReveal>
      </div>

      <div className="flex flex-1 items-center justify-center bg-secondary/30 p-12 md:p-24">
        <ScrollReveal delay={300} className="w-full max-w-md">
          <div className="w-full max-w-md border-2 border-primary bg-background p-6 font-mono text-sm shadow-[8px_8px_0_0_hsl(var(--primary))]">
            <div className="mb-4 flex items-center justify-between border-b-2 border-border pb-4">
              <span className="text-muted-foreground">state.json</span>
              <span className="text-primary text-xs uppercase">Local Vector DB</span>
            </div>
            <pre className="text-muted-foreground overflow-x-auto text-[10px] md:text-sm">
              <code>{`{
  "project_name": "auth-service",
  "project_path": "/home/dev/auth-service",
  "project_id": "auth-service-a1b2c3d4",
  "started_at": "2025-11-05T10:00:00Z",
  "pid": 48210,
  "base_commit": "7f2d1a3..."
}`}</code>
            </pre>
          </div>
        </ScrollReveal>
      </div>
    </section>
  )
}
