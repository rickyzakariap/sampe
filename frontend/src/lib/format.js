import { displayNumber } from "./detailFormat.mjs";

export const rupiah = (n) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1_000_000_000) return `Rp${displayNumber(v / 1_000_000_000)}M`;
  if (Math.abs(v) >= 1_000_000) return `Rp${displayNumber(v / 1_000_000)}jt`;
  if (Math.abs(v) >= 1_000) return `Rp${displayNumber(v / 1_000, 0)}rb`;
  return `Rp${displayNumber(v, 0)}`;
};

export const rupiahFull = (n) =>
  "Rp" + Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 });

export const pct = (n) => `${displayNumber(n || 0)}%`;

export const statusColor = {
  green: "text-emerald-400",
  amber: "text-amber-400",
  red: "text-red-400",
};
export const statusBg = {
  green: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
  amber: "bg-amber-500/10 border-amber-500/30 text-amber-400",
  red: "bg-red-500/10 border-red-500/30 text-red-400",
};
export const statusLabel = { green: "On Track", amber: "Waspada", red: "Tertinggal" };
