"use client"
import type React from "react"
import type { ReactNode } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { FacebookIcon, InstagramIcon, LinkedinIcon, YoutubeIcon } from "lucide-react"
import Image from "next/image"
import Link from "next/link"

interface FooterLink {
  title: string
  href: string
  icon?: React.ComponentType<{ className?: string }>
}

interface FooterSection {
  label: string
  links: FooterLink[]
}

const footerLinks: FooterSection[] = [
  {
    label: "Product",
    links: [
      { title: "Dashboard", href: "/dashboard" },
      { title: "AI Analytics", href: "/ai-analytics" },
      { title: "Chat", href: "/chatbot" },
      { title: "Upload", href: "/upload" },
    ],
  },
  {
    label: "Analytics",
    links: [
      { title: "Weekly", href: "/analytics?tab=weekly" },
      { title: "Monthly", href: "/analytics?tab=monthly" },
      { title: "Yearly", href: "/analytics?tab=yearly" },
    ],
  },
  {
    label: "Account",
    links: [
      { title: "Sign in", href: "/signin" },
      { title: "Get started", href: "/signin?next=/dashboard" },
    ],
  },
  {
    label: "Social",
    links: [
      { title: "Facebook", href: "https://facebook.com", icon: FacebookIcon },
      { title: "Instagram", href: "https://instagram.com", icon: InstagramIcon },
      { title: "Youtube", href: "https://youtube.com", icon: YoutubeIcon },
      { title: "LinkedIn", href: "https://linkedin.com", icon: LinkedinIcon },
    ],
  },
]

export function Footer() {
  return (
    <footer className="md:rounded-t-6xl relative w-full max-w-6xl mx-auto flex flex-col items-center justify-center rounded-t-4xl border-t bg-[radial-gradient(35%_128px_at_50%_0%,theme(backgroundColor.white/8%),transparent)] px-6 py-12 lg:py-16">
      <div className="bg-foreground/20 absolute top-0 right-1/2 left-1/2 h-px w-1/3 -translate-x-1/2 -translate-y-1/2 rounded-full blur" />

      <div className="grid w-full gap-8 xl:grid-cols-3 xl:gap-8">
        <AnimatedContainer className="space-y-4">
          <Image src="/lumen_logo.svg" alt="Lumen logo" width={64} height={64} className="size-16" />
          <div className="text-muted-foreground mt-8 text-sm md:mt-0 md:block hidden">
            <p>© {new Date().getFullYear()} Lumen. All rights reserved.</p>
          </div>
        </AnimatedContainer>

        <div className="mt-10 grid grid-cols-2 gap-8 md:grid-cols-4 xl:col-span-2 xl:mt-0">
          {footerLinks.map((section, index) => (
            <AnimatedContainer key={section.label} delay={0.1 + index * 0.1}>
              <div className="mb-10 md:mb-0">
                <h3 className="text-xs">{section.label}</h3>
                <ul className="text-muted-foreground mt-4 space-y-2 text-sm">
                  {section.links.map((link) => (
                    <li key={link.title}>
                      <Link
                        href={link.href}
                        className="hover:text-foreground inline-flex items-center transition-all duration-300"
                      >
                        {link.icon && <link.icon className="me-1 size-4" />}
                        {link.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            </AnimatedContainer>
          ))}
        </div>
      </div>

      <div className="md:hidden mt-8 text-center space-y-2">
        <p className="text-muted-foreground text-sm">© {new Date().getFullYear()} Lumen. All rights reserved.</p>
      </div>

      <div className="hidden md:block mt-8 pt-6 border-t border-foreground/10 w-full">
        <p className="text-muted-foreground text-xs text-center">AI-powered invoice management for modern teams</p>
      </div>
    </footer>
  )
}

type AnimatedContainerProps = {
  delay?: number
  children: ReactNode
  className?: string
}

function AnimatedContainer({ delay = 0.1, children, className }: AnimatedContainerProps) {
  const shouldReduceMotion = useReducedMotion()

  if (shouldReduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay, duration: 0.5 }}
    >
      {children}
    </motion.div>
  )
}
