# SAMPE Design System V1

Status: panduan internal berbasis source branch `work/lynk-entitlement-phase2`, 16 Oktober 2026. Dokumen ini tidak mengubah UI atau mengklaim telah memvalidasi setiap layar production secara visual. Label **Existing** berarti dapat ditelusuri ke source; **Usulan** berarti aturan untuk iterasi berikutnya yang belum diterapkan.

## 1. Identitas dan prinsip

**Quiet Motion × Data-First SaaS.** Angka, periode, target, selisih, dan tindakan operasional harus lebih mudah ditemukan daripada dekorasi. Satu layar sebaiknya memiliki satu judul utama, satu aksi utama yang relevan, dan status yang terbaca tanpa mengandalkan warna. Pertahankan logo resmi SAMPE apa adanya. Aset yang tersedia: `frontend/public/branding/sampe-dark-landscape.png`, `sampe-dark-portrait.png`, dan `sampe-clear-portrait.png`; varian landscape gelap memuat mark biru–ungu dan wordmark putih. Warna pada logo adalah identitas merek, bukan alasan mengubah palet status KPI.

Hindari tampilan generik: gradien pada setiap kartu, glow terus-menerus, statistik contoh yang tampak nyata, ikon sparkles di semua bagian, jargon AI tanpa sumber data, dan animasi yang menunda pembacaan KPI. Gunakan istilah SAMPE yang sudah dipakai: **Dashboard Harian**, **List KPI**, **Analisa AI**, **Refresh Data**, **On Track / Waspada / Tertinggal**.

Referensi Linear, Vercel, shadcn/ui, dan Motion.dev adalah tolok ukur keterbacaan, konsistensi, aksesibilitas, dan respons interaksi. Jangan menyalin layout atau identitas visualnya.

## 2. Warna dan token

**Existing — sumber:** `frontend/src/index.css` mendefinisikan token HSL Tailwind v4; `:root` dan `.dark` hampir sama, sehingga source saat ini pada praktiknya bertema gelap. `frontend/index.html` juga memakai `class="dark"`. Jangan mendokumentasikan light mode sebagai fitur yang sudah ada.

| Peran existing | Nilai source | Aturan pemakaian |
| --- | --- | --- |
| `background` | `hsl(222 47% 7%)` | Kanvas halaman. |
| `foreground` | `hsl(210 40% 98%)` | Teks utama. |
| `card` | `hsl(220 39% 13%)` | Permukaan kartu semantik. |
| `popover` | `hsl(222 44% 10%)` | Menu, tooltip, konten mengambang. |
| `primary` / `ring` | `hsl(160 84% 39%)` | Aksi utama dan fokus. |
| `secondary` / `muted` | `hsl(217 33% 17%)` | Permukaan sekunder. |
| `muted-foreground` | `hsl(215 20% 65%)` | Teks sekunder. |
| `destructive` | root `hsl(0 84% 60%)`; `.dark` `hsl(0 72% 51%)` | Aksi berisiko/error. |
| `border` / `input` | `hsl(217 33% 20%)` | Pemisah dan field. |
| `chart-1…5` | emerald, biru, amber, ungu, merah | Warna seri; selalu dipasangkan dengan label. |

**Existing tambahan:** banyak layar memakai kelas langsung `bg-[#161F30]`, `bg-slate-900`, `text-slate-400/500`, `emerald-400/500`, `amber-400/500`, dan `red-400/500`; grafik memakai hex langsung (`Dashboard.jsx`, `DashboardExtras.jsx`). Ini belum satu sumber token. Badge KPI memakai hijau/amber/merah plus teks status dari `frontend/src/lib/format.js`.

**Usulan:** pada iterasi UI, petakan permukaan `#161F30` dan warna grafik ke token bernama sebelum mengubah nilai; jangan melakukan penggantian global tanpa uji visual. Gunakan emerald untuk aksi/hasil positif, amber untuk perhatian atau Analisa AI, merah untuk risiko/kegagalan, dan biru/ungu hanya bila membantu membedakan seri grafik. Jangan gunakan satu warna untuk dua makna yang bersaing di layar yang sama.

**Kontras yang perlu ditinjau:** perhitungan WCAG dari nilai CSS solid menunjukkan `#64748b` (`slate-500`) di atas `#161F30` sekitar **3,47:1**, di bawah target **4,5:1** untuk teks kecil. `#94a3b8` (`slate-400`) pada kartu yang sama sekitar **6,43:1**. Latar transparan dan rendering nyata perlu diuji lagi. Mulai dari label/timestamp penting di dashboard, tabel, dan Owner Report; jangan mengubah palet besar-besaran.

