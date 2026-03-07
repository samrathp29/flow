"use client"

import { useEffect, useState, useRef, useCallback } from "react"
import { Terminal, Play, Square, Sun, ChevronRight } from "lucide-react"
import { ScrollReveal } from "./scroll-reveal"

interface Step {
    label: string
    cmd: string
    lines: { text: string; delay: number; style?: string }[]
    duration: number
}

const STEPS: Step[] = [
    {
        label: "Start",
        cmd: "flow start",
        lines: [
            { text: "$ flow start", delay: 0, style: "text-primary font-bold" },
            { text: "", delay: 200 },
            { text: "\u25B6 Session started \u2014 watching auth-service", delay: 400 },
            { text: "", delay: 600 },
            { text: "  Searching project memory...", delay: 800, style: "text-muted-foreground" },
            { text: "  \u2713 3 queries \u2192 9 memories \u2192 6 unique", delay: 1400, style: "text-muted-foreground" },
            { text: "  \u2713 Compressed to 284 tokens", delay: 1800, style: "text-muted-foreground" },
            { text: "", delay: 2000 },
            { text: "\u21BB Context injected into CLAUDE.md", delay: 2200, style: "text-primary" },
            { text: "", delay: 2600 },
            { text: "  \u250C\u2500\u2500 CLAUDE.md \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510", delay: 2800, style: "text-border" },
            { text: "  \u2502 **Current state:** Refactoring auth    \u2502", delay: 3000, style: "text-muted-foreground" },
            { text: "  \u2502 middleware for JWT rotation. /lib/auth  \u2502", delay: 3000, style: "text-muted-foreground" },
            { text: "  \u2502 partially updated.                     \u2502", delay: 3000, style: "text-muted-foreground" },
            { text: "  \u2502 **Dead ends:** Do not use auth-v1      \u2502", delay: 3200, style: "text-destructive/70" },
            { text: "  \u2502 patterns \u2014 deprecated, breaks migration\u2502", delay: 3200, style: "text-destructive/70" },
            { text: "  \u2502 **Next:** Complete test suite in        \u2502", delay: 3400, style: "text-primary/70" },
            { text: "  \u2502 /tests/auth.test.ts                    \u2502", delay: 3400, style: "text-primary/70" },
            { text: "  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518", delay: 3400, style: "text-border" },
        ],
        duration: 5000,
    },
    {
        label: "Code",
        cmd: "you work normally",
        lines: [
            { text: "$ git commit -m \"add JWT rotation middleware\"", delay: 0, style: "text-primary font-bold" },
            { text: "[main 3f8a1b2] add JWT rotation middleware", delay: 400 },
            { text: " 3 files changed, 147 insertions(+), 23 deletions(-)", delay: 600, style: "text-muted-foreground" },
            { text: "", delay: 1000 },
            { text: "$ git commit -m \"fix: exclude /auth/refresh from middleware\"", delay: 1200, style: "text-primary font-bold" },
            { text: "[main 9c4d2e7] fix: exclude /auth/refresh from middleware", delay: 1600 },
            { text: " 1 file changed, 8 insertions(+), 2 deletions(-)", delay: 1800, style: "text-muted-foreground" },
            { text: "", delay: 2200 },
            { text: "$ git commit -m \"test: auth middleware rotation tests\"", delay: 2400, style: "text-primary font-bold" },
            { text: "[main e1f5a83] test: auth middleware rotation tests", delay: 2800 },
            { text: " 2 files changed, 89 insertions(+)", delay: 3000, style: "text-muted-foreground" },
            { text: "", delay: 3400 },
            { text: "(flow) $", delay: 3600, style: "text-primary animate-pulse" },
        ],
        duration: 5000,
    },
    {
        label: "Stop",
        cmd: "flow stop",
        lines: [
            { text: "$ flow stop", delay: 0, style: "text-primary font-bold" },
            { text: "", delay: 200 },
            { text: "\u2823 Processing session...", delay: 400 },
            { text: "", delay: 800 },
            { text: "  Parsing Claude Code logs      \u2713  42 turns", delay: 1000, style: "text-muted-foreground" },
            { text: "  Deduplicating                 \u2713  38 unique", delay: 1400, style: "text-muted-foreground" },
            { text: "  git diff (3f8a1b2..HEAD)      \u2713  244 lines", delay: 1800, style: "text-muted-foreground" },
            { text: "  LLM diff summarization        \u2713", delay: 2200, style: "text-muted-foreground" },
            { text: "  Redacting secrets             \u2713  2 keys masked", delay: 2600, style: "text-muted-foreground" },
            { text: "  Chunking (4 chunks \u00D7 10 msgs) \u2713", delay: 3000, style: "text-muted-foreground" },
            { text: "", delay: 3200 },
            { text: "  mem0: extracting facts...", delay: 3400, style: "text-muted-foreground" },
            { text: "    + \"COMPLETED: JWT rotation middleware with /auth/refresh exclusion\"", delay: 3800, style: "text-primary/80" },
            { text: "    ~ UPDATE: \"auth middleware\" \u2192 merged with existing memory", delay: 4200, style: "text-primary/60" },
            { text: "    - DISCARD: already captured in memory", delay: 4400, style: "text-muted-foreground/50" },
            { text: "", delay: 4600 },
            { text: "\u2713 Session saved (auth-service \u00B7 1h 23m)", delay: 4800, style: "text-primary font-bold" },
        ],
        duration: 6400,
    },
    {
        label: "Wake",
        cmd: "flow wake",
        lines: [
            { text: "$ flow wake", delay: 0, style: "text-primary font-bold" },
            { text: "", delay: 400 },
            { text: "\u26A1 auth-service", delay: 800, style: "text-primary font-bold text-lg" },
            { text: "", delay: 1000 },
            { text: "You finished the JWT rotation middleware with", delay: 1200 },
            { text: "the /auth/refresh exclusion fix and added test", delay: 1200 },
            { text: "coverage. The auth-v1 migration path is fully", delay: 1200 },
            { text: "deprecated. Next up: the session expiry webhook", delay: 1200 },
            { text: "handler that was blocked on the auth refactor.", delay: 1200 },
            { text: "", delay: 2800 },
            { text: "  \u250C\u2500\u2500 source \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510", delay: 3200, style: "text-border" },
            { text: "  \u2502 8 memories \u00B7 3 days away \u00B7 SHORT tier   \u2502", delay: 3400, style: "text-muted-foreground" },
            { text: "  \u2502 cached for 5 min                       \u2502", delay: 3400, style: "text-muted-foreground" },
            { text: "  \u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518", delay: 3400, style: "text-border" },
        ],
        duration: 5000,
    },
]

