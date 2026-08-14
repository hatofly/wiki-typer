const app = document.querySelector("#app");

const state = {
  words: [],
  current: null,
  input: "",
  startedAt: null,
  averageSpeed: null,
  previousSpeed: null,
  totalChars: 0,
  totalTime: 0,
  dataName: null,
  inputType: null,
  wordId: 0,
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatSpeed(value) {
  return value == null || !Number.isFinite(value) ? "--" : value.toFixed(1);
}

function getInputWord(word) {
  if (Array.isArray(word.english) && word.english.length > 0 && word.english[0]) {
    return {
      text: String(word.english[0]),
      type: "english",
    };
  }

  return {
    text: String(word.reading ?? ""),
    type: "reading",
  };
}

function renderTarget(target, input) {
  let html = "";

  for (let i = 0; i < target.length; i++) {
    let cls = "char";

    if (i < input.length) {
      cls += input[i] === target[i] ? " correct" : " incorrect";
    }

    html += `<span class="${cls}">${escapeHtml(target[i])}</span>`;
  }

  return html;
}

async function loadJson(url) {
  const response = await fetch(url, { cache: "no-cache" });

  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.status}`);
  }

  return response.json();
}

function titleFromFileName(fileName) {
  return fileName
    .replace(/\.json$/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

async function showHome() {
  let files;

  try {
    files = await loadJson("JSON/index.json");
  } catch (error) {
    app.innerHTML = `
      <section class="home">
        <h1>Wiki Typer</h1>
        <p>JSON/index.json を読み込めませんでした。</p>
        <p>${escapeHtml(error.message)}</p>
      </section>
    `;
    return;
  }

  app.innerHTML = `
    <section class="home">
      <h1>Wiki Typer</h1>
      <div class="data-list">
        ${files.map(file => {
          const name = typeof file === "string" ? file : file.file;
          const title = typeof file === "string"
            ? titleFromFileName(file)
            : (file.title ?? titleFromFileName(name));

          return `
            <a class="data-link"
               href="?data=${encodeURIComponent(name.replace(/\.json$/i, ""))}">
              ${escapeHtml(title)}
            </a>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function renderGame() {
  const word = state.current;
  const target = getInputWord(word);

  state.inputType = target.type;

  app.innerHTML = `
    <section class="game">
      <div class="top-row">
        <a class="panel home-button" href="./" aria-label="Home">
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <path d="M8 30 L32 8 L56 30" />
            <path d="M14 28 V56 H50 V28" />
            <path d="M25 56 V38 H39 V56" />
          </svg>
        </a>

        <div class="panel stat average">
          <div class="stat-value">${formatSpeed(state.averageSpeed)}</div>
          <div class="stat-label">[average]<br>char / sec</div>
        </div>

        <div class="panel stat previous">
          <div class="stat-value">${formatSpeed(state.previousSpeed)}</div>
          <div class="stat-label">[previous]<br>char / sec</div>
        </div>
      </div>

      <div class="word-row ${target.type === "english" ? "active" : ""}">
        ${
          target.type === "english"
            ? createTypingDisplay(target.text)
            : escapeHtml(word.english?.[0] ?? "")
        }
      </div>

      <div class="word-row reading-row ${target.type === "reading" ? "active" : ""}">
        ${
          target.type === "reading"
            ? createTypingDisplay(target.text)
            : escapeHtml(word.reading ?? "")
        }
      </div>

      <div class="term">${escapeHtml(word.term ?? "")}</div>

      <div class="description">
        ${escapeHtml(word.description ?? "")}
      </div>
    </section>
  `;

  const input = document.querySelector("#typing-input");

  // Do not restore the previous word's value through HTML/browser state.
  // The new word always starts with a genuinely empty input element.
  input.value = "";
  state.input = "";

  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKeyDown);

  // Focus after the DOM has been replaced.
  requestAnimationFrame(() => {
    input.focus();
    input.value = "";
  });
}

function createTypingDisplay(target) {
  return `
    <span class="typing-display" id="typing-display">
      ${renderTarget(target, "")}
      <input
        id="typing-input"
        class="typing-input"
        type="text"
        inputmode="text"
        autocomplete="off"
        autocorrect="off"
        autocapitalize="off"
        spellcheck="false"
      >
    </span>
  `;
}

function onInput(event) {
  if (state.startedAt === null) {
    state.startedAt = performance.now();
  }

  state.input = event.target.value;
  updateTypingDisplay();
}

function updateTypingDisplay() {
  const display = document.querySelector("#typing-display");
  if (!display) return;

  const target = getInputWord(state.current).text;

  display.querySelectorAll(".char").forEach((span, i) => {
    span.className = "char";

    if (i < state.input.length) {
      span.classList.add(
        state.input[i] === target[i] ? "correct" : "incorrect"
      );
    }
  });
}

function onKeyDown(event) {
  if (event.key !== "Enter") return;

  event.preventDefault();

  const target = getInputWord(state.current).text;

  if (state.input !== target) return;

  finishWord();
}

function finishWord() {
  if (state.startedAt === null) return;

  const elapsedSeconds = (performance.now() - state.startedAt) / 1000;
  const characterCount = getInputWord(state.current).text.length;

  if (elapsedSeconds > 0) {
    state.previousSpeed = characterCount / elapsedSeconds;
    state.totalChars += characterCount;
    state.totalTime += elapsedSeconds;
    state.averageSpeed = state.totalChars / state.totalTime;
  }

  nextWord();
}

function nextWord() {
  if (state.words.length === 0) {
    throw new Error("JSON contains no words.");
  }

  const index = Math.floor(Math.random() * state.words.length);
  state.current = state.words[index];

  // Reset all per-word state before replacing the DOM.
  state.wordId += 1;
  state.input = "";
  state.startedAt = null;

  renderGame();
}

async function startGame(dataName) {
  state.dataName = dataName;

  try {
    const data = await loadJson(`json/${encodeURIComponent(dataName)}.json`);

    state.words = Array.isArray(data) ? data : data.words;

    if (!Array.isArray(state.words) || state.words.length === 0) {
      throw new Error("JSON contains no words.");
    }

    nextWord();
  } catch (error) {
    app.innerHTML = `
      <section class="home">
        <h1>Wiki Typer</h1>
        <p>データを読み込めませんでした。</p>
        <p>${escapeHtml(error.message)}</p>
        <p><a href="./">Home</a></p>
      </section>
    `;
  }
}

function boot() {
  const params = new URLSearchParams(location.search);
  const dataName = params.get("data");

  if (!dataName) {
    showHome();
  } else {
    startGame(dataName);
  }
}

boot();
