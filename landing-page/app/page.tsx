import { Navbar } from "@/components/navbar"
import { HeroSection } from "@/components/hero-section"
import { HomeSection } from "@/components/home-section"
import { OwnDataSection } from "@/components/own-data-section"
import { ContextInjectionSection } from "@/components/context-injection-section"
import { WhyFlowSection } from "@/components/why-flow-section"
import { DeveloperSection } from "@/components/developer-section"
import { Footer } from "@/components/footer"

export default function Page() {
  return (
    <main className="min-h-screen bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
      <Navbar />
      <HeroSection />
      <HomeSection />
      <OwnDataSection />
      <ContextInjectionSection />
      <WhyFlowSection />
      <DeveloperSection />
      <Footer />
    </main>
  )
}
