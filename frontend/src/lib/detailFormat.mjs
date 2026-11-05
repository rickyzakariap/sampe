const formatters = [0, 1, 2].map((digits) => new Intl.NumberFormat("id-ID", { maximumFractionDigits: digits }));

export function displayNumber(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? formatters[digits].format(number) : "Tidak tersedia";
}

// Presentation only: keep the value used by the KPI and progress bar unchanged.
export function detailPercent(value) {
  const formatted = displayNumber(value);
  return formatted === "Tidak tersedia" ? formatted : `${formatted}%`;
}
