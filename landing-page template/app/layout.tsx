import React from "react"
import type { Metadata } from 'next'
import { Bricolage_Grotesque, IBM_Plex_Mono } from 'next/font/google'

import './globals.css'

const bricolage = Bricolage_Grotesque({
  subsets: ['latin'],
  variable: '--font-bricolage',
})

const ibmPlexMono = IBM_Plex_Mono({
  weight: ['400', '500', '600', '700'],
  subsets: ['latin'],
  variable: '--font-ibm-plex',
})

export const metadata: Metadata = {
  title: 'Flow | CLI Session Tracker',
  description: 'A CLI that watches your coding session and tells you exactly where you left off. Reclaim your context and reach flow state instantly.',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${bricolage.variable} ${ibmPlexMono.variable} font-sans antialiased bg-background text-foreground selection:bg-primary selection:text-primary-foreground`}>
        {children}
      </body>
    </html>
  )
}
