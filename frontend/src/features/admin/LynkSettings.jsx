import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Copy, Link2, Loader2, Save } from "lucide-react";
import { adminApi, errMsg } from "@/lib/api";
import { copyText } from "./CreateLicenseForm";

const WEBHOOK_URL = `${process.env.REACT_APP_BACKEND_URL}/api/webhooks/lynk`;
const ACTIVATION_URL = `${window.location.origin}/aktivasi`;

const CopyRow = ({ label, value, testid }) => (
  <div className="space-y-1">
    <p className="text-xs text-slate-400">{label}</p>
    <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
      <span data-testid={testid} className="num flex-1 truncate text-xs text-slate-200">{value}</span>
      <button type="button" data-testid={`${testid}-copy`} onClick={() => copyText(value)} className="text-slate-400 hover:text-emerald-400"><Copy className="h-4 w-4" /></button>
    </div>
  </div>
);

export const LynkSettings = () => {
  const [s, setS] = useState(null);
  const [key, setKey] = useState("");
  const [url, setUrl] = useState("");
  const [defDays, setDefDays] = useState(0);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { const r = await adminApi.lynk(); setS(r); setUrl(r.renew_url || ""); setDefDays(r.default_days || 0); }, []);
  useEffect(() => { load().catch(() => {}); }, [load]);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { setS(await adminApi.saveLynk({ merchant_key: key, renew_url: url, default_days: defDays })); setKey(""); toast.success("Pengaturan Lynk disimpan"); }
    catch (err) { toast.error(errMsg(err)); }
    finally { setBusy(false); }
  };

  return (
    <div data-testid="admin-lynk-settings" className="rounded-xl border border-slate-800 bg-[#161F30] p-5 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 font-semibold"><Link2 className="h-4 w-4 text-amber-400" /> Integrasi Lynk.id</p>
        {s && <Badge data-testid="admin-lynk-status" variant="outline" className={s.merchant_key_set ? "text-emerald-400 border-emerald-500/30" : "text-red-400 border-red-500/30"}>
          {s.merchant_key_set ? `Terhubung (${s.merchant_key_hint})` : "Merchant key belum diisi"}</Badge>}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <CopyRow label="1. Tempel di Lynk → Settings → Webhook" value={WEBHOOK_URL} testid="admin-webhook-url" />
        <CopyRow label="2. Tempel di konten produk Lynk (setelah bayar)" value={ACTIVATION_URL} testid="admin-activation-url" />
      </div>
      <form onSubmit={save} className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
        <div className="space-y-1.5"><Label className="text-xs text-slate-400">3. Merchant Key dari Lynk</Label>
          <Input data-testid="admin-merchant-key" type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={s?.merchant_key_set ? "Isi untuk mengganti" : "mk_live_…"} className="h-10 bg-slate-900 border-slate-700" /></div>
        <div className="space-y-1.5"><Label className="text-xs text-slate-400">Link produk untuk tombol "Perpanjang di Lynk"</Label>
          <Input data-testid="admin-renew-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://lynk.id/akunmu/sampe" className="h-10 bg-slate-900 border-slate-700" /></div>
        <Button data-testid="admin-lynk-save" type="submit" disabled={busy} className="h-10 bg-amber-500 hover:bg-amber-600 text-slate-950 font-semibold">
          {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />} Simpan</Button>
      </form>
      <div data-testid="admin-default-days" className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-2.5">
        <span className="text-xs text-slate-300">Durasi default jika nama produk tidak menyebut durasi:</span>
        {[[0, "Tidak ada"], [1, "1 hari"], [7, "7 hari"], [30, "30 hari"], [365, "365 hari"]].map(([d, l]) => (
          <button type="button" key={d} data-testid={`admin-default-days-${d}`} onClick={() => setDefDays(d)}
            className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${defDays === d ? "bg-amber-500 text-slate-950" : "text-slate-400 hover:text-white"}`}>{l}</button>
        ))}
        <span className="text-[11px] text-slate-500">(klik Simpan setelah memilih)</span>
      </div>
      <p className="text-xs text-slate-500">Durasi dibaca dari nama produk Lynk: mengandung "1 Hari", "7 Hari", "30 Hari", "365 Hari" atau "1 Tahun". Kalau tidak ada, dipakai durasi default di atas. Pembelian ulang dengan email sama = perpanjang (sisa hari ditambah).</p>
      <WebhookLogs />
    </div>
  );
};

const LOG_TONE = { processed: "text-emerald-400", duplicate: "text-sky-400", ignored: "text-amber-400", rejected: "text-red-400", unmatched: "text-red-400" };

const WebhookLogs = () => {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(null);
  const load = useCallback(() => adminApi.webhookLogs().then(setRows).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);
  const reprocess = async (r) => {
    if (!window.confirm(`Proses order ${r.ref_id} dan buat/perpanjang lisensi?`)) return;
    try { const o = await adminApi.reprocess(r.received_at); toast.success(`Lisensi ${o.action === "extended" ? "diperpanjang" : "dibuat"} +${o.days} hari untuk ${o.email}`); }
    catch (e) { toast.error(errMsg(e)); }
    load();
  };
  return (
    <div data-testid="admin-webhook-logs" className="rounded-lg border border-slate-800 bg-slate-900/50">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
        <p className="text-xs font-semibold text-slate-300">Webhook terakhir diterima</p>
        <button type="button" data-testid="admin-webhook-logs-refresh" onClick={load} className="text-xs text-amber-400 hover:underline">Muat ulang</button>
      </div>
      {!rows?.length ? <p className="px-3 py-4 text-xs text-slate-500">Belum ada webhook masuk. Klik "Test" di Lynk atau lakukan order percobaan.</p> : rows.slice(0, 8).map((r, i) => (
        <div key={i} data-testid="admin-webhook-log-row" className="border-b border-slate-800/60 px-3 py-2 last:border-0">
          <button type="button" onClick={() => setOpen(open === i ? null : i)} className="flex w-full items-center justify-between gap-3 text-left text-xs">
            <span className={`font-semibold uppercase ${LOG_TONE[r.status] || "text-slate-300"}`}>{r.status}</span>
            <span className="flex-1 truncate text-slate-300">{r.reason}{r.ref_id ? ` · ${r.ref_id}` : ""}</span>
            <span className="num text-slate-500">{fmt(r.received_at)}</span>
          </button>
          {open === i && <pre className="num mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-950 p-2 text-[10px] text-slate-400">{r.body || "(kosong)"}</pre>}
          {r.ref_id && ["rejected", "unmatched"].includes(r.status) && (
            <button type="button" data-testid={`admin-webhook-process-${r.ref_id}`} onClick={() => reprocess(r)}
              className="mt-1.5 rounded-md border border-amber-500/40 px-2.5 py-1 text-[11px] font-semibold text-amber-300 hover:bg-amber-500/10">Proses order ini → buat lisensi</button>
          )}
        </div>
      ))}
    </div>
  );
};

const fmt = (s) => new Date(s).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export const OrdersTable = ({ refreshKey }) => {
  const [rows, setRows] = useState(null);
  useEffect(() => { adminApi.orders().then(setRows).catch(() => setRows([])); }, [refreshKey]);
  if (rows === null) return null;
  return (
    <div data-testid="admin-orders-table" className="overflow-x-auto rounded-xl border border-slate-800 bg-[#161F30]">
      <p className="border-b border-slate-800 px-4 py-3 text-sm font-semibold">Order Lynk.id <span className="text-xs font-normal text-slate-500">({rows.length})</span></p>
      {rows.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">Belum ada order masuk dari Lynk.</p> : (
        <table className="w-full min-w-[760px] text-sm">
          <tbody>
            {rows.map((o) => (
              <tr key={o.ref_id} data-testid={`admin-order-${o.ref_id}`} className="border-b border-slate-800/60 last:border-0">
                <td className="py-2.5 pl-4 pr-3"><p className="text-slate-200">{o.name || o.email}</p><p className="text-xs text-slate-500">{o.email}</p></td>
                <td className="num px-3 text-xs text-slate-400">{o.ref_id}</td>
                <td className="px-3 text-xs text-slate-300">{o.product}</td>
                <td className="px-3">
                  {o.status === "processed"
                    ? <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">{o.action === "extended" ? "Diperpanjang" : "Lisensi baru"} +{o.days} hari</Badge>
                    : <Badge variant="outline" className="text-red-400 border-red-500/30">Produk tidak dikenali</Badge>}
                </td>
                <td className="num px-3 text-xs text-slate-400">{o.license?.code || "—"}</td>
                <td className="num pr-4 pl-3 text-xs text-slate-500">{fmt(o.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
