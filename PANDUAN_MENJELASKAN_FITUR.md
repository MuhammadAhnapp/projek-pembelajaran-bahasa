# Panduan Menjelaskan Fitur Baru Language Buddy

Dokumen ini merangkum bagian kode yang diberi komentar `FITUR BARU` agar mudah ditunjukkan saat presentasi atau menjawab pertanyaan dosen.

## Peta file

| File | Fungsi |
|---|---|
| `app.py` | Backend Flask: mengelola sesi chat, mengirim prompt ke Gemini, menghitung skor, membuat kuis, dan menyiapkan simulasi. |
| `templates/index.html` | Struktur tampilan: pilihan mode, pilihan tema, panel skor, tombol kuis, dan modal soal. |
| `static/script.js` | Interaksi browser: memulai sesi, mengirim pesan, memperbarui skor, memunculkan soal, dan menghitung nilai kuis. |
| `static/style.css` | Tampilan visual untuk menu mode, panel evaluasi, serta modal kuis. |

## Fitur 1 — Evaluasi kemampuan bahasa otomatis

**Bagian utama kode:**
- `app.py` → endpoint `send_message()` pada route `/api/message`.
- `app.py` → helper `transcript_for_ai(..., only_users=True)`.
- `static/script.js` → `updateScorePanel(scores)` dan bagian `sendMessage()` yang memanggil fungsi tersebut.
- `templates/index.html` → elemen `scorePanel`, `overallScore`, `grammarScore`, `vocabularyScore`, dan `clarityScore`.

**Alur kerjanya:** setelah pengguna mengirim pesan dan AI membalas, backend mengambil pesan pengguna dalam riwayat percakapan. Riwayat ini dikirim ke Gemini untuk menilai tiga aspek dengan rentang 0–100: tata bahasa (*grammar*), kosakata (*vocabulary*), dan kejelasan (*clarity*). Skor keseluruhan adalah rata-rata ketiga aspek. Backend mengirim hasil evaluasi bersama balasan chat; JavaScript menampilkan angka, progress bar, dan saran AI.

**Contoh jawaban ke dosen:**

> Skor dihitung oleh AI berdasarkan pesan yang dikirim pengguna sepanjang percakapan, bukan berdasarkan balasan AI. Penilaian dibagi menjadi tata bahasa, kosakata, dan kejelasan. Backend mengambil rata-rata ketiganya untuk skor keseluruhan, lalu frontend memperbarui panel skor setiap kali respons evaluasi diterima. Skor ini merupakan perkiraan untuk latihan, bukan sertifikat kemampuan bahasa resmi.

## Fitur 2 — Kuis kosakata otomatis

**Bagian utama kode:**
- `app.py` → endpoint `generate_vocabulary_quiz()` pada route `/api/quiz`.
- `app.py` → `generate_ai_json()` dan `transcript_for_ai()`, yang membantu meminta data kuis berdasarkan riwayat percakapan.
- `static/script.js` → `openQuiz()`, `renderQuiz()`, `submitQuiz()`, dan `closeQuiz()`.
- `templates/index.html` → tombol `quizBtn` dan modal `quizModal`.

**Alur kerjanya:** saat tombol Kuis Kosakata diklik, JavaScript meminta soal ke route `/api/quiz`. Backend mengirim riwayat percakapan, bahasa, dan level ke Gemini, lalu meminta lima soal pilihan ganda. Respons divalidasi agar pilihan jawabannya berjumlah empat dan indeks jawaban benar valid. Frontend menampilkan soal; saat pengguna memeriksa jawaban, JavaScript menghitung jumlah jawaban benar, mengubahnya menjadi persentase, dan menampilkan penjelasan.

**Contoh jawaban ke dosen:**

> Kuis dibuat secara dinamis berdasarkan riwayat percakapan, jadi kosakata yang diuji relevan dengan latihan pengguna. Backend meminta Gemini membentuk data soal dalam JSON, memvalidasinya, lalu mengirimkan soal ke frontend. Frontend menangani pilihan jawaban dan perhitungan nilai kuis.

## Fitur 3 — Simulasi percakapan situasional

**Tema tersedia:** Wawancara Kerja, Memesan Makanan di Restoran, Berbelanja, Komunikasi Daring, dan Bertamu.

**Bagian utama kode:**
- `app.py` → kamus `SIMULATION_THEMES`, fungsi `build_system_prompt()`, dan endpoint `start_session()` pada route `/api/start`.
- `templates/index.html` → tombol mode dengan atribut `data-mode`, elemen `simulationOptions`, dan pilihan `simulationTheme`.
- `static/script.js` → `setMode()` dan `startSession()`.

**Alur kerjanya:** pengguna memilih mode Simulasi Situasional, memilih bahasa dan level, lalu menentukan tema. JavaScript mengirim pilihan ini ke `/api/start`. Backend menggunakan `SIMULATION_THEMES` untuk memilih situasi dan peran yang harus dimainkan AI, menyusun instruksi sesuai level, lalu meminta AI membuat pesan pembuka. Setelah itu percakapan berjalan seperti chat biasa, tetapi AI mempertahankan peran sesuai skenario.

**Contoh jawaban ke dosen:**

> Simulasi menggunakan satu mekanisme chat yang sama, tetapi prompt sistemnya dibedakan berdasarkan tema. Contohnya pada tema restoran, AI berperan sebagai pelayan; pada wawancara kerja, AI berperan sebagai perekrut. Level yang dipilih ikut dikirim agar kosakata dan kompleksitas percakapan menyesuaikan kemampuan pengguna.

## Catatan teknis yang perlu diketahui

1. Skor saat ini dibuat lewat permintaan AI tambahan setiap kali pesan pengguna berhasil diproses; karena itu pemakaian kuota API lebih banyak dibanding chat saja.
2. Kuis memerlukan riwayat percakapan. Jika sesi baru belum memiliki percakapan yang cukup, backend mengirim pesan agar pengguna berlatih terlebih dahulu.
3. Jika Gemini/API bermasalah, fitur evaluasi atau kuis bisa gagal meskipun tampilan web berfungsi. Periksa pesan error dan konfigurasi `GEMINI_API_KEY` di file `.env`.
4. Untuk demonstrasi, tunjukkan terlebih dahulu menu mode di halaman awal, lalu lakukan beberapa pesan, perlihatkan panel skor, dan terakhir klik Kuis Kosakata.
