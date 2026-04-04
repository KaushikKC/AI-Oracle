"use client"

import { useEffect, useRef, useState } from "react"
import * as d3 from "d3"
import type { LifeEvent } from "@/lib/types"

interface TooltipState {
  x: number
  y: number
  event: LifeEvent
}

const CATEGORY_COLORS: Record<string, string> = {
  career:        "#6366f1",
  health:        "#10b981",
  finances:      "#f59e0b",
  relationships: "#ec4899",
  skills:        "#8b5cf6",
  other:         "#6b7280",
}

const CATEGORIES = ["career", "health", "finances", "relationships", "skills"]

const LANE_H   = 52
const MARGIN_L = 96
const MARGIN_R = 24
const MARGIN_T = 16
const MARGIN_B = 36

export function EventTimeline({ events }: { events: LifeEvent[] }) {
  const svgRef       = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || events.length === 0) return

    const W = containerRef.current.offsetWidth
    const H = CATEGORIES.length * LANE_H + MARGIN_T + MARGIN_B

    const svg = d3.select(svgRef.current)
    svg.selectAll("*").remove()
    svg.attr("width", W).attr("height", H)

    const dates = events.map((e) => new Date(e.timestamp))
    const xScale = d3
      .scaleTime()
      .domain([d3.min(dates)!, d3.max(dates)!])
      .range([MARGIN_L, W - MARGIN_R])
      .nice()

    // X axis
    svg
      .append("g")
      .attr("transform", `translate(0,${H - MARGIN_B})`)
      .call(
        d3.axisBottom(xScale)
          .ticks(6)
          .tickFormat((d) => d3.timeFormat("%b %y")(d as Date))
      )
      .call((g) => g.select(".domain").attr("stroke", "#2a3347"))
      .call((g) =>
        g
          .selectAll(".tick line")
          .attr("stroke", "#2a3347")
          .attr("y1", -(H - MARGIN_T - MARGIN_B))
      )
      .call((g) => g.selectAll(".tick text").attr("fill", "#64748b").attr("font-size", 11))

    CATEGORIES.forEach((cat, i) => {
      const cy = MARGIN_T + i * LANE_H + LANE_H / 2

      // Lane label
      svg
        .append("text")
        .attr("x", MARGIN_L - 8)
        .attr("y", cy)
        .attr("text-anchor", "end")
        .attr("dominant-baseline", "middle")
        .attr("fill", CATEGORY_COLORS[cat])
        .attr("font-size", 12)
        .attr("font-weight", 600)
        .text(cat)

      // Lane baseline
      svg
        .append("line")
        .attr("x1", MARGIN_L)
        .attr("x2", W - MARGIN_R)
        .attr("y1", cy)
        .attr("y2", cy)
        .attr("stroke", "#1e2636")
        .attr("stroke-width", 1)

      // Events in this lane
      events
        .filter((e) => e.category === cat)
        .forEach((ev) => {
          const cx = xScale(new Date(ev.timestamp))
          const r  = 3.5 + ev.importance_score * 5.5
          const strokeColor =
            ev.sentiment > 0.2
              ? "#10b981"
              : ev.sentiment < -0.2
              ? "#ef4444"
              : "#64748b"
          const fillOpacity = 0.25 + Math.abs(ev.sentiment) * 0.55

          const circle = svg
            .append("circle")
            .attr("cx", cx)
            .attr("cy", cy)
            .attr("r", r)
            .attr("fill", CATEGORY_COLORS[cat])
            .attr("fill-opacity", fillOpacity)
            .attr("stroke", strokeColor)
            .attr("stroke-width", 1.5)
            .style("cursor", "pointer")
            .style("transition", "fill-opacity 0.1s")

          circle
            .on("mouseenter", function (mouseEvent: MouseEvent) {
              d3.select(this).attr("fill-opacity", 0.9)
              const rect = containerRef.current!.getBoundingClientRect()
              setTooltip({
                x: mouseEvent.clientX - rect.left,
                y: mouseEvent.clientY - rect.top,
                event: ev,
              })
            })
            .on("mouseleave", function () {
              d3.select(this).attr("fill-opacity", fillOpacity)
              setTooltip(null)
            })
        })
    })
  }, [events])

  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-sm text-slate-500 border border-dashed border-slate-700 rounded-lg">
        No events yet — click "Seed 50 Events" to get started.
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative w-full select-none">
      <svg ref={svgRef} className="w-full overflow-visible" />

      {tooltip && (
        <div
          className="absolute z-20 pointer-events-none max-w-xs rounded-lg border border-slate-600 bg-slate-900 p-3 shadow-xl"
          style={{ left: tooltip.x + 14, top: tooltip.y - 8 }}
        >
          <p className="text-sm font-medium text-slate-100 leading-snug mb-1">
            {tooltip.event.description}
          </p>
          <p className="text-xs text-slate-400 mb-2">
            {new Date(tooltip.event.timestamp).toLocaleDateString("en-US", {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </p>
          <div className="flex gap-4 text-xs">
            <span>
              Sentiment:{" "}
              <span
                className={
                  tooltip.event.sentiment > 0 ? "text-green-400" : "text-red-400"
                }
              >
                {tooltip.event.sentiment > 0 ? "+" : ""}
                {tooltip.event.sentiment.toFixed(2)}
              </span>
            </span>
            <span className="text-slate-400">
              Importance: {Math.round(tooltip.event.importance_score * 100)}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
