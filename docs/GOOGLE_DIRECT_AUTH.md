# Google Direct Login

Mode ini belum aktif secara default. Jalur login lama tetap tersedia untuk rollback.

Untuk pengujian nonproduction, buat OAuth Client ID Google tipe Web application dengan origin yang sesuai, misalnya `http://localhost:3000`. Untuk production nantinya tambahkan `https://sampe.web.id`. Client ID bukan client secret; jangan memasukkan client secret ke frontend.

Konfigurasi frontend saat build: `REACT_APP_GOOGLE_DIRECT_AUTH=true` dan `REACT_APP_GOOGLE_CLIENT_ID=<client-id>`. Konfigurasi backend privat: `GOOGLE_DIRECT_AUTH_ENABLED=true`, `GOOGLE_CLIENT_ID=<client-id-yang-sama>`, dan `GOOGLE_AUTH_ALLOWED_ORIGINS=<origin-terpercaya-dipisahkan-koma>`. Keduanya harus cocok. HTTPS diwajibkan di production.

Migrasi `0004_google_identity` harus diuji pada database terisolasi sebelum ada rencana penerapan. Untuk rollback aplikasi gunakan flag frontend untuk kembali ke jalur lama dan nonaktifkan `GOOGLE_DIRECT_AUTH_ENABLED`; jangan menghapus tabel identitas. `GOOGLE_LEGACY_AUTH_ENABLED=false` hanya boleh dipakai setelah Google Direct tervalidasi dan rollback dipertimbangkan.

Google `sub` dipetakan ke `user_id` yang sama secara transaksional. Pengaitan pertama lewat email hanya diizinkan untuk Gmail atau alamat Workspace dengan klaim `hd` yang cocok dan email terverifikasi. Email pihak ketiga ditolak; selama masa transisi pelanggan dapat tetap memakai jalur lama. Prosedur aman yang diperlukan adalah pelanggan membuktikan kendali sesi SAMPE lama yang masih valid, lalu secara eksplisit mengonfirmasi pengaitan `sub` Google melalui alur akun yang terautentikasi dan terlindung CSRF. Alur pengaitan tersebut belum diimplementasikan, sehingga akun ini belum siap dipindahkan ke mode Direct saja. Jangan mengaitkan atau memindahkan lisensi secara manual berdasarkan email saja.

Google Client ID nyata, uji popup dan uji akun existing terhadap lingkungan yang aman masih diperlukan. Jangan mengaktifkan mode ini di production hanya berdasarkan tes mock.