## 3. Tipografi dan hierarki

**Existing:** Plus Jakarta Sans untuk body, Cabinet Grotesk untuk `h1–h3`, JetBrains Mono untuk `.num`/`code` (`frontend/src/index.css`, `frontend/index.html`). Kelas `.num` memakai angka tabular. Dashboard memakai heading `text-3xl sm:text-4xl`, judul kartu/grafik `text-lg`, label `text-xs uppercase tracking-wider`, dan nilai utama `text-2xl sm:text-3xl` (`Dashboard.jsx`).

**Usulan:** pertahankan tiga keluarga font ini. Satu `h1` per halaman; urutkan `h2` untuk modul, `h3` untuk subbagian. Angka utama harus menonjol melalui ukuran dan posisi, bukan glow. Gunakan JetBrains Mono pada angka, tanggal, persentase, dan perbandingan yang perlu disejajarkan; hindari seluruh paragraf mono. Teks bantuan minimal nyaman dibaca di HP; kelas `text-[10px]`/`text-[11px]` pada grafik/tabel perlu evaluasi visual dan kontras sebelum dibakukan.

## 4. Spacing, radius, border, elevation

**Existing:** token radius dasar `--radius: 0.75rem`; `rounded-xl` pada kartu, `rounded-lg` pada panel/status, `rounded-md` pada primitive button/input. Layout utama `max-w-7xl px-4 sm:px-6 py-6 sm:py-8`; banyak kartu `p-5`, dialog `p-6`, grid `gap-3/4`, antarbagian `space-y-6`. Primitive `Card` memakai border + `shadow-sm`, tooltip grafik `shadow-xl`; kebanyakan layar mengandalkan border dan warna permukaan, bukan bayangan berat.

**Usulan:** gunakan skala Tailwind yang sudah dipakai (4/8/12/16/24/32 px) dan radius existing sebagai default. Kartu data memakai border halus; elevasi lebih kuat hanya untuk layer yang mengambang. Hindari campuran radius dan padding acak antar kartu setara. Jangan menambah efek blur/glow agar kartu tampak penting.

## 5. Komponen

| Komponen | Existing | Panduan V1 / pemeriksaan sebelum implementasi |
| --- | --- | --- |
| Button | `ui/button.jsx` punya `default`, `outline`, `secondary`, `ghost`, `link`, `destructive`; `TopNavbar` dan `DailyInput` menimpa warna emerald untuk aksi utama. | Satu primary action per konteks. Disabled dan loading harus jelas; icon-only wajib nama aksesibel dan focus ring. Jangan menyamakan aksi hapus dengan navigasi. |
| Input | `ui/input.jsx` h-9, focus ring, placeholder muted; `DailyInput` menimpa h-10, wizard h-12. Date picker icon dibuat terlihat pada dark mode oleh `index.css`. | Label selalu terkait field; pesan validasi dekat field. Pertahankan min 44 px target sentuh pada form HP bila diuji. Jangan hanya mengandalkan placeholder. |
| Select | Primitive Radix di `ui/select.jsx`; selector bulan desktop/mobile berbeda di `TopNavbar`. | Tampilkan periode aktif jelas dan pastikan tidak terpotong pada lebar HP. Pertahankan keyboard navigation. |
| Modal/sheet | Radix Dialog/Sheet; onboarding memakai dialog, Analisa AI memakai sheet. | Fokus masuk, Esc/close, judul dan deskripsi aksesibel; aksi utama dan error tetap terlihat tanpa scroll berlebihan. Durasi diatur pada panduan motion. |
| Table/list | `ui/table.jsx`, `DashboardExtras.jsx`, `DailyInput.jsx`; Owner Report memakai tabel native dengan `min-w-[560px]` dan overflow horizontal. | Header, satuan, dan perataan angka konsisten. Pada HP uji scroll/tabel ringkas tanpa menyembunyikan kolom penting. Empty state harus menjelaskan langkah berikutnya. |
| Card | Primitive `Card` + banyak override `#161F30`; kartu metrik membuka detail saat diklik. | Angka, target, progress, lalu rincian. Kartu interaktif harus punya semantik tombol/link dan keyboard/focus; jangan mengandalkan `onClick` pada `<div>`. |
| Tooltip | Radix tooltip tersedia; grafik memakai tooltip Recharts tersendiri. | Tooltip melengkapi label, bukan satu-satunya cara membaca nilai. Sediakan ringkasan teks/tabel untuk pengguna keyboard dan layar sentuh. |

