import Link from "next/link"
import { Terminal } from "lucide-react"

export function Footer() {
  return (
    <footer className="border-t-4 border-primary bg-background px-6 py-16 md:px-12">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-8 md:flex-row">
        <div className="flex flex-col items-center md:items-start">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center bg-primary text-primary-foreground">
              <Terminal className="h-4 w-4" />
            </div>
            <span className="font-sans text-xl font-black uppercase tracking-tighter text-foreground">Flow</span>
          </div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Kill Cognitive Overhead.
          </p>
        </div>

        <div className="flex gap-8">
          <Link href="/docs" className="font-mono text-xs uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors hover:underline">
            Docs
          </Link>
          <Link href="https://github.com/samrathp29/flow" target="_blank" rel="noopener noreferrer" className="font-mono text-xs uppercase tracking-widest text-muted-foreground hover:text-primary transition-colors hover:underline">
            GitHub
          </Link>
        </div>
      </div>
    </footer>
  )
}
