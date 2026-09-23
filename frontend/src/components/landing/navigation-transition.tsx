"use client"

import { usePathname, useRouter } from "next/navigation"
import { useEffect, useState, useRef } from "react"
import { logger } from "@/lib/logger"

export function NavigationTransition() {
  const pathname = usePathname()
  const router = useRouter()
  const [isTransitioning, setIsTransitioning] = useState(false)
  const previousPathname = useRef(pathname)

  useEffect(() => {
    logger.debug("[v0] NavigationTransition mounted for path:", pathname)

    // Handle link clicks for smooth transitions
    const handleLinkClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const link = target.closest("a")

      if (link && link.href && link.href.startsWith(window.location.origin)) {
        const url = new URL(link.href)

        // Only intercept internal navigation to different pages
        if (url.pathname !== pathname && !url.hash) {
          logger.debug("[v0] Intercepting navigation to:", url.pathname)
          e.preventDefault()

          // Start fade out
          setIsTransitioning(true)
          logger.debug("[v0] Transition state set to true")

          // Navigate after fade out
          setTimeout(() => {
            logger.debug("[v0] Navigating to:", url.pathname)
            router.push(url.pathname)
          }, 300)
        }
      }
    }

    document.addEventListener("click", handleLinkClick)

    return () => {
      document.removeEventListener("click", handleLinkClick)
    }
  }, [pathname, router])

  useEffect(() => {
    // Check if pathname actually changed
    if (pathname !== previousPathname.current) {
      logger.debug("[v0] Pathname changed from", previousPathname.current, "to", pathname)
      logger.debug("[v0] isTransitioning state:", isTransitioning)

      if (isTransitioning) {
        logger.debug("[v0] Page loaded, fading in")
      }

      // Always fade in after navigation, even if state wasn't set
      setTimeout(() => {
        setIsTransitioning(false)
      }, 50)

      previousPathname.current = pathname
    }
  }, [pathname, isTransitioning])

  return (
    <div
      className={`fixed inset-0 bg-black pointer-events-none transition-opacity duration-300 ease-in-out z-[100] ${
        isTransitioning ? "opacity-100" : "opacity-0"
      }`}
    />
  )
}
