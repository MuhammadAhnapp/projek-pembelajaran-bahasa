#!/usr/bin/env python3
"""Language Buddy: chatbot latihan bahasa dengan evaluasi, kuis, dan simulasi.

CATATAN ARSITEKTUR (penting untuk hosting serverless seperti Vercel):
Versi ini TIDAK menyimpan riwayat percakapan di memori server. Setiap kali
frontend mengirim pesan, ia juga mengirim ulang seluruh riwayat percakapan
(history) yang sudah disimpannya sendiri di browser. Server hanya memproses
satu request lalu "lupa" lagi setelah selesai.

Kenapa didesain begini: platform serverless (Vercel, dll.) bisa menjalankan
tiap request di instance/container yang berbeda-beda, jadi data yang
disimpan di variabel Python biasa (dict, list global) TIDAK dijamin masih
ada saat request berikutnya datang. Dengan menaruh riwayat percakapan di
sisi browser, aplikasi ini jadi aman dijalankan di server mana pun --
termasuk yang auto-scaling atau yang me-restart proses kapan saja.
"""

import json
import os
import re
import sys
import time

from flask import Flask, jsonify, render_template, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    print("Library 'python-dotenv' belum terinstall. Jalankan: pip install python-dotenv")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Library 'google-genai' belum terinstall. Jalankan: pip install google-genai")
    sys.exit(1)

_env_models = os.environ.get("GEMINI_MODELS", "")
CANDIDATE_MODELS = [m.strip() for m in _env_models.split(",") if m.strip()] or [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]
MAX_TOKENS = 1024
EVALUATION_TOKENS = 384
QUIZ_TOKENS = 768
PORT = int(os.environ.get("PORT", "5050"))

# Batas jumlah giliran percakapan yang dikirim balik ke model, dan batas
# panjang tiap pesan, supaya payload tetap wajar dan biaya/latensi terkendali.
MAX_HISTORY_TURNS = 30
MAX_MESSAGE_CHARS = 4000

LEVELS = {
    "1": "Pemula (Beginner)",
    "2": "Menengah (Intermediate)",
    "3": "Mahir (Advanced)",
}

SIMULATION_THEMES = {
    "Wawancara Kerja": {
        "role": "pewawancara atau perekrut perusahaan",
        "situation": "pengguna sedang menjalani wawancara kerja",
        "opening": "Sapa kandidat dengan sopan, lalu ajukan pertanyaan wawancara pertama.",
    },
    "Memesan Makanan di Restoran": {
        "role": "pelayan restoran",
        "situation": "pengguna adalah pelanggan yang ingin memesan makanan dan minuman",
        "opening": "Sambut pelanggan dan tanyakan apa yang ingin dipesan.",
    },
    "Berbelanja": {
        "role": "pegawai toko",
        "situation": "pengguna adalah pelanggan yang sedang mencari atau membeli barang",
        "opening": "Sapa pelanggan dan tanyakan barang apa yang sedang dicari.",
    },
    "Komunikasi Daring": {
        "role": "rekan kerja atau teman dalam percakapan daring",
        "situation": "pengguna sedang berkomunikasi melalui chat atau rapat daring",
        "opening": "Mulai percakapan daring dengan sapaan yang wajar dan sebuah pertanyaan pembuka.",
    },
    "Bertamu": {
        "role": "tuan rumah yang menerima kunjungan pengguna",
        "situation": "pengguna datang bertamu ke rumah seseorang",
        "opening": "Sambut tamu dengan ramah dan persilakan masuk.",
    },
}

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("GEMINI_API_KEY belum di-set. Tambahkan ke file .env, misalnya:")
    print("GEMINI_API_KEY=key-kamu-disini")
    print("Dapatkan API key dari https://aistudio.google.com/apikey")
    sys.exit(1)

client = genai.Client(api_key=API_KEY, http_options=types.HttpOptions(timeout=20000))


