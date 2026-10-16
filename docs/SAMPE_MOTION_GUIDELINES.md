# SAMPE Motion Guidelines V1

Status: panduan internal untuk **Quiet Motion × Data-First SaaS**, 16 Oktober 2026. Tidak ada animasi baru yang diterapkan oleh dokumen ini. Angka pada kolom **Usulan** adalah target review, bukan token yang sudah ada di source.

## 1. Baseline yang benar-benar ada

- `frontend/package.json` mencantumkan `framer-motion@11.18.0`; pencarian import di `frontend/src` tidak menemukan pemakaian langsung. Jangan menyebut SAMPE sudah menggunakan Framer Motion pada layar aplikasi.
- Animasi berjalan melalui Tailwind CSS, `tw-animate-css`, Radix state classes, dan CSS lokal. `frontend/src/index.css` memiliki `fade-up` **500 ms**, `pulse-glow` **2 s infinite**, transisi panel Analisa AI **220 ms**, serta aturan reduced motion untuk panel dan glow.
- `ui/dialog.jsx` memakai entrance/exit berbasis data state sekitar **200 ms**. `ui/sheet.jsx` memiliki durasi dasar **500 ms saat buka** dan **300 ms saat tutup**; panel AI menimpa durasinya menjadi 220 ms.
- Spinner AI/Refresh memakai `motion-safe:animate-spin`; skeleton dashboard memakai `motion-reduce:animate-none`. Spinner boot di `App.js` masih `animate-spin` tanpa guard reduced motion. Kartu metrik memakai `animate-fade-up`; `glow-danger` dapat berulang pada tombol AI saat ada KPI merah.

## 2. Prinsip keputusan

Animasi harus menjawab salah satu hal: **apa yang baru muncul**, **apa yang berubah**, **apa yang sedang menunggu**, atau **apakah aksi berhasil/gagal**. Konten KPI harus tetap dapat dibaca segera. Jangan menganimasikan angka, target, dan grafik hanya agar layar tampak hidup.

| Gunakan | Kondisi tepat | Hindari |
| --- | --- | --- |
| CSS/Tailwind | Hover, focus, active, warna, opacity sederhana, spinner, skeleton, entrance tunggal yang tidak butuh koordinasi state React. | Banyak variasi duration/easing tanpa token bersama. |
| Motion/Framer Motion yang sudah terpasang | Enter/exit komponen yang benar-benar mount/unmount, koordinasi dua panel, atau perubahan layout yang sulit dinyatakan dengan CSS dan sudah teruji keyboard/reduced motion. | Mengimpor Motion untuk hover satu tombol, atau menganimasikan setiap KPI/card. |

Jika CSS sudah memenuhi kebutuhan, jangan menambah jalur runtime Motion. Tidak ada dependency baru yang diperlukan.

## 3. Durasi dan easing

| Peristiwa | Existing | Usulan V1 | Reduced motion |
| --- | --- | --- | --- |
| Hover/focus/active button | `transition-colors`, durasi default Tailwind | 100–150 ms, warna/opacity saja | Perubahan state langsung boleh; fokus tetap jelas. |
| Dialog/sheet masuk/keluar | Dialog ~200 ms; sheet umum 500/300 ms; AI override 220 ms | 180–240 ms, opacity + translate 8–12 px; exit 150–200 ms | Tanpa perpindahan; opacity singkat atau langsung. |
| Tab/navigasi | `transition-colors` di navbar; wizard progress 300 ms | 120–200 ms untuk indikator; konten baru tidak ditunda | Tanpa slide. |
| Feedback simpan/error | Toast Sonner, warna/status | 120–180 ms untuk reveal ringan; teks segera tersedia | Langsung. |
| Loading | Spinner dan skeleton | Mulai hanya jika request nyata; jangan menambah delay palsu | Ikon statis + teks status. |

**Usulan easing:** `ease-out` atau `cubic-bezier(0.22, 1, 0.36, 1)` untuk entrance; `ease-in` ringan untuk exit. Jangan menetapkan easing baru pada setiap komponen. Timing di atas perlu diuji pada HP kelas menengah sebelum menjadi token implementasi.

## 4. Pola per fitur

### Modal/dialog dan Analisa AI

- Pertahankan fokus Radix: fokus pindah ke panel saat buka, Esc/close tetap bekerja, fokus kembali ke trigger saat tutup. Jangan mengunci close hanya demi animasi.
- Gunakan satu perpindahan pendek + opacity untuk panel; overlay fade serempak. Hindari spring overshoot pada teks panjang atau data.
- Saat Analisa AI berjalan, satu indikator dan teks status cukup. Tombol trigger disabled serta `aria-busy` sudah ada (`Dashboard.jsx`, `TopNavbar.jsx`, `AiAnalysisPanel.jsx`); jangan menambahkan animasi berulang pada banyak elemen sekaligus.
- Sukses/error muncul tanpa menggeser seluruh viewport. Hasil Markdown harus dapat dibaca, dipilih, dan digulir tanpa animasi per paragraf.
- `glow-danger` 2 s infinite dan sparkle pulse saat loading adalah **existing**, bukan pola yang dianjurkan untuk diperluas. Review apakah sinyal KPI merah tetap jelas bila glow dihentikan.

