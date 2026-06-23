import type { Distribution } from "../types";

const COLORS: Record<string, string> = {
  Urgent: "#ef4444",
  Upcoming: "#f59e0b",
  Good: "#22c55e",
};
const ORDER = ["Urgent", "Upcoming", "Good"];

export default function DistributionBars({ dist, title }: { dist: Distribution; title?: string }) {
  const comps = Object.keys(dist);
  if (comps.length === 0) return null;
  return (
    <div>
      {title && <div className="text-xs font-semibold text-gray-500 mb-2">{title}</div>}
      <div className="space-y-2">
        {comps.map((comp) => {
          const counts = dist[comp];
          const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
          return (
            <div key={comp} className="flex items-center gap-2">
              <div className="w-32 text-xs text-gray-600 truncate">{comp}</div>
              <div className="flex-1 flex h-5 rounded overflow-hidden bg-gray-100">
                {ORDER.map((cls) =>
                  counts[cls] ? (
                    <div
                      key={cls}
                      title={`${cls}: ${counts[cls]}`}
                      style={{ width: `${(counts[cls] / total) * 100}%`, background: COLORS[cls] }}
                      className="text-[10px] text-white flex items-center justify-center"
                    >
                      {counts[cls]}
                    </div>
                  ) : null
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
