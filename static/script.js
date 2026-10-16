const setupScreen = document.getElementById("setupScreen");
const chatLayout = document.getElementById("chatLayout");
const startBtn = document.getElementById("startBtn");
const endBtn = document.getElementById("endBtn");
const sendBtn = document.getElementById("sendBtn");
const quizBtn = document.getElementById("quizBtn");
const userInput = document.getElementById("userInput");
const messages = document.getElementById("messages");
const metaInfo = document.getElementById("metaInfo");
const quizModal = document.getElementById("quizModal");
const quizContent = document.getElementById("quizContent");
const quizFooter = document.getElementById("quizFooter");
const quizSubmitBtn = document.getElementById("quizSubmitBtn");
const quizProgress = document.getElementById("quizProgress");

let quizState = null;

// Riwayat percakapan disimpan di browser (bukan di server) supaya aplikasi
// ini bisa jalan di server serverless seperti Vercel. Setiap kali kirim
// pesan, seluruh riwayat ini dikirim ulang ke backend sebagai konteks.
let convo = {
  language: "",
  level: "1",
  mode: "chat",
  scenario: null,
  strictness: "santai",
  topic: "",
  openingInstruction: null,
  history: [],
};

startBtn.addEventListener("click", startSession);
endBtn.addEventListener("click", () => window.location.reload());
sendBtn.addEventListener("click", sendMessage);
quizBtn.addEventListener("click", openQuiz);
document.getElementById("closeQuizBtn").addEventListener("click", closeQuiz);
quizSubmitBtn.addEventListener("click", submitQuiz);
userInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendMessage();
});
quizModal.addEventListener("click", (event) => {
  if (event.target === quizModal) closeQuiz();
});

// >>> FITUR BARU 3: mengubah pilihan mode dan menampilkan opsi yang sesuai (chat atau simulasi).
function setMode(mode) {
  document.getElementById("mode").value = mode;
  document.querySelectorAll(".mode-card").forEach((button) => {
    const active = button.dataset.mode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });

  document.getElementById("chatOptions").classList.toggle("hidden", mode !== "chat");
  document.getElementById("simulationOptions").classList.toggle("hidden", mode !== "simulation");
  startBtn.textContent = mode === "simulation" ? "Mulai Simulasi" : "Mulai Chat";
}

document.querySelectorAll(".mode-card").forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

// >>> FITUR BARU 3: kirim pilihan bahasa, level, mode, dan tema ke endpoint /api/start.
async function startSession() {
  const language = document.getElementById("language").value.trim() || "Inggris";
  const level = document.getElementById("level").value || "1";
  const mode = document.getElementById("mode").value || "chat";
  const topic = document.getElementById("topic").value.trim() || "bebas, apa saja";
  const strictness = document.getElementById("strictness").value || "santai";
  const simulationTheme = document.getElementById("simulationTheme").value;
  const originalLabel = mode === "simulation" ? "Mulai Simulasi" : "Mulai Chat";

  startBtn.disabled = true;
  startBtn.textContent = "Menyiapkan...";

  try {
    const response = await fetch("/api/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language, level, mode, topic, strictness, simulation_theme: simulationTheme }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Gagal memulai sesi.");

    // Simpan konteks sesi ini di browser; tidak ada apa pun yang disimpan di server.
    convo = {
      language,
      level,
      mode,
      scenario: data.scenario || null,
      strictness,
      topic,
      openingInstruction: data.opening_instruction || null,
      history: [],
    };
    if (mode === "simulation" && data.opening_instruction && data.opening_message) {
      convo.history.push({ role: "user", text: data.opening_instruction });
      convo.history.push({ role: "model", text: data.opening_message });
    }

    const modeLabel = mode === "simulation" ? `Simulasi: ${data.scenario || simulationTheme}` : `Chat: ${topic}`;
    metaInfo.textContent = `${language} · ${data.level_label || level} · ${modeLabel}`;
    messages.replaceChildren();
    resetScorePanel();
    setupScreen.classList.add("hidden");
    chatLayout.classList.remove("hidden");

    if (data.opening_message) addMessage("bot", data.opening_message, null);
    else if (mode === "simulation") addMessage("bot", "Simulasi siap. Ketik jawabanmu untuk memulai percakapan.", null);
    userInput.focus();
  } catch (error) {
    window.alert(error.message);
  } finally {
    startBtn.disabled = false;
    startBtn.textContent = originalLabel;
  }
}

