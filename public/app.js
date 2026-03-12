const modeEl = document.getElementById("mode");
const resultEl = document.getElementById("result");
const statusBadge = document.getElementById("statusBadge");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");
const speakBtn = document.getElementById("speakBtn");
const voiceSelect = document.getElementById("voiceSelect");
const rateRange = document.getElementById("rateRange");
const rateValue = document.getElementById("rateValue");

const speechSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
let availableVoices = [];

const STORAGE_KEYS = {
  rate: "cg_voice_rate",
  voice: "cg_voice_name"
};

const initialRate = Number(localStorage.getItem(STORAGE_KEYS.rate) || "1.0");
rateRange.value = String(Number.isFinite(initialRate) ? initialRate : 1.0);
rateValue.textContent = Number(rateRange.value).toFixed(2);

if (!speechSupported) {
  speakBtn.disabled = true;
  speakBtn.title = "This browser does not support speech synthesis.";
  voiceSelect.disabled = true;
  rateRange.disabled = true;
}

function loadVoices() {
  if (!speechSupported) {
    return;
  }

  const allVoices = window.speechSynthesis.getVoices();
  const englishVoices = allVoices.filter((voice) => /^en([-_]|$)/i.test(voice.lang));

  // Keep the selector compact on mobile by exposing only a small English-only set.
  availableVoices = englishVoices.slice(0, 8);
  voiceSelect.innerHTML = "";

  if (!availableVoices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "English Default";
    voiceSelect.appendChild(option);
    return;
  }

  const savedVoiceName = localStorage.getItem(STORAGE_KEYS.voice) || "";

  availableVoices.forEach((voice, index) => {
    const option = document.createElement("option");
    option.value = voice.name;
    option.textContent = `${voice.name} (${voice.lang})`;
    if (voice.name === savedVoiceName) {
      option.selected = true;
    }
    if (!savedVoiceName && index === 0) {
      option.selected = true;
    }
    voiceSelect.appendChild(option);
  });
}

function setStatus(text, kind) {
  statusBadge.textContent = text;
  statusBadge.classList.remove("loading", "ok", "error");
  if (kind) {
    statusBadge.classList.add(kind);
  }
}

async function generateCommand() {
  const mode = modeEl.value;
  setStatus("Generating...", "loading");
  generateBtn.disabled = true;

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ mode })
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Generation failed");
    }

    resultEl.textContent = payload.text || "No result";
    setStatus("Done", "ok");
  } catch (error) {
    resultEl.textContent = `Error: ${error.message}`;
    setStatus("Error", "error");
  } finally {
    generateBtn.disabled = false;
  }
}

async function copyResult() {
  const text = resultEl.textContent.trim();
  if (!text) {
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setStatus("Copied", "ok");
  } catch (_error) {
    setStatus("Copy failed", "error");
  }
}

function speakResult() {
  if (!speechSupported) {
    setStatus("Speech not supported", "error");
    return;
  }

  const text = resultEl.textContent.trim();
  if (!text || text === "ここに生成結果が表示されます。") {
    setStatus("No text to speak", "error");
    return;
  }

  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    speakBtn.textContent = "Speak";
    setStatus("Stopped", "ok");
    return;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = Number(rateRange.value);
  utterance.pitch = 1.0;

  const selectedVoiceName = voiceSelect.value;
  const selectedVoice = availableVoices.find((voice) => voice.name === selectedVoiceName);
  if (selectedVoice) {
    utterance.voice = selectedVoice;
    utterance.lang = selectedVoice.lang;
  }

  utterance.onstart = () => {
    speakBtn.textContent = "Stop";
    setStatus("Speaking...", "loading");
  };

  utterance.onend = () => {
    speakBtn.textContent = "Speak";
    setStatus("Done speaking", "ok");
  };

  utterance.onerror = () => {
    speakBtn.textContent = "Speak";
    setStatus("Speech failed", "error");
  };

  window.speechSynthesis.speak(utterance);
}

rateRange.addEventListener("input", () => {
  const currentRate = Number(rateRange.value);
  rateValue.textContent = currentRate.toFixed(2);
  localStorage.setItem(STORAGE_KEYS.rate, String(currentRate));
});

voiceSelect.addEventListener("change", () => {
  localStorage.setItem(STORAGE_KEYS.voice, voiceSelect.value);
});

if (speechSupported) {
  loadVoices();
  window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
}

generateBtn.addEventListener("click", generateCommand);
copyBtn.addEventListener("click", copyResult);
speakBtn.addEventListener("click", speakResult);
