import { Terminal } from "lucide-react"
import { ScrollReveal } from "./scroll-reveal"

export function HomeSection() {
  return (
    <section className="relative flex flex-col items-center bg-background px-4 py-32 text-center border-b-4 border-primary">
      <div className="absolute top-0 left-0 w-full h-8 bg-secondary border-b border-border flex items-center px-4 gap-2">
        <div className="w-3 h-3 rounded-full bg-destructive"></div>
        <div className="w-3 h-3 rounded-full bg-primary/50"></div>
        <div className="w-3 h-3 rounded-full bg-primary"></div>
      </div>

      <ScrollReveal delay={100}>
        <h2 className="mb-16 mt-8 max-w-2xl font-sans text-4xl font-black uppercase leading-tight text-foreground md:text-5xl lg:text-7xl">
          Three Commands.<br />
          <span className="text-primary text-3xl md:text-4xl lg:text-5xl">No cognitive overhead.</span>
        </h2>
      </ScrollReveal>

      <div className="grid w-full max-w-5xl gap-8 md:grid-cols-3">
        {[
          { cmd: "start", desc: "Begin tracking a session. Flow automatically injects project context into your AI rules files." },
          { cmd: "stop", desc: "End the session. Flow collates logs and git diffs, redacts secrets, and stores them in memory." },
          { cmd: "wake", desc: "Get a situational briefing on where you left off. Adapts detail based on absence length." },
        ].map((item, i) => (
          <ScrollReveal key={i} delay={(i + 1) * 150} className="h-full">
            <div className="flex flex-col items-start border-2 border-border bg-secondary/20 p-8 text-left transition-all hover:border-primary hover:-translate-y-2 h-full">
              <div className="mb-6 flex w-full items-center gap-3 border-b-2 border-border pb-4">
                <Terminal className="h-6 w-6 text-primary" />
                <span className="font-mono text-xl font-bold text-foreground">flow {item.cmd}</span>
              </div>
              <p className="font-mono text-sm leading-relaxed text-muted-foreground">
                {item.desc}
              </p>
            </div>
          </ScrollReveal>
        ))}
      </div>
    </section>
  )
}