## 6. Status KPI dan visualisasi data

**Existing:** `green → On Track`, `amber → Waspada`, `red → Tertinggal` (`frontend/src/lib/format.js`). Dashboard menampilkan nominal, target, prorata, gap, progress, tren harian, channel, dan perbandingan bulan; grafik menggunakan Recharts (`Dashboard.jsx`, `DashboardExtras.jsx`). Alert merangkum KPI tertinggal dan data hari ini yang belum diisi (`KpiAlertBanner.jsx`).

**Panduan:** selalu tampilkan nilai, unit, periode, dan target bersama persentase. Bedakan **0**, **belum ada data**, dan **gagal memuat**. Warna status harus disertai teks/icon. Jelaskan baseline pada tren dan periode pada tooltip. Seri grafik harus konsisten antar layar; jangan memakai warna status merah hanya sebagai seri dekoratif. Pada HP, ringkasan utama didahulukan; tabel rinci dapat di-scroll dengan petunjuk yang jelas. Jangan membuat animasi grafik berulang atau angka yang bergerak tanpa perubahan data.

## 7. Dark mode, aksesibilitas, responsive

- **Existing:** tema gelap, breakpoint Tailwind `sm/md/lg`, navigasi HP terpisah, `role="status"` pada skeleton, `aria-busy` pada AI dan Refresh, `motion-safe` pada beberapa spinner. Logo resmi dipilih melalui `BrandLogo.jsx`.
- **Usulan:** uji teks kecil pada kartu gelap terhadap WCAG AA; target 4,5:1 untuk teks normal dan 3:1 untuk elemen grafis/teks besar. Jaga fokus terlihat, target sentuh memadai, urutan tab logis, dan label tombol icon-only. Jangan mengandalkan tooltip hover pada HP. Uji lebar 320–390 px, 768 px, dan desktop dengan data panjang/angka besar.
- Jangan menyatakan light mode tersedia hanya karena token `.dark` ada. Jika kelak ditambah, perlu keputusan desain dan audit kontras tersendiri.

## 8. Loading, empty, error, success

**Existing:** dashboard memakai skeleton saat fetch (`App.js`), boot memakai spinner, AI punya loading/error state (`AiAnalysisPanel.jsx`), Owner Report mempertahankan data saat refresh dan memberi timestamp (`OwnerReportPage.jsx`), form memakai toast dari Sonner, tabel live/input memiliki pesan empty.

**Panduan:** skeleton hanya untuk area yang benar-benar menunggu; saat refresh, pertahankan data lama dengan status “memperbarui”. Error perlu menyebut tindakan yang bisa dicoba tanpa membocorkan detail server. Success singkat dan tidak menutupi data. Empty state membedakan belum setup target, belum ada entri, dan periode kosong. Cegah submit/request ganda di UI dan backend. Jangan tampilkan angka sintetis saat loading.

## 9. Contoh SAMPE: lakukan / hindari

| Lakukan | Hindari |
| --- | --- |
| “Penjualan Rp12,4 jt dari target Rp20 jt; Waspada; periode Oktober” dalam urutan yang terbaca. | Kartu dengan angka besar tanpa target/periode dan hanya warna kuning. |
| Ringkasan AI memakai heading, bullet, waktu dibuat, dan status data usang. | Markdown mentah, teks promosi, atau animasi sparkles terus-menerus. |
| Owner Report menampilkan “Data diambil…” lalu angka terbaru saat Refresh Data selesai. | Mengosongkan semua KPI selama refresh atau memicu AI berbayar otomatis. |
| Tombol “Hapus entri” memiliki label aksesibel dan konfirmasi yang proporsional. | Ikon sampah tanpa nama/umpan balik. |
| Logo resmi pada ukuran yang tetap terbaca dan tidak terdistorsi. | Menggambar ulang mark, mengganti warna logo, atau memakai logo sebagai latar kartu. |

## 10. Prioritas UI polish berikutnya — belum diimplementasikan

