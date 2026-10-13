export const SCALES = {
  mikro: { label: "Mikro", hint: "omzet ±Rp30 jt/bln", values: {
    target_sales: 30_000_000, budget_ads: 3_000_000, budget_branding: 1_000_000, budget_campaign: 1_500_000,
    budget_kol: 2_000_000, target_kol_count: 4, live_team_count: 1, target_live_hours: 60, target_live_revenue: 6_000_000 } },
  kecil: { label: "Kecil", hint: "omzet ±Rp150 jt/bln", values: {
    target_sales: 150_000_000, budget_ads: 15_000_000, budget_branding: 5_000_000, budget_campaign: 7_500_000,
    budget_kol: 10_000_000, target_kol_count: 8, live_team_count: 2, target_live_hours: 120, target_live_revenue: 30_000_000 } },
  menengah: { label: "Menengah", hint: "omzet ±Rp500 jt/bln", values: {
    target_sales: 500_000_000, budget_ads: 50_000_000, budget_branding: 20_000_000, budget_campaign: 25_000_000,
    budget_kol: 40_000_000, target_kol_count: 15, live_team_count: 4, target_live_hours: 240, target_live_revenue: 120_000_000 } },
};

export const STEP_FIELDS = {
  1: ["target_sales"], 2: ["budget_ads"], 3: ["budget_branding"], 4: ["budget_campaign"],
  5: ["budget_kol", "target_kol_count"], 6: ["live_team_count", "target_live_hours", "target_live_revenue"],
};

export const guessScale = (sales) => {
  const s = Number(sales) || 0;
  if (!s) return "kecil";
  return s < 90_000_000 ? "mikro" : s < 325_000_000 ? "kecil" : "menengah";
};
