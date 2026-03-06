"use client"

import { useEffect, useRef, useState } from "react"

export function ScrollReveal({
    children,
    className = "",
    delay = 0
}: {
    children: React.ReactNode
    className?: string
    delay?: number
}) {
    const [isVisible, setIsVisible] = useState(false)
    const ref = useRef<HTMLDivElement>(null)

    useEffect(() => {
        const observer = new IntersectionObserver(([entry]) => {
            if (entry.isIntersecting) {
                setIsVisible(true)
                if (ref.current) observer.unobserve(ref.current)
            }
        }, { threshold: 0.15, rootMargin: "0px 0px -50px 0px" })

        if (ref.current) observer.observe(ref.current)
        return () => observer.disconnect()
    }, [])

    return (
        <div
            ref={ref}
            className={className}
            style={{
                opacity: isVisible ? 1 : 0,
                transform: isVisible ? "translateY(0)" : "translateY(32px)",
                transition: `opacity 700ms ease-out, transform 700ms ease-out`,
                transitionDelay: `${delay}ms`
            }}
        >
            {children}
        </div>
    )
}
