import Link from "next/link"
import { Terminal } from "lucide-react"

export function Navbar() {
  return (
    <nav className="absolute top-0 left-0 right-0 z-50 flex items-center justify-between border-b-2 border-border bg-background px-6 py-4 md:px-12 backdrop-blur-sm">
      <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
        <div className="flex h-10 w-10 items-center justify-center bg-primary border-2 border-primary text-primary-foreground shadow-[2px_2px_0_0_hsl(var(--foreground))]">
          <Terminal className="h-5 w-5" />
        </div>
        <span className="font-sans text-xl font-black uppercase tracking-tighter text-foreground">Flow</span>
      </Link>
      <div className="flex items-center gap-6">
        <Link href="https://github.com" className="font-mono text-sm uppercase tracking-widest text-foreground hover:text-primary transition-colors hover:underline underline-offset-4 border-2 border-transparent px-2 py-1 hover:border-border">
          GitHub
        </Link>
      </div>
    </nav>
  )
}
