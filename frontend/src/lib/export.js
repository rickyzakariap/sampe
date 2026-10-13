import { rupiahFull } from "@/lib/format";

export const monthLabel = (m) => {
  if (!m) return "";
  const [y, mo] = m.split("-").map(Number);
  const names = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
  return `${names[mo - 1]} ${y}`;
};

const statusText = { green: "On Track", amber: "Waspada", red: "Tertinggal" };

const summaryRows = (d) => {
  const r = (label, m, unit = "rp") => {
    const fmt = (v) => (unit === "rp" ? rupiahFull(v) : `${Number(v).toFixed(1)} jam`);
    return [label, fmt(m.monthly_target), fmt(m.expected_to_date), fmt(m.achieved), `${m.achieved_pct.toFixed(1)}%`, statusText[m.status]];
  };
  return [
    r("Penjualan", d.sales),
    r("Ads Spend", d.ads),
    r("Branding", d.branding),
    r("Campaign", d.campaign),
    r("Durasi Live", d.live_hours, "jam"),
    r("Omzet Live", d.live_revenue),
    r("Budget KOL", d.kol),
  ];
};

const download = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

export const exportCSV = (dash, entries) => {
  const lines = [];
  lines.push([`Laporan KPI`, dash.config.company_name]);
  lines.push([`Periode`, monthLabel(dash.config.month)]);
  lines.push([`Hari berjalan`, `${dash.month_meta.days_elapsed}/${dash.month_meta.days_in_month}`]);
  lines.push([]);
  lines.push(["RINGKASAN KPI"]);
  lines.push(["Metrik", "Target Bulan", "Target Prorata", "Tercapai", "Pencapaian %", "Status"]);
  summaryRows(dash).forEach((row) => lines.push(row));
  lines.push([]);
  lines.push(["DETAIL INPUT HARIAN"]);
  lines.push(["Tanggal", "Modul", "Platform/Tipe", "Nama/Akun", "Nilai"]);
  entries.forEach((e) => {
    const d = e.data || {};
    const nilai = d.omzet ?? d.spend ?? d.budget ?? "";
    lines.push([e.date, e.module, d.platform || d.type || "", d.account || d.name || d.streamer || "", nilai]);
  });

  const csv = lines
    .map((row) => row.map((c) => `"${String(c ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  download(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" }), `KPI_${dash.config.company_name}_${dash.config.month}.csv`);
};

export const exportPDF = async (dash) => {
  const { default: jsPDF } = await import("jspdf");
  const autoTable = (await import("jspdf-autotable")).default;
  const doc = new jsPDF();

  doc.setFontSize(16);
  doc.setTextColor(16, 185, 129);
  doc.text("Laporan KPI — SAMPE", 14, 16);
  doc.setFontSize(10);
  doc.setTextColor(60);
  doc.text(`${dash.config.company_name}  ·  ${monthLabel(dash.config.month)}  ·  Hari berjalan ${dash.month_meta.days_elapsed}/${dash.month_meta.days_in_month}`, 14, 23);

  autoTable(doc, {
    startY: 29,
    head: [["Metrik", "Target Bulan", "Target Prorata", "Tercapai", "%", "Status"]],
    body: summaryRows(dash),
    theme: "grid",
    headStyles: { fillColor: [16, 185, 129] },
    styles: { fontSize: 9, cellPadding: 2.5 },
  });

  doc.setFontSize(8);
  doc.setTextColor(140);
  doc.text(`Dibuat ${new Date().toLocaleString("id-ID")}`, 14, doc.lastAutoTable.finalY + 8);

  doc.save(`KPI_${dash.config.company_name}_${dash.config.month}.pdf`);
};