| Area | Masalah berbukti di source | Rekomendasi | Prioritas | Risiko regresi |
| --- | --- | --- | --- | --- |
| Dashboard KPI | Kartu metrik berupa `Card`/`div` dengan `onClick` (`Dashboard.jsx`); teks sekunder `slate-500` pada `#161F30` berpotensi kontras rendah. | Jadikan kartu interaktif dapat dioperasikan keyboard; audit teks kecil dan pertahankan hierarki angka/target. | P0 | Sedang: klik detail dan layout grid. |
| List KPI & tanggal | Baris input memiliki icon-only delete tanpa nama aksesibel; form/tab lebar memakai banyak field (`DailyInput.jsx`). | Nama aksesibel, umpan balik hapus, audit fokus/target sentuh dan date picker pada HP. | P0 | Sedang: input data dan validasi. |
| Owner Report HP | Tabel `min-w-[560px]` dengan horizontal scroll (`OwnerReportPage.jsx`). | Uji data panjang di HP; beri petunjuk scroll atau presentasi baris yang lebih ringkas tanpa kehilangan rincian. | P1 | Sedang: keterbacaan dan cakupan data. |
| Modal Analisa AI | Sheet memiliki override animasi 220 ms; ringkasan panjang bergulir di panel (`AiAnalysisPanel.jsx`, `index.css`). | Uji fokus, close, scroll, dan heading pada layar kecil; konsistenkan loading/error. | P1 | Rendah–sedang: aksesibilitas panel. |
| Navigasi & onboarding | Mobile header menempatkan dua tab + selector bulan 130 px; wizard tujuh langkah (`TopNavbar.jsx`, `OnboardingWizard.jsx`). | Uji 320–390 px dan keyboard; ringkas progres/label tanpa mengubah alur bisnis. | P1 | Sedang: navigasi dan onboarding. |
| Loading/empty/feedback | Spinner boot `animate-spin` belum diberi `motion-safe`; beberapa pesan empty sangat singkat (`App.js`, `DailyInput.jsx`). | Selaraskan reduced motion, bedakan empty vs error, beri aksi pemulihan kontekstual. | P2 | Rendah. |

P0/P1/P2 adalah **prioritas rekomendasi**, bukan status bug production yang telah direproduksi. Pemeriksaan visual nyata di HP/desktop dan uji keyboard diperlukan sebelum patch.

## 11. Outline SEO dan panduan pelanggan — rencana saja

**Metadata existing:** `frontend/index.html` memiliki title dan description statis, favicon, `meta referrer=no-referrer`, serta injeksi `noindex,nofollow,noarchive` untuk `/report/`. Route SPA di `frontend/src/index.js`: `/admin`, `/aktivasi`, `/report/:shareId`, dan wildcard ke `AuthGate`. Tracked `frontend/public` belum memiliki `robots.txt` atau `sitemap.xml`; source yang diperiksa belum menunjukkan canonical atau Open Graph. Script Emergent dan PostHog masih dimuat pada halaman selain `/report/`; Google Login masih memakai Emergent Auth. Keberadaan metadata pada HTML SPA tidak membuktikan perilaku crawler atau header server production.

**Rencana SEO:** (1) putuskan landing page publik dan copy yang faktual; (2) title/description/canonical/OG untuk halaman publik; (3) `robots.txt` dan sitemap hanya untuk URL publik; (4) `noindex` dan header cache/referrer yang sesuai untuk admin, dashboard privat, aktivasi sensitif, dan Owner Report; (5) uji HTML yang diterima crawler tanpa sesi, bukan hanya DOM setelah JavaScript. Jangan menaruh link report bearer pada sitemap, analytics, atau OG. Evaluasi dependensi Emergent/PostHog sebelum mengubahnya; jangan memutus Google Login.

**Outline User Guide:** aktivasi lisensi dengan Ref ID → Google Login → onboarding target → isi KPI per modul/tanggal → baca status dan grafik → Analisa AI (biaya/ketergantungan layanan) → buat/rotasi/cabut link Owner Report → Refresh Data dan keamanan link. Sertakan contoh tanpa data pelanggan, definisi angka/target/prorata, troubleshooting yang aman, dan peringatan bahwa siapa pun yang memegang link report aktif dapat membaca laporan.

## 12. Keputusan pemilik sebelum UI/SEO implementation

1. Prioritas antara aksesibilitas kartu/input (P0) dan perapian visual P1; rekomendasi tim: selesaikan P0 dulu.
2. Apakah landing page publik baru diperlukan, dan klaim produk/CTA resmi yang boleh dipublikasikan. Source sekarang mengarahkan wildcard ke `AuthGate`.
3. Apakah dukungan light mode diinginkan kelak; V1 ini mendokumentasikan dark mode saja.
4. Apakah tabel Owner Report di HP lebih baik tetap scroll dengan petunjuk atau memakai layout baris; pilih setelah review data nyata dan visual.

Tidak ada perubahan UI, SEO, route, atau production dalam pekerjaan dokumentasi ini.