def discover_models():
    """Deteksi model Flash yang aktif; daftar bawaan tetap dipakai jika gagal."""
    try:
        live = []
        for model in client.models.list():
            name = (model.name or "").replace("models/", "")
            actions = getattr(model, "supported_actions", None) or []
            if "flash" in name and "generateContent" in actions and not any(
                bad in name
                for bad in (
                    "image", "live", "audio", "tts", "embedding", "preview",
                    "omni", "latest", "thinking",
                )
            ):
                live.append(name)
        live.sort(reverse=True)
        if live:
            kept = [name for name in CANDIDATE_MODELS if name in live]
            for name in live[:4]:
                if name not in kept:
                    kept.append(name)
            CANDIDATE_MODELS[:] = kept
        print("Model aktif terdeteksi:", ", ".join(live[:8]) or "(tidak ada; memakai daftar bawaan)")
    except Exception as exc:
        print(f"Tidak bisa mendeteksi model ({exc}). Memakai daftar bawaan.")


# Catatan: variabel di bawah ini adalah state proses (bukan per-pengguna).
# Di server serverless, tiap instance punya salinannya sendiri yang reset
# saat cold start -- itu tidak masalah, karena ini cuma cache optimasi
# (urutan model mana yang dicoba duluan), bukan data milik pengguna.
COOLDOWN = {}
COOLDOWN_SECONDS = 60
DEAD_MODELS = set()


def is_dead_model_error(err):
    text = str(err).lower()
    return "404" in text or "not_found" in text or "limit: 0" in text


def is_transient_error(err):
    text = str(err).lower()
    return "503" in text or "unavailable" in text or "overloaded" in text or "deadline exceeded" in text


def explain_error(err):
    text = str(err or "")
    low = text.lower()
    if "404" in text or "not_found" in low or "no longer available" in low:
        return "Model Gemini tidak ditemukan atau sudah tidak tersedia. Periksa GEMINI_MODELS di environment variable."
    if "429" in text or "resource_exhausted" in low or "quota" in low:
        return "Kuota API Gemini habis atau terlalu banyak permintaan. Tunggu sebentar lalu coba lagi."
    if "api key" in low or "api_key" in low or "403" in text or "permission" in low or "401" in text:
        return "API key tidak valid atau tidak memiliki izin. Periksa GEMINI_API_KEY di environment variable."
    if "503" in text or "unavailable" in low or "overloaded" in low:
        return "Server Gemini sedang padat. Coba lagi dalam beberapa saat."
    return f"Terjadi kesalahan saat menghubungi Gemini: {text[:240]}" if text else "Tidak ada model Gemini yang tersedia."


def model_order():
    now = time.time()
    alive = [name for name in CANDIDATE_MODELS if name not in DEAD_MODELS]
    return [name for name in alive if COOLDOWN.get(name, 0) <= now] + [
        name for name in alive if COOLDOWN.get(name, 0) > now
    ]


def normalize_history(raw_history):
    """Validasi & bersihkan riwayat percakapan yang dikirim frontend."""
    cleaned = []
    for item in (raw_history or [])[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = "model" if item.get("role") == "model" else "user"
        text = str(item.get("text") or "").strip()[:MAX_MESSAGE_CHARS]
        if text:
            cleaned.append({"role": role, "text": text})
    return cleaned


def history_to_contents(history):
    """Ubah riwayat (list of {role, text}) menjadi list types.Content untuk Gemini."""
    return [
        types.Content(role=item["role"], parts=[types.Part(text=item["text"])])
        for item in history
    ]


def transcript_from_history(history, opening_instruction=None, max_items=18, only_users=False):
    """Susun riwayat menjadi teks yang dapat dikirim ke model evaluasi/kuis."""
    lines = []
    for item in history[-max_items:]:
        role = item["role"]
        text = item["text"]
        if opening_instruction and role == "user" and text == opening_instruction:
            continue
        if only_users and role != "user":
            continue
        label = "Pengguna" if role == "user" else "Buddy AI"
        lines.append(f"{label}: {text}")
    return "\n".join(lines) or "Belum ada riwayat percakapan."


def generate_ai_json(prompt, max_tokens=512):
    """Minta hasil JSON dari model yang tersedia, dengan fallback jika model gagal."""
    last_error = None
    for model_name in model_order():
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=max_tokens,
                    temperature=0.2,
                ),
            )
            raw = (getattr(response, "text", None) or "").strip()
            if not raw:
                raise ValueError("Model tidak mengembalikan isi JSON.")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}|\[.*\]", raw, flags=re.DOTALL)
                if not match:
                    raise ValueError("Format JSON dari model tidak valid.")
                return json.loads(match.group(0))
        except Exception as err:
            last_error = err
            if is_dead_model_error(err):
                DEAD_MODELS.add(model_name)
            elif is_transient_error(err):
                COOLDOWN[model_name] = time.time() + COOLDOWN_SECONDS
    raise RuntimeError(explain_error(last_error))


