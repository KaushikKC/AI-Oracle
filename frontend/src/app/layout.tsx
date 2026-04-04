import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "UserLife — Simulation Engine",
  description: "Temporal life simulation across career, health, finances, relationships and skills.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