function addMessage(role, text, correction) {
  const wrapper = document.createElement("div");
  wrapper.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrapper.appendChild(bubble);

  if (correction) {
    const box = document.createElement("div");
    box.className = "correction";
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = "Koreksi";
    box.appendChild(label);
    box.appendChild(document.createTextNode(correction));
    wrapper.appendChild(box);
  }

  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

function parseReply(raw) {
  const marker = raw.indexOf("KOREKSI:");
  if (marker === -1) return { main: raw.trim(), correction: null };
  return {
    main: raw.slice(0, marker).trim(),
    correction: raw.slice(marker).replace("KOREKSI:", "").trim(),
  };
}

function addTypingIndicator() {
  const typing = document.createElement("div");
  typing.className = "typing";
  typing.textContent = "Buddy sedang mengetik dan menilai percakapan...";
  typing.id = "typingIndicator";
  messages.appendChild(typing);
  messages.scrollTop = messages.scrollHeight;
  return typing;
}

// >>> FITUR BARU 1: setelah pesan dikirim, frontend menerima balasan chat dan data evaluasi skor.
async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || sendBtn.disabled) return;

  userInput.value = "";
  addMessage("user", text, null);
  const typing = addTypingIndicator();
  sendBtn.disabled = true;
  userInput.disabled = true;

  try {
    const response = await fetch("/api/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        history: convo.history,
        language: convo.language,
        level: convo.level,
        mode: convo.mode,
        scenario: convo.scenario,
        strictness: convo.strictness,
        topic: convo.topic,
        opening_instruction: convo.openingInstruction,
      }),
    });
    const data = await response.json();
    typing.remove();
    if (!response.ok) throw new Error(data.error || "Terjadi kesalahan saat mengirim pesan.");

    const parsed = parseReply(data.reply || "");
    addMessage("bot", parsed.main || data.reply || "", parsed.correction);
    // Simpan giliran ini (teks balasan AI apa adanya) supaya jadi konteks pesan berikutnya.
    convo.history.push({ role: "user", text });
    convo.history.push({ role: "model", text: data.reply || "" });
    if (data.evaluation) updateScorePanel(data.evaluation);
    else {
      document.getElementById("scoreStatus").textContent = "Pesan terkirim; skor belum berhasil diperbarui.";
    }
  } catch (error) {
    typing.remove();
    addMessage("bot", `Pesan belum berhasil diproses: ${error.message}`, null);
  } finally {
    sendBtn.disabled = false;
    userInput.disabled = false;
    userInput.focus();
  }
}

// >>> FITUR BARU 1: kembalikan tampilan skor ke kondisi awal saat sesi baru dimulai.
function resetScorePanel() {
  document.getElementById("overallScore").textContent = "--";
  document.getElementById("grammarScore").textContent = "--";
  document.getElementById("vocabularyScore").textContent = "--";
  document.getElementById("clarityScore").textContent = "--";
  document.getElementById("grammarBar").style.width = "0%";
  document.getElementById("vocabularyBar").style.width = "0%";
  document.getElementById("clarityBar").style.width = "0%";
  document.getElementById("scoreStatus").textContent = "Skor muncul setelah pesan pertama.";
  document.getElementById("scoreFeedback").textContent = "Mulai percakapan untuk mendapatkan saran belajar.";
}