def build_system_prompt(language, level, topic, strictness="santai", mode="chat", scenario=None):
    strictness_instructions = {
        "santai": "Koreksi hanya kesalahan yang mengganggu pemahaman. Utamakan kelancaran percakapan.",
        "sedang": "Koreksi kesalahan tata bahasa dan pilihan kata yang umum secara wajar.",
        "ketat": "Koreksi secara teliti, termasuk tata bahasa, ejaan, dan pilihan kata.",
    }
    selected_strictness = strictness_instructions.get(strictness, strictness_instructions["santai"])
    base_prompt = f"""Kamu adalah Language Buddy, partner latihan bahasa yang ramah dan sabar.
Bahasa target: {language}.
Level pengguna: {level}. Sesuaikan panjang kalimat, kosakata, dan kompleksitas dengan level tersebut.
Tingkat koreksi: {selected_strictness}

Aturan:
1. Lakukan percakapan terutama dalam {language}.
2. Jika perlu menjelaskan kesalahan tata bahasa, gunakan Bahasa Indonesia agar mudah dipahami.
3. Jangan mengarang skor atau menampilkan laporan evaluasi di dalam pesan percakapan.
4. Bersikap suportif dan ajukan satu pertanyaan atau respons yang membantu percakapan berlanjut.
5. Bila ada koreksi, gunakan format:
KOREKSI: [kalimat salah] -> [kalimat benar]
PENJELASAN: [penjelasan singkat dalam Bahasa Indonesia]
"""
    if mode == "simulation":
        details = SIMULATION_THEMES.get(scenario, SIMULATION_THEMES["Wawancara Kerja"])
        return base_prompt + f"""
MODE: SIMULASI PERCAKAPAN SITUASIONAL.
Tema: {scenario}.
Situasi: {details['situation']}.
Peranmu: {details['role']}.
Aturan simulasi:
- Tetap berada dalam peran dan buat percakapan terasa realistis.
- Mulai percakapan sesuai arahan pembuka skenario.
- Ucapkan satu atau dua kalimat per giliran, lalu tunggu jawaban pengguna.
- Jangan menjawab atas nama pengguna atau menyelesaikan seluruh percakapan sendiri.
- Gunakan ungkapan yang cocok dengan level {level}.
"""
    return base_prompt + f"\nTopik percakapan bebas pengguna: {topic}. Bantu pengguna berlatih secara natural."


# static_folder dimatikan dan diganti rute manual di bawah, karena Vercel
# merekomendasikan untuk tidak mengandalkan Flask static_folder bawaan.
app = Flask(__name__, static_folder=None)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.route("/static/<path:filename>", endpoint="static")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/")
def index():
    return render_template(
        "index.html",
        levels=LEVELS,
        simulation_themes=list(SIMULATION_THEMES.keys()),
    )


