import { ScrollReveal } from "./scroll-reveal"
import { Bot, Zap, ArrowRight } from "lucide-react"

export function ContextInjectionSection() {
    return (
        <section className="relative flex flex-col items-center border-b-4 border-primary bg-background px-4 py-32 overflow-hidden">
            {/* Background decoration */}
            <div className="absolute top-0 right-0 h-64 w-64 translate-x-32 -translate-y-32 border-4 border-primary/10 rotate-45" />
            <div className="absolute bottom-0 left-0 h-64 w-64 -translate-x-32 translate-y-32 border-4 border-primary/10 rotate-12" />

            <div className="max-w-6xl w-full grid md:grid-cols-2 gap-16 items-center">
                <div className="text-left">
                    <ScrollReveal delay={100}>
                        <div className="inline-flex items-center gap-2 bg-primary text-primary-foreground font-mono text-xs uppercase tracking-widest px-3 py-1 mb-8">
                            <Zap className="h-3 w-3" />
                            Proactive Injection
                        </div>
                    </ScrollReveal>

                    <ScrollReveal delay={200}>
                        <h2 className="mb-8 font-sans text-5xl font-black uppercase leading-tight text-foreground lg:text-7xl">
                            Zero-Shot <br />
                            <span className="text-primary">Recall.</span>
                        </h2>
                    </ScrollReveal>

                    <ScrollReveal delay={300}>
                        <p className="mb-8 font-mono text-base leading-relaxed text-muted-foreground">
                            On <code className="text-foreground font-bold">flow start</code>, Flow queries your project memory and injects a surgical 300-token context block into your AI tool's rules.
                        </p>

                        <ul className="space-y-4 mb-10">
                            {[
                                "CLAUDE.md for Claude Code",
                                ".cursor/rules/flow.mdc for Cursor",
                                "AGENTS.md for Codex"
                            ].map((text, i) => (
                                <li key={i} className="flex items-center gap-3 font-mono text-sm text-foreground">
                                    <ArrowRight className="h-4 w-4 text-primary" />
                                    {text}
                                </li>
                            ))}
                        </ul>

                        <p className="font-mono text-sm text-muted-foreground italic">
                            "Your agent arrives with full project technical context before you even send the first prompt."
                        </p>
                    </ScrollReveal>
                </div>

                <div className="relative">
                    <ScrollReveal delay={400}>
                        <div className="border-4 border-primary bg-secondary p-1 rotate-1 shadow-[12px_12px_0_0_hsl(var(--primary))]">
                            <div className="bg-background border-2 border-primary p-6 font-mono text-xs md:text-sm">
                                <div className="flex items-center gap-2 mb-4 text-primary border-b border-border pb-2">
                                    <Bot className="h-4 w-4" />
                                    <span>CLAUDE.md</span>
                                </div>
                                <div className="space-y-4 text-muted-foreground">
                                    <div>
                                        <span className="text-foreground font-bold">**Current State:**</span>
                                        <p>Refactoring auth middleware to support JWT rotation. Middleware logic in `/lib/auth.ts` is partially updated.</p>
                                    </div>
                                    <div>
                                        <span className="text-foreground font-bold">**Decisions:**</span>
                                        <p>Switched from Redis to local cache for session IDs to reduce latency. Rejected DB-level session tracking.</p>
                                    </div>
                                    <div>
                                        <span className="text-foreground font-bold">**Dead Ends:**</span>
                                        <p>Do not use `auth-v1` patterns; they are deprecated and will break the current migration.</p>
                                    </div>
                                    <div className="flex items-center gap-2 text-primary font-bold">
                                        <span>NEXT:</span>
                                        <span>Complete the test suite in /tests/auth.test.ts</span>
                                    </div>
                                    <div className="text-[10px] opacity-50 border-t border-border pt-2">
                                        &lt;!-- flow:start --&gt; | 284 tokens | &lt;!-- flow:end --&gt;
                                    </div>
                                </div>
                            </div>
                        </div>
                    </ScrollReveal>
                </div>
            </div>
        </section>
    )
}