// >>> FITUR BARU 1: tampilkan skor dari backend dan sesuaikan panjang progress bar di panel evaluasi.
function updateScorePanel(scores) {
  const values = {
    overall: clampScore(scores.overall),
    grammar: clampScore(scores.grammar),
    vocabulary: clampScore(scores.vocabulary),
    clarity: clampScore(scores.clarity),
  };
  document.getElementById("overallScore").textContent = values.overall;
  document.getElementById("grammarScore").textContent = values.grammar;
  document.getElementById("vocabularyScore").textContent = values.vocabulary;
  document.getElementById("clarityScore").textContent = values.clarity;
  document.getElementById("grammarBar").style.width = `${values.grammar}%`;
  document.getElementById("vocabularyBar").style.width = `${values.vocabulary}%`;
  document.getElementById("clarityBar").style.width = `${values.clarity}%`;
  document.getElementById("scoreStatus").textContent = scoreDescription(values.overall);
  document.getElementById("scoreFeedback").textContent = scores.feedback || "Terus berlatih secara konsisten.";
}

function clampScore(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : 0;
}

function scoreDescription(score) {
  if (score >= 90) return "Sangat baik. Pertahankan!";
  if (score >= 75) return "Bagus, terus tingkatkan.";
  if (score >= 60) return "Cukup baik; masih ada ruang untuk berkembang.";
  return "Terus berlatih. Kesalahan adalah bagian dari belajar.";
}

