import { Terminal, Database } from "lucide-react"
import Link from "next/link"
import Image from "next/image"

export function HeroSection() {
  return (
    <section className="relative flex min-h-[90vh] flex-col items-center justify-center overflow-hidden border-b-4 border-primary">
      {/* Brutalist terminal background grid */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:50px_50px]" />

      <div className="relative z-10 flex flex-col items-center px-4 text-center mt-20 pb-20">
        <div className="inline-flex items-center gap-2 bg-primary/20 text-primary px-3 py-1 text-xs font-mono mb-8 uppercase tracking-widest border border-primary animate-in fade-in slide-in-from-bottom-4 duration-700">
          <Terminal className="h-4 w-4" />
          <span>v0.1.0 Alpha</span>
        </div>

        <h1 className="mb-6 font-sans text-6xl font-black uppercase tracking-tighter text-foreground md:text-8xl lg:text-9xl animate-in fade-in slide-in-from-bottom-8 duration-700 fill-mode-both delay-150">
          Reach <br /><span className="text-primary">Flow State</span>
        </h1>

        <p className="mb-12 max-w-2xl font-mono text-base leading-relaxed text-muted-foreground md:text-lg animate-in fade-in slide-in-from-bottom-8 duration-700 fill-mode-both delay-300">
          Return to your coding projects after weeks away without the cognitive overhead. Instantly retrieve your context and pick up right where you left off.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 items-center animate-in fade-in slide-in-from-bottom-8 duration-700 fill-mode-both delay-500">
          <Link href="https://github.com/samrathp29/flow" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 bg-primary px-8 py-4 font-mono text-sm font-bold text-primary-foreground uppercase tracking-widest hover:bg-primary/90 transition-none border-2 border-primary hover:translate-y-1 hover:translate-x-1 active:translate-y-0 active:translate-x-0">
            flow start
          </Link>
          <Link href="/docs" className="flex items-center gap-2 bg-transparent px-8 py-4 font-mono text-sm font-bold text-foreground uppercase tracking-widest hover:bg-secondary transition-none border-2 border-border">
            Read Docs
          </Link>
        </div>

        <div className="mt-12 flex items-center gap-0 animate-in fade-in slide-in-from-bottom-4 duration-1000 fill-mode-both delay-700">
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">Powered by</span>
          <Link href="https://mem0.ai/" target="_blank" rel="noopener noreferrer" className="relative h-6 w-20 grayscale opacity-80 hover:grayscale-0 hover:opacity-100 transition-all -ml-4">
            <Image
              src="/images/mem0_logo.jpeg"
              alt="Mem0 Logo"
              fill
              className="object-contain"
            />
          </Link>
        </div>

      </div>
    </section>
  )
}
