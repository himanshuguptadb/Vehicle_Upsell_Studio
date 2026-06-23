import type { ReactNode } from "react";

export function Card({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-5">
      {(title || right) && (
        <div className="flex items-center justify-between mb-3">
          {title && <h2 className="text-lg font-semibold text-[#1B3139]">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

export function Button({
  children, onClick, variant = "primary", disabled, type,
}: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "danger";
  disabled?: boolean; type?: "button" | "submit";
}) {
  const base = "px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary: "bg-[#FF3621] text-white hover:bg-[#e22e1b]",
    ghost: "bg-gray-100 text-[#1B3139] hover:bg-gray-200",
    danger: "bg-red-50 text-red-700 hover:bg-red-100",
  }[variant];
  return (
    <button type={type || "button"} onClick={onClick} disabled={disabled} className={`${base} ${styles}`}>
      {children}
    </button>
  );
}

const CLASS_STYLE: Record<string, string> = {
  Urgent: "bg-red-100 text-red-700",
  Upcoming: "bg-amber-100 text-amber-700",
  Good: "bg-green-100 text-green-700",
};

export function ClassBadge({ value }: { value: string | null }) {
  if (!value) return <span className="text-gray-400">—</span>;
  const style = CLASS_STYLE[value] || "bg-gray-100 text-gray-600";
  return <span className={`px-2 py-0.5 rounded text-xs font-semibold ${style}`}>{value}</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-gray-500">
      <span className="w-4 h-4 border-2 border-gray-300 border-t-[#FF3621] rounded-full animate-spin" />
      {label}
    </span>
  );
}

export function ErrorBox({ msg }: { msg: string }) {
  return <div className="bg-red-50 text-red-700 text-sm rounded-lg p-3 mb-3 whitespace-pre-wrap">{msg}</div>;
}