// >>> FITUR BARU 2: buka modal, minta soal dari /api/quiz, lalu tampilkan status loading/error/soal.
async function openQuiz() {
  quizModal.classList.remove("hidden");
  quizContent.replaceChildren();
  quizFooter.classList.add("hidden");
  quizSubmitBtn.disabled = true;
  const loading = document.createElement("p");
  loading.className = "quiz-loading";
  loading.textContent = "Buddy sedang menyiapkan kuis kosakata...";
  quizContent.appendChild(loading);

  try {
    const response = await fetch("/api/quiz", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        history: convo.history,
        language: convo.language,
        level: convo.level,
        opening_instruction: convo.openingInstruction,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Kuis belum dapat dibuat.");
    quizState = { questions: data.questions || [], submitted: false };
    if (quizState.questions.length === 0) throw new Error("Belum ada soal yang bisa ditampilkan.");
    renderQuiz();
  } catch (error) {
    quizContent.replaceChildren();
    const message = document.createElement("p");
    message.className = "quiz-error";
    message.textContent = error.message;
    quizContent.appendChild(message);
    quizState = null;
  } finally {
    quizSubmitBtn.disabled = false;
  }
}

// >>> FITUR BARU 2: buat elemen soal dan empat pilihan jawaban secara dinamis dari respons AI.
function renderQuiz() {
  quizContent.replaceChildren();
  const questions = quizState.questions;
  questions.forEach((question, index) => {
    const card = document.createElement("fieldset");
    card.className = "quiz-question";
    const legend = document.createElement("legend");
    legend.textContent = `${index + 1}. ${question.question}`;
    card.appendChild(legend);

    const word = document.createElement("p");
    word.className = "quiz-word";
    word.textContent = question.word;
    card.appendChild(word);

    const optionList = document.createElement("div");
    optionList.className = "quiz-options";
    question.options.forEach((option, optionIndex) => {
      const label = document.createElement("label");
      label.className = "quiz-option";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `quiz-question-${index}`;
      input.value = String(optionIndex);
      input.disabled = quizState.submitted;
      const text = document.createElement("span");
      text.textContent = option;
      label.append(input, text);
      optionList.appendChild(label);
    });
    card.appendChild(optionList);

    const explanation = document.createElement("p");
    explanation.className = "quiz-explanation hidden";
    explanation.id = `quiz-explanation-${index}`;
    explanation.textContent = `Jawaban benar: ${question.options[question.answer_index]}. ${question.explanation || ""}`;
    card.appendChild(explanation);
    quizContent.appendChild(card);
  });

  quizProgress.textContent = `${questions.length} soal`;
  quizFooter.classList.remove("hidden");
  quizSubmitBtn.textContent = quizState.submitted ? "Selesai" : "Periksa Jawaban";
  quizSubmitBtn.disabled = false;
}

// >>> FITUR BARU 2: periksa jawaban, hitung nilai, dan tampilkan jawaban benar beserta penjelasannya.
function submitQuiz() {
  if (!quizState) {
    closeQuiz();
    return;
  }
  if (quizState.submitted) {
    closeQuiz();
    return;
  }

  let correct = 0;
  quizState.questions.forEach((question, index) => {
    const selected = document.querySelector(`input[name="quiz-question-${index}"]:checked`);
    const selectedValue = selected ? Number(selected.value) : -1;
    const card = quizContent.querySelectorAll(".quiz-question")[index];
    card.classList.add(selectedValue === question.answer_index ? "answer-correct" : "answer-wrong");
    if (selectedValue === question.answer_index) correct += 1;
    const explanation = document.getElementById(`quiz-explanation-${index}`);
    explanation.classList.remove("hidden");
    card.querySelectorAll("input").forEach((input) => { input.disabled = true; });
  });

  quizState.submitted = true;
  const percent = Math.round((correct / quizState.questions.length) * 100);
  quizProgress.textContent = `Nilai kuis: ${correct}/${quizState.questions.length} (${percent}%)`;
  quizSubmitBtn.textContent = "Selesai";
}

// >>> FITUR BARU 2: tutup modal dan hapus status kuis dari memori frontend.
function closeQuiz() {
  quizModal.classList.add("hidden");
  quizState = null;
}

function setupCustomDropdown(dropdownId, selectedId, menuId, textId, hiddenInputId, itemSelector) {
  const selected = document.getElementById(selectedId);
  const menu = document.getElementById(menuId);
  const selectedText = document.getElementById(textId);
  const hiddenInput = document.getElementById(hiddenInputId);
  if (!selected || !menu || !selectedText || !hiddenInput) return;

  const items = menu.querySelectorAll(itemSelector);
  selected.addEventListener("click", (event) => {
    event.stopPropagation();
    document.querySelectorAll(".dropdown-menu").forEach((otherMenu) => {
      if (otherMenu !== menu) {
        otherMenu.classList.add("hidden");
        const otherButton = otherMenu.parentElement.querySelector(".dropdown-selected");
        if (otherButton) {
          otherButton.setAttribute("aria-expanded", "false");
          const arrow = otherButton.querySelector(".arrow");
          if (arrow) arrow.style.transform = "rotate(0deg)";
        }
      }
    });
    menu.classList.toggle("hidden");
    const expanded = !menu.classList.contains("hidden");
    selected.setAttribute("aria-expanded", String(expanded));
    const arrow = selected.querySelector(".arrow");
    if (arrow) arrow.style.transform = expanded ? "rotate(180deg)" : "rotate(0deg)";
  });

  items.forEach((item) => {
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      items.forEach((other) => {
        other.classList.remove("active");
        other.setAttribute("aria-selected", "false");
      });
      item.classList.add("active");
      item.setAttribute("aria-selected", "true");
      selectedText.textContent = item.textContent.trim();
      hiddenInput.value = item.dataset.value;
      menu.classList.add("hidden");
      selected.setAttribute("aria-expanded", "false");
      const arrow = selected.querySelector(".arrow");
      if (arrow) arrow.style.transform = "rotate(0deg)";
    });
  });
}

document.addEventListener("click", () => {
  document.querySelectorAll(".dropdown-menu").forEach((menu) => {
    menu.classList.add("hidden");
    const button = menu.parentElement.querySelector(".dropdown-selected");
    if (button) {
      button.setAttribute("aria-expanded", "false");
      const arrow = button.querySelector(".arrow");
      if (arrow) arrow.style.transform = "rotate(0deg)";
    }
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const welcomeOverlay = document.getElementById("welcomeOverlay");
  if (welcomeOverlay) {
    window.setTimeout(() => welcomeOverlay.classList.add("fade-out"), 1400);
  }

  setupCustomDropdown("languageDropdown", "dropdownSelected", "dropdownMenu", "selectedText", "language", ".dropdown-item");
  setupCustomDropdown("levelDropdown", "levelSelected", "levelMenu", "selectedLevelText", "level", ".level-item");
  setupCustomDropdown("strictnessDropdown", "strictnessSelected", "strictnessMenu", "selectedStrictnessText", "strictness", ".strictness-item");
  setMode("chat");
});