@app.route("/api/start", methods=["POST"])
def start_session():
    data = request.get_json(silent=True) or {}
    language = (data.get("language") or "Inggris").strip()
    level_key = str(data.get("level") or "1")
    level_label = LEVELS.get(level_key, LEVELS["1"])
    mode = data.get("mode") if data.get("mode") in ("chat", "simulation") else "chat"
    strictness = (data.get("strictness") or "santai").lower()
    if strictness not in ("santai", "sedang", "ketat"):
        strictness = "santai"

    if mode == "simulation":
        scenario = data.get("simulation_theme") or "Wawancara Kerja"
        if scenario not in SIMULATION_THEMES:
            return jsonify({"error": "Tema simulasi tidak dikenal."}), 400
        topic = scenario
    else:
        scenario = None
        topic = (data.get("topic") or "bebas, apa saja").strip() or "bebas, apa saja"

    system_prompt = build_system_prompt(language, level_label, topic, strictness, mode, scenario)

    opening_message = None
    opening_instruction = None
    selected_model = None

    if mode == "simulation":
        details = SIMULATION_THEMES[scenario]
        opening_instruction = (
            f"Mulai simulasi sekarang. {details['opening']} "
            f"Gunakan {language} pada level {level_label}."
        )
        last_error = None
        for model_name in model_order():
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[types.Content(role="user", parts=[types.Part(text=opening_instruction)])],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=MAX_TOKENS,
                    ),
                )
                text = (getattr(response, "text", None) or "").strip()
                if text:
                    opening_message = text
                    selected_model = model_name
                    COOLDOWN.pop(model_name, None)
                    break
            except Exception as err:
                last_error = err
                if is_dead_model_error(err):
                    DEAD_MODELS.add(model_name)
                elif is_transient_error(err):
                    COOLDOWN[model_name] = time.time() + COOLDOWN_SECONDS
        if not opening_message:
            # Sesi tetap bisa dipakai walau pesan pembuka gagal dibuat.
            print(f"Tidak dapat membuat pembuka simulasi: {last_error}")

    return jsonify({
        "ok": True,
        "level_label": level_label,
        "mode": mode,
        "scenario": scenario,
        "opening_message": opening_message,
        "opening_instruction": opening_instruction,
        "model": selected_model,
    })


@app.route("/api/message", methods=["POST"])
def send_message():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Pesan tidak boleh kosong."}), 400
    user_message = user_message[:MAX_MESSAGE_CHARS]

    language = (data.get("language") or "Inggris").strip()
    level_key = str(data.get("level") or "1")
    level_label = LEVELS.get(level_key, LEVELS["1"])
    mode = data.get("mode") if data.get("mode") in ("chat", "simulation") else "chat"
    strictness = (data.get("strictness") or "santai").lower()
    if strictness not in ("santai", "sedang", "ketat"):
        strictness = "santai"
    scenario = data.get("scenario") if mode == "simulation" else None
    topic = (data.get("topic") or "bebas, apa saja").strip() or "bebas, apa saja"
    opening_instruction = data.get("opening_instruction")
    history = normalize_history(data.get("history"))

    system_prompt = build_system_prompt(language, level_label, topic, strictness, mode, scenario)
    contents = history_to_contents(history) + [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]

    last_error = None
    reply = None
    replied_model = None
    for model_name in model_order():
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=MAX_TOKENS,
                    ),
                )
                reply = (getattr(response, "text", None) or "").strip()
                if not reply:
                    raise ValueError("Model tidak mengembalikan balasan.")
                replied_model = model_name
                COOLDOWN.pop(model_name, None)
                break
            except Exception as err:
                last_error = err
                if is_dead_model_error(err):
                    DEAD_MODELS.add(model_name)
                    break
                if is_transient_error(err):
                    if attempt == 0:
                        time.sleep(1)
                        continue
                    COOLDOWN[model_name] = time.time() + COOLDOWN_SECONDS
                break
        if reply:
            break

    if not reply:
        return jsonify({"error": explain_error(last_error)}), 500

    # Evaluasi skor tata bahasa/kosakata/kejelasan; kegagalan di sini tidak
    # membatalkan balasan chat yang sudah berhasil didapat.
    evaluation = None
    try:
        updated_history = history + [
            {"role": "user", "text": user_message},
            {"role": "model", "text": reply},
        ]
        user_transcript = transcript_from_history(
            updated_history, opening_instruction=opening_instruction, max_items=32, only_users=True
        )
        prompt = f"""Kamu adalah penilai pembelajaran bahasa. Evaluasi kemampuan pengguna berdasarkan pesan-pesan PENGGUNA berikut.
Bahasa target: {language}.
Level pembelajaran: {level_label}.
Pesan pengguna:
{user_transcript[-7000:]}

Nilai secara suportif dan sesuai level, bukan seperti ujian penutur asli. Berikan skor 0 sampai 100 untuk:
- grammar: ketepatan tata bahasa
- vocabulary: ketepatan dan variasi kosakata
- clarity: kejelasan makna dan kemampuan menyampaikan maksud
Nilai mencerminkan kualitas percakapan pengguna sampai saat ini, terutama pesan-pesan terbarunya. Jangan menilai pesan AI.
Kembalikan hanya JSON valid dengan bentuk:
{{"grammar": 0, "vocabulary": 0, "clarity": 0, "feedback": "satu atau dua kalimat singkat dalam Bahasa Indonesia"}}
"""
        result = generate_ai_json(prompt, max_tokens=EVALUATION_TOKENS)
        scores = {}
        for key in ("grammar", "vocabulary", "clarity"):
            try:
                scores[key] = max(0, min(100, int(round(float(result.get(key, 0))))))
            except (TypeError, ValueError):
                scores[key] = 0
        scores["overall"] = int(round(sum(scores.values()) / 3))
        scores["feedback"] = str(result.get("feedback") or "Terus berlatih agar kemampuan bahasa semakin meningkat.")[:360]
        evaluation = scores
    except Exception as err:
        print(f"Evaluasi skor belum berhasil dibuat: {err}")

    return jsonify({"reply": reply, "evaluation": evaluation, "model": replied_model})


