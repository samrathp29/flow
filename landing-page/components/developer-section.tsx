import { ScrollReveal } from "./scroll-reveal"
import { ClaudeLogo, CursorLogo, CodexLogo, GitLogo } from "./logos"

export function DeveloperSection() {
  return (
    <section className="relative flex flex-col items-center border-b-4 border-primary bg-secondary px-4 py-32 text-center">
      <ScrollReveal delay={100} className="mb-16">
        <h2 className="mb-4 font-sans text-4xl font-black uppercase text-foreground md:text-5xl lg:text-6xl">
          Works with your stack
        </h2>
        <p className="font-mono text-sm uppercase tracking-widest text-muted-foreground">
          No extra plugins required.
        </p>
      </ScrollReveal>

      <div className="grid w-full max-w-4xl gap-4 sm:grid-cols-2 md:grid-cols-4">
        {[
          { icon: <ClaudeLogo className="h-10 w-10 text-foreground mb-4" />, status: "Supported" },
          { icon: <CursorLogo className="h-10 w-10 text-foreground mb-4" />, status: "Supported" },
          { icon: <CodexLogo className="h-10 w-10 text-foreground mb-4" />, status: "Supported" },
          { icon: <GitLogo className="h-10 w-10 text-foreground mb-4" />, status: "Supported" },
        ].map((tool, i) => (
          <ScrollReveal key={i} delay={(i + 1) * 100} className="h-full">
            <div className="flex flex-col items-center border-2 border-border bg-background p-6 transition-transform hover:-translate-y-1 hover:border-primary h-full">
              {tool.icon}
              <div className={`mt-auto inline-flex w-max items-center px-2 py-1 font-mono text-xs uppercase tracking-wider ${tool.status === "Supported" ? "bg-primary/20 text-primary border border-primary" : "bg-muted text-muted-foreground border border-muted-foreground"}`}>
                {tool.status}
              </div>
            </div>
          </ScrollReveal>
        ))}
      </div>
    </section>
  )
}