### Owner Report

- `Refresh Data` hanya memutar icon saat request berjalan; tombol disabled dan `aria-busy` sudah ada (`OwnerReportPage.jsx`). Data lama tetap tampil saat refresh periode yang sama.
- Jangan menganimasikan ulang semua grafik/kartu ketika respons baru datang; cukup perbarui angka dan timestamp. Jika angka berubah, perubahan harus terbaca tanpa efek rolling counter.
- Jangan menghubungkan Refresh ke request SumoPod AI. Ringkasan AI hanya dibaca dari data tersimpan.
- Pada reduced motion, icon refresh diam dan teks “Memperbarui…” tetap menjelaskan status.

### Dashboard KPI dan grafik

- Skeleton hanya pada area dashboard yang benar-benar fetch (`App.js`); gunakan bentuk mendekati kartu/grafik nyata agar layout tidak meloncat. Jangan menampilkan data contoh sebagai placeholder.
- Entrance kartu `fade-up` 500 ms saat ini perlu evaluasi: jika membuat angka muncul terlambat, kurangi menjadi transisi singkat atau hilangkan. Jangan stagger semua kartu.
- Saat ganti bulan/tab, tampilkan indikator periode dan status fetch; jangan memutar grafik terus-menerus. Recharts sebaiknya tidak menganimasikan ulang seri besar pada setiap refresh jika mengganggu pembacaan.
- Pada tabel dan grafik, tooltip adalah bantuan; informasi angka tetap dapat dijangkau tanpa hover pada HP/keyboard.

### Input, validasi, hover/focus/active

- Hover: ubah border/warna/opacity saja. Focus: ring nyata dan tetap terlihat pada keyboard, tanpa pulse. Active: respons instan; perubahan skala kecil hanya jika tidak menggeser layout dan lulus uji sentuh.
- Validasi form: tampilkan pesan dekat field dan toast bila perlu; jangan mengguncang field. Error tidak boleh hilang sebelum dibaca.
- Tombol hapus dan tindakan berisiko harus punya nama aksesibel serta feedback keberhasilan/kegagalan. Motion tidak menggantikan konfirmasi.

## 5. Reduced motion dan aksesibilitas

Hormati `prefers-reduced-motion: reduce` pada **seluruh** jalur, bukan hanya panel AI. CSS: `motion-safe:` untuk loop/non-esensial dan `motion-reduce:animate-none` untuk skeleton; jika memakai Framer Motion, baca preferensi dengan `useReducedMotion()` lalu hilangkan translate/scale dan loop. Jangan menyembunyikan loading, error, atau fokus ketika animasi dimatikan. Periksa spinner boot `App.js` dan primitive Dialog/Sheet sebelum memperluas gerak.

Teks status dan `aria-live` menyampaikan progres tanpa perlu animasi. Jangan membuat hover sebagai satu-satunya petunjuk bahwa kartu dapat dibuka; kartu metrik saat ini memerlukan semantik keyboard terpisah dari motion.

## 6. Kinerja HP kelas menengah

- Animasikan terutama `opacity` dan `transform`; hindari width/height/top/left, filter blur, dan box-shadow besar per frame.
- Maksimal satu perhatian bergerak pada satu area. Hentikan spinner saat request selesai, panel tertutup, atau komponen unmount.
- Hindari parallax, glow berlebihan, animasi dekoratif berulang, dan animasi grafik terus-menerus.
- Ukur sebelum menerima perubahan: respons tap, kelancaran scroll Owner Report, waktu modal muncul, dan layout shift pada lebar 320–390 px dengan data panjang. Periksa juga preferensi reduced motion dan throttling CPU/perangkat kelas menengah.

## 7. Checklist review motion

1. Perubahan data/status tetap jelas tanpa animasi dan tanpa warna saja.
2. Gerak menunjukkan state nyata; tidak ada loading palsu atau request ganda.
3. Keyboard, fokus, Esc, dan screen reader tetap bekerja saat panel masuk/keluar.
4. Reduced motion menghapus perpindahan/loop tanpa menghilangkan informasi.
5. Tidak ada jank pada scroll HP, grafik, atau tabel data panjang.
6. Durasi mengikuti tabel usulan hanya setelah keputusan implementasi; jangan mengklaim nilai rekomendasi sudah menjadi token source.

Dokumen ini tidak memicu build, instalasi, deploy, atau perubahan kode aplikasi.