@app.route("/api/quiz", methods=["POST"])
def generate_vocabulary_quiz():
    data = request.get_json(silent=True) or {}
    history = normalize_history(data.get("history"))
    language = (data.get("language") or "Inggris").strip()
    level_key = str(data.get("level") or "1")
    level_label = LEVELS.get(level_key, LEVELS["1"])
    opening_instruction = data.get("opening_instruction")

    transcript = transcript_from_history(history, opening_instruction=opening_instruction, max_items=24)
    if transcript == "Belum ada riwayat percakapan.":
        return jsonify({"error": "Lakukan beberapa giliran percakapan terlebih dahulu agar kuis sesuai dengan kosakata yang dipelajari."}), 400

    prompt = f"""Buat kuis kosakata otomatis berdasarkan kata dan ungkapan dalam percakapan berikut.
Bahasa target: {language}.
Level: {level_label}.
Percakapan:
{transcript[-6000:]}

Buat 5 soal pilihan ganda yang berbeda. Utamakan kosakata yang benar-benar muncul atau relevan dengan percakapan. Pertanyaan dan penjelasan ditulis dalam Bahasa Indonesia; kata target dan contoh frasa tetap dalam bahasa target. Tiap soal harus memiliki tepat 4 pilihan jawaban dan hanya satu jawaban benar. Variasikan arti kata, pemilihan kata dalam konteks, dan ungkapan yang digunakan.
Kembalikan hanya JSON valid dengan bentuk:
{{"questions":[{{"word":"word/frasa target","question":"Apa arti ...?","options":["...","...","...","..."],"answer_index":0,"explanation":"Penjelasan singkat dalam Bahasa Indonesia."}}]}}
"""
    try:
        result = generate_ai_json(prompt, max_tokens=QUIZ_TOKENS)
        raw_questions = result.get("questions", []) if isinstance(result, dict) else []
        questions = []
        for question in raw_questions[:5]:
            options = question.get("options") if isinstance(question, dict) else None
            if not isinstance(options, list) or len(options) != 4:
                continue
            try:
                answer_index = int(question.get("answer_index", -1))
            except (TypeError, ValueError):
                continue
            if not 0 <= answer_index <= 3:
                continue
            questions.append({
                "word": str(question.get("word") or "Kosakata")[:100],
                "question": str(question.get("question") or "Pilih jawaban yang tepat.")[:300],
                "options": [str(option)[:180] for option in options],
                "answer_index": answer_index,
                "explanation": str(question.get("explanation") or "")[:360],
            })
        if len(questions) < 3:
            raise ValueError("Kuis yang dihasilkan belum lengkap. Silakan coba lagi.")
        return jsonify({"questions": questions})
    except Exception as err:
        return jsonify({"error": str(err) or "Kuis belum dapat dibuat. Coba lagi."}), 502


if __name__ == "__main__":
    discover_models()
    print(f"\nLanguage Buddy berjalan di http://127.0.0.1:{PORT}\n")
    try:
        app.run(debug=True, host="127.0.0.1", port=PORT)
    except OSError as err:
        print(f"Gagal menjalankan server di port {PORT}: {err}")
        print("Ganti nilai PORT atau tutup aplikasi lain yang memakai port tersebut.")
        sys.exit(1)
