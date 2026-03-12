const modeEl = document.getElementById("mode");
const resultEl = document.getElementById("result");
const statusBadge = document.getElementById("statusBadge");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");
const speakBtn = document.getElementById("speakBtn");
const qrBtn = document.getElementById("qrBtn");
const qrSection = document.getElementById("qrSection");
const qrImage = document.getElementById("qrImage");
const qrDownload = document.getElementById("qrDownload");
const voiceSelect = document.getElementById("voiceSelect");
const rateRange = document.getElementById("rateRange");
const rateValue = document.getElementById("rateValue");

const speechSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
let cleanEnglishVoices = [];
const presetVoiceMap = new Map();

const VOICE_PRESETS = [
  { id: "devis", label: "devis", keywords: ["devis", "davis", "guy", "daniel", "arthur"] },
  { id: "ryan", label: "ryan", keywords: ["ryan", "george", "liam", "james"] },
  { id: "andrew", label: "andrew", keywords: ["andrew", "christopher", "mark", "brian"] },
  { id: "david", label: "david", keywords: ["microsoft david", "david", "alex"] },
  { id: "aria", label: "aria", keywords: ["aria", "samantha", "jenny", "emma"] },
  { id: "natasha", label: "natasha", keywords: ["natasha", "ava", "olivia", "victoria"] },
  { id: "susan", label: "susan", keywords: ["susan", "michelle", "karen", "allison", "joanna"] },
  { id: "zira", label: "zira", keywords: ["microsoft zira", "zira", "serena"] }
];

const BAD_VOICE_NAME_PATTERN = /whisper|novelty|robot|child|kid|silly|bells|boing|trinoids|bad news|hysterical|sing/i;

const STORAGE_KEYS = {
  rate: "cg_voice_rate",
  voice: "cg_voice_preset"
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

function findPresetVoice(preset, voices, usedVoiceNames) {
  const lowerKeywords = preset.keywords.map((keyword) => keyword.toLowerCase());
  const directMatch = voices.find((voice) => {
    const name = voice.name.toLowerCase();
    return !usedVoiceNames.has(name) && lowerKeywords.some((keyword) => name.includes(keyword));
  });

  if (directMatch) {
    return directMatch;
  }

  return voices.find((voice) => !usedVoiceNames.has(voice.name.toLowerCase())) || null;
}

function loadVoices() {
  if (!speechSupported) {
    return;
  }

  const allVoices = window.speechSynthesis.getVoices();
  cleanEnglishVoices = allVoices.filter((voice) => {
    return /^en([-_]|$)/i.test(voice.lang) && !BAD_VOICE_NAME_PATTERN.test(voice.name);
  });

  presetVoiceMap.clear();
  const usedVoiceNames = new Set();

  VOICE_PRESETS.forEach((preset) => {
    const matchedVoice = findPresetVoice(preset, cleanEnglishVoices, usedVoiceNames);
    presetVoiceMap.set(preset.id, matchedVoice);
    if (matchedVoice) {
      usedVoiceNames.add(matchedVoice.name.toLowerCase());
    }
  });

  voiceSelect.innerHTML = "";

  const savedPreset = localStorage.getItem(STORAGE_KEYS.voice) || "aria";
  VOICE_PRESETS.forEach((preset, index) => {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = preset.label;
    if (preset.id === savedPreset) {
      option.selected = true;
    }
    if (!savedPreset && index === 0) {
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

async function showQrCode() {
  const text = resultEl.textContent.trim();
  if (!text || text === "ここに生成結果が表示されます。") {
    setStatus("No text for QR", "error");
    return;
  }

  qrBtn.disabled = true;
  setStatus("Generating QR...", "loading");

  try {
    const response = await fetch(`/api/qrcode?text=${encodeURIComponent(text)}`);
    if (!response.ok) {
      throw new Error("QR generation failed");
    }

    const imageBlob = await response.blob();
    const imageUrl = URL.createObjectURL(imageBlob);

    if (qrImage.dataset.url) {
      URL.revokeObjectURL(qrImage.dataset.url);
    }

    qrImage.src = imageUrl;
    qrImage.dataset.url = imageUrl;
    qrDownload.href = imageUrl;
    qrSection.hidden = false;
    setStatus("QR ready", "ok");
  } catch (_error) {
    setStatus("QR failed", "error");
  } finally {
    qrBtn.disabled = false;
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

  const selectedPresetId = voiceSelect.value;
  const selectedVoice = presetVoiceMap.get(selectedPresetId) || cleanEnglishVoices[0] || null;
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
qrBtn.addEventListener("click", showQrCode);
