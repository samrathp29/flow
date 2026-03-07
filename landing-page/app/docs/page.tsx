import { Navbar } from "@/components/navbar"
import { Footer } from "@/components/footer"
import { ScrollReveal } from "@/components/scroll-reveal"
import { Terminal, ArrowLeft } from "lucide-react"
import Link from "next/link"

export default function DocsPage() {
    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col">
            <Navbar />

            <main className="flex-1 mt-20 md:mt-24 px-6 md:px-12 py-12 pb-32 max-w-4xl mx-auto w-full">
                <ScrollReveal delay={100}>
                    <div className="mb-12 border-b-4 border-primary pb-8">
                        <Link href="/" className="inline-flex items-center gap-2 mb-8 font-mono text-sm uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors">
                            <ArrowLeft className="h-4 w-4" />
                            Back to Home
                        </Link>
                        <h1 className="font-sans text-5xl md:text-7xl font-black uppercase tracking-tighter mb-6">
                            Documentation
                        </h1>
                        <p className="font-mono text-base md:text-lg leading-relaxed text-muted-foreground">
                            Flow is a CLI that watches your coding session and tells you where you left off. Reclaim your context and reach flow state instantly. It tracks your AI tool chat logs (Claude Code, Cursor, Codex) and git activity, distilling it into concise project context using an LLM and Mem0.
                        </p>
                    </div>
                </ScrollReveal>

                <div className="space-y-16">
                    <ScrollReveal delay={200}>
                        <section>
                            <h2 className="font-sans text-3xl font-bold uppercase mb-6 flex items-center gap-3">
                                <Terminal className="h-6 w-6 text-primary" />
                                Installation
                            </h2>
                            <div className="bg-secondary/30 border-2 border-border p-6 mb-4 font-mono text-sm leading-relaxed">
                                <p className="mb-4">Install the package from the project root:</p>
                                <div className="bg-background border-2 border-border p-4 shadow-[4px_4px_0_0_hsl(var(--primary))]">
                                    <code className="text-primary whitespace-pre-wrap">
                                        git clone https://github.com/samrathp29/flow.git{"\n"}
                                        cd flow{"\n"}
                                        pip install -e .
                                    </code>
                                </div>
                            </div>
                        </section>
                    </ScrollReveal>

                    <ScrollReveal delay={300}>
                        <section>
                            <h2 className="font-sans text-3xl font-bold uppercase mb-6 flex items-center gap-3">
                                <Terminal className="h-6 w-6 text-primary" />
                                Setup
                            </h2>
                            <div className="bg-secondary/30 border-2 border-border p-6 mb-4 font-mono text-sm leading-relaxed">
                                <p className="mb-4">Run the initialization command to configure your LLM provider and API key. This interactive prompt will set up your provider (Anthropic or OpenAI), default models, and initialize the local storage directory.</p>
                                <div className="bg-background border-2 border-border p-4 shadow-[4px_4px_0_0_hsl(var(--primary))]">
                                    <code className="text-primary">flow init</code>
                                </div>
                            </div>
                        </section>
                    </ScrollReveal>

                    <ScrollReveal delay={400}>
                        <section>
                            <h2 className="font-sans text-3xl font-bold uppercase mb-6 flex items-center gap-3">
                                <Terminal className="h-6 w-6 text-primary" />
                                Usage
                            </h2>
                            <div className="bg-secondary/30 border-2 border-border p-6 font-mono text-sm leading-relaxed space-y-12">
                                <p>Flow operates alongside your normal git workflow.</p>

                                <div>
                                    <h3 className="text-xl font-bold text-foreground mb-4 uppercase">Start a Session</h3>
                                    <p className="mb-4 text-muted-foreground">Begin tracking a coding session in your current git repository.</p>
                                    <div className="bg-background border-2 border-border p-4 shadow-[4px_4px_0_0_hsl(var(--primary))]">
                                        <code className="text-primary">flow start</code>
                                    </div>
                                </div>

                                <div>
                                    <h3 className="text-xl font-bold text-foreground mb-4 uppercase">Stop a Session</h3>
                                    <p className="mb-4 text-muted-foreground">End the current session. Flow collates logs from Claude Code, Cursor, and Codex, summarizes git diffs with an LLM, redacts secrets, and stores the result as chunked messages in local vector memory via Mem0.</p>
                                    <div className="bg-background border-2 border-border p-4 shadow-[4px_4px_0_0_hsl(var(--primary))]">
                                        <code className="text-primary">flow stop</code>
                                    </div>
                                </div>

                                <div>
                                    <h3 className="text-xl font-bold text-foreground mb-4 uppercase">Wake</h3>
                                    <p className="mb-4 text-muted-foreground">Get a situational briefing on what you were last working on in this project.</p>
                                    <div className="bg-background border-2 border-border p-4 shadow-[4px_4px_0_0_hsl(var(--primary))]">
                                        <code className="text-primary">flow wake</code>
                                    </div>
                                </div>
                            </div>
                        </section>
                    </ScrollReveal>
                </div>
            </main>

            <Footer />
        </div>
    )
}
