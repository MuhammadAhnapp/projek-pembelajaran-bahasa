# Language Buddy

Aplikasi latihan bahasa berbasis Python, Flask, dan Google Gemini.

## Fitur

1. **Chat bebas** — latihan bahasa berdasarkan topik pilihan sendiri.
2. **Skor percakapan otomatis** — setelah pengguna mengirim pesan, AI memperbarui skor tata bahasa, kosakata, kejelasan, skor keseluruhan, dan saran singkat.
3. **Kuis kosakata otomatis** — membuat lima soal pilihan ganda berdasarkan riwayat percakapan. Jawaban dan penjelasan ditampilkan setelah kuis diperiksa.
4. **Simulasi percakapan situasional** — pilih salah satu tema: Wawancara Kerja, Memesan Makanan di Restoran, Berbelanja, Komunikasi Daring, atau Bertamu.
5. **Pemilihan bahasa, level, dan tingkat koreksi** — opsi ini tersedia sebelum sesi dimulai.

> Skor adalah estimasi dari model AI untuk membantu latihan, bukan penilaian kemampuan bahasa resmi. Evaluasi memerlukan permintaan Gemini tambahan pada setiap giliran percakapan sehingga menggunakan kuota API.

## Cara menjalankan di Windows

1. Pastikan Python sudah terpasang.
2. Buka Command Prompt atau terminal di folder proyek ini.
3. Pasang dependensi:

   ```bash
   pip install -r requirements.txt
   ```

4. Buat file bernama `.env` di folder yang sama dengan `app.py` (atau salin dari proyek asli), lalu isi API key Gemini:

   ```env
   GEMINI_API_KEY=API_KEY_KAMU
   ```

   API key dapat dibuat melalui <https://aistudio.google.com/apikey>. Jangan membagikan file `.env` atau memasukkan API key ke repositori publik.

5. Jalankan aplikasi:

   ```bash
   python app.py
   ```

6. Buka <http://127.0.0.1:5050> pada browser.

## Struktur folder

```text
Kelompok Praktek/
├── app.py
├── .env
├── .env.example
├── requirements.txt
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── script.js
    └── style.css
```

Riwayat sesi disimpan di memori server, jadi sesi percakapan dapat hilang saat server dimulai ulang.

## Penanda kode yang baru ditambahkan

Pada file kode, cari komentar dengan awalan `FITUR BARU 1`, `FITUR BARU 2`, atau `FITUR BARU 3`. Komentar tersebut menandai blok utama yang ditambahkan untuk tugas pengembangan ini.

- **Fitur 1 — Evaluasi kemampuan bahasa:** pada `app.py`, lihat endpoint `/api/message` dan komentar evaluasi di dalamnya. Pada `static/script.js`, lihat `updateScorePanel()`. Pada `templates/index.html`, lihat elemen `scorePanel`.
- **Fitur 2 — Kuis kosakata:** pada `app.py`, lihat endpoint `/api/quiz`. Pada `static/script.js`, lihat `openQuiz()`, `renderQuiz()`, dan `submitQuiz()`. Struktur modalnya ada di `templates/index.html`.
- **Fitur 3 — Simulasi situasional:** pada `app.py`, lihat `SIMULATION_THEMES`, `build_system_prompt()`, dan endpoint `/api/start`. Pada `templates/index.html`, lihat pilihan mode dan `simulationOptions`. Pada `static/script.js`, lihat `setMode()` dan `startSession()`.

Baca juga file `PANDUAN_MENJELASKAN_FITUR.md` untuk ringkasan alur program dan contoh jawaban saat dosen bertanya.
