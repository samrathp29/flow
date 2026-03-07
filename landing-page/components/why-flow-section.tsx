import { ScrollReveal } from "./scroll-reveal"
import { X, Check, Brain } from "lucide-react"

export function WhyFlowSection() {
    return (
        <section className="relative flex flex-col items-center border-b-4 border-primary bg-background px-4 py-32 overflow-hidden">
            <div className="absolute top-0 left-0 h-48 w-48 -translate-x-24 -translate-y-24 border-4 border-primary/10 rotate-12" />
            <div className="absolute bottom-0 right-0 h-48 w-48 translate-x-24 translate-y-24 border-4 border-primary/10 -rotate-12" />

            <ScrollReveal delay={100}>
                <div className="inline-flex items-center gap-2 bg-primary text-primary-foreground font-mono text-xs uppercase tracking-widest px-3 py-1 mb-8">
                    <Brain className="h-3 w-3" />
                    Memory vs. Scanning
                </div>
            </ScrollReveal>

            <ScrollReveal delay={200}>
                <h2 className="mb-6 max-w-3xl text-center font-sans text-4xl font-black uppercase leading-tight text-foreground md:text-5xl lg:text-7xl">
                    Why Not Just<br />
                    <span className="text-primary">Ask Your AI?</span>
                </h2>
            </ScrollReveal>

            <ScrollReveal delay={300}>
                <p className="mb-16 max-w-2xl text-center font-mono text-base leading-relaxed text-muted-foreground">
                    &ldquo;Can&rsquo;t I just ask Claude Code to look at my codebase and tell me where I left off?&rdquo; You can. But what&rsquo;s in your code is not the same as what you were doing.
                </p>
            </ScrollReveal>

            <div className="grid w-full max-w-5xl gap-8 md:grid-cols-2">
                {[
                    {
                        title: "Dead ends vanish from code",
                        body: "If you tried WebSockets and switched to SSE, the codebase only shows SSE. Your next AI session will suggest WebSockets again. Flow remembers what failed and why.",
                        type: "problem" as const,
                    },
                    {
                        title: "Flow tracks decisions, not just code",
                        body: "Code is the output of decisions. Flow stores the decisions themselves \u2014 why you chose Qdrant over Pinecone, why the auth flow is a workaround, what\u2019s still unresolved.",
                        type: "solution" as const,
                    },
                    {
                        title: "AI tools are stateless",
                        body: "Claude Code, Cursor, and Codex start every session with zero context about prior sessions. They can read files but can\u2019t know what you decided yesterday.",
                        type: "problem" as const,
                    },
                    {
                        title: "Flow injects context proactively",
                        body: "Before you send your first prompt, Flow has already queried your memory and injected what\u2019s in progress, what failed, and what comes next into your agent\u2019s rules file.",
                        type: "solution" as const,
                    },
                ].map((item, i) => (
                    <ScrollReveal key={i} delay={(i + 1) * 100} className="h-full">
                        <div className={`flex flex-col border-2 p-8 text-left transition-all hover:-translate-y-1 h-full ${item.type === "problem" ? "border-border bg-secondary/20 hover:border-muted-foreground" : "border-primary bg-primary/5 hover:border-primary"}`}>
                            <div className={`mb-4 flex items-center gap-3 font-mono text-sm font-bold uppercase tracking-widest ${item.type === "problem" ? "text-muted-foreground" : "text-primary"}`}>
                                {item.type === "problem" ? <X className="h-4 w-4" /> : <Check className="h-4 w-4" />}
                                {item.type === "problem" ? "Codebase scan" : "Flow + Mem0"}
                            </div>
                            <h3 className="mb-3 font-sans text-xl font-bold text-foreground">
                                {item.title}
                            </h3>
                            <p className="font-mono text-sm leading-relaxed text-muted-foreground">
                                {item.body}
                            </p>
                        </div>
                    </ScrollReveal>
                ))}
            </div>

            <ScrollReveal delay={600} className="mt-16 w-full max-w-3xl">
                <div className="border-2 border-primary bg-primary/5 p-8 text-center">
                    <p className="font-mono text-sm leading-relaxed text-foreground">
                        Your codebase tells an AI agent <span className="font-bold text-primary">what your code does</span>.
                        Flow tells it <span className="font-bold text-primary">what you were doing, what you decided, what didn&rsquo;t work, and what to do next</span>.
                    </p>
                </div>
            </ScrollReveal>
        </section>
    )
}
