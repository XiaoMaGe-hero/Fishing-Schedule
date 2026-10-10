import { useEffect, useRef } from "react";
import { copy } from "../copy";
import type { Spot } from "../data/derive";

/** A small map with a labelled marker per spot. The map library loads only when the map nears the screen. */
export function SpotMap({ spots }: { spots: Spot[] }) {
  const holder = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = holder.current;
    if (!el) return;
    let map: { remove: () => void } | null = null;
    let cancelled = false;
    const watcher = new IntersectionObserver(async (entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      watcher.disconnect();
      const [{ default: L }] = await Promise.all([import("leaflet"), import("leaflet/dist/leaflet.css")]);
      if (cancelled) return;
      const m = L.map(el, { scrollWheelZoom: false, dragging: !L.Browser.mobile, attributionControl: true });
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 17, attribution: copy.footer.mapCredit }).addTo(m);
      const bounds = L.latLngBounds(spots.map((s) => [s.lat, s.lon] as [number, number]));
      spots.forEach((s) => {
        L.circleMarker([s.lat, s.lon], { radius: 8, color: "#ffffff", weight: 2, fillColor: "#0e3a4a", fillOpacity: 1 })
          .addTo(m).bindTooltip(s.name, { permanent: true, direction: "right", offset: [10, 0], className: "map-label" });
      });
      m.fitBounds(bounds.pad(0.9));
      map = m;
    }, { rootMargin: "300px" });
    watcher.observe(el);
    return () => { cancelled = true; watcher.disconnect(); map?.remove(); };
  }, [spots]);
  return <div ref={holder} className="map" role="img" aria-label={copy.week.mapHeading} />;
}