export function DemoSection() {
    const [activeStep, setActiveStep] = useState(0)
    const [visibleLines, setVisibleLines] = useState(0)
    const [isPlaying, setIsPlaying] = useState(true)
    const timersRef = useRef<NodeJS.Timeout[]>([])
    const advanceTimerRef = useRef<NodeJS.Timeout | null>(null)

    const clearAllTimers = useCallback(() => {
        timersRef.current.forEach(clearTimeout)
        timersRef.current = []
        if (advanceTimerRef.current) {
            clearTimeout(advanceTimerRef.current)
            advanceTimerRef.current = null
        }
    }, [])

    const playStep = useCallback((stepIndex: number) => {
        clearAllTimers()
        setVisibleLines(0)
        setActiveStep(stepIndex)

        const step = STEPS[stepIndex]
        step.lines.forEach((line, i) => {
            const timer = setTimeout(() => {
                setVisibleLines(i + 1)
            }, line.delay)
            timersRef.current.push(timer)
        })

        if (isPlaying) {
            advanceTimerRef.current = setTimeout(() => {
                setActiveStep(prev => {
                    const next = (prev + 1) % STEPS.length
                    playStep(next)
                    return next
                })
            }, step.duration)
        }
    }, [clearAllTimers, isPlaying])

    useEffect(() => {
        playStep(0)
        return clearAllTimers
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    const handleStepClick = (index: number) => {
        playStep(index)
    }

    const togglePlay = () => {
        setIsPlaying(prev => {
            if (prev) {
                if (advanceTimerRef.current) {
                    clearTimeout(advanceTimerRef.current)
                    advanceTimerRef.current = null
                }
            } else {
                const step = STEPS[activeStep]
                advanceTimerRef.current = setTimeout(() => {
                    const next = (activeStep + 1) % STEPS.length
                    playStep(next)
                }, 2000)
            }
            return !prev
        })
    }

    const step = STEPS[activeStep]

    return (
        <section className="relative flex flex-col items-center border-b-4 border-primary bg-secondary/30 px-4 py-32 overflow-hidden">
            <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:40px_40px]" />

            <div className="relative z-10 w-full max-w-5xl">
                <ScrollReveal delay={100}>
                    <div className="text-center mb-16">
                        <div className="inline-flex items-center gap-2 bg-primary text-primary-foreground font-mono text-xs uppercase tracking-widest px-3 py-1 mb-8">
                            <Play className="h-3 w-3" />
                            Demo
                        </div>
                        <h2 className="font-sans text-4xl font-black uppercase leading-tight text-foreground md:text-5xl lg:text-7xl">
                            See It In<br />
                            <span className="text-primary">Action.</span>
                        </h2>
                    </div>
                </ScrollReveal>

                <ScrollReveal delay={200}>
                    {/* Step tabs */}
                    <div className="flex items-center border-2 border-border bg-background mb-0">
                        {STEPS.map((s, i) => (
                            <button
                                key={i}
                                onClick={() => handleStepClick(i)}
                                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 font-mono text-xs uppercase tracking-widest transition-colors border-r-2 border-border last:border-r-0 ${
                                    i === activeStep
                                        ? "bg-primary text-primary-foreground"
                                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                                }`}
                            >
                                <span className="hidden sm:inline">{i + 1}.</span>
                                {s.label}
                            </button>
                        ))}
                        <button
                            onClick={togglePlay}
                            className="px-4 py-3 border-l-2 border-border text-muted-foreground hover:text-primary transition-colors"
                            title={isPlaying ? "Pause" : "Play"}
                        >
                            {isPlaying ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                        </button>
                    </div>

                    {/* Terminal window */}
                    <div className="border-2 border-t-0 border-border bg-background shadow-[8px_8px_0_0_hsl(var(--primary))]">
                        {/* Title bar */}
                        <div className="flex items-center justify-between border-b-2 border-border px-4 py-2 bg-secondary/50">
                            <div className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full bg-destructive" />
                                <div className="w-3 h-3 rounded-full bg-primary/50" />
                                <div className="w-3 h-3 rounded-full bg-primary" />
                            </div>
                            <span className="font-mono text-xs text-muted-foreground">
                                (flow) ~/auth-service
                            </span>
                            <Terminal className="h-4 w-4 text-muted-foreground" />
                        </div>

                        {/* Terminal body */}
                        <div className="p-6 font-mono text-sm leading-relaxed min-h-[420px] max-h-[420px] overflow-hidden">
                            {step.lines.slice(0, visibleLines).map((line, i) => (
                                <div
                                    key={`${activeStep}-${i}`}
                                    className={`${line.style || "text-foreground"} animate-in fade-in slide-in-from-bottom-1 duration-200`}
                                    style={{ minHeight: line.text ? undefined : "1.25rem" }}
                                >
                                    {line.text}
                                </div>
                            ))}
                            {visibleLines < step.lines.length && (
                                <span className="inline-block w-2 h-4 bg-primary animate-pulse mt-1" />
                            )}
                        </div>
                    </div>

                    {/* Step description */}
                    <div className="mt-6 flex items-start gap-4">
                        <ChevronRight className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                        <p className="font-mono text-sm text-muted-foreground">
                            {activeStep === 0 && "flow start records the HEAD commit, writes a PID file, queries Mem0 for prior context, and injects a compressed briefing into your AI tool's rules file before you write a single prompt."}
                            {activeStep === 1 && "You work normally. Flow doesn't run in the foreground. The (flow) shell indicator shows a session is active. Commits, AI conversations, and file changes are captured at stop time."}
                            {activeStep === 2 && "flow stop parses all AI tool logs, runs an LLM over the git diff for semantic understanding, redacts secrets, chunks the session, and feeds it to Mem0. Facts are extracted, compared against existing memories, and merged or added."}
                            {activeStep === 3 && "flow wake searches your Mem0 memory by meaning, picks a prompt tier based on how long you've been away, and generates a natural-language briefing from your memories plus recent git activity."}
                        </p>
                    </div>
                </ScrollReveal>
            </div>
        </section>
    )
}
