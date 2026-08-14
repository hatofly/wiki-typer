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
  if (Array.isArray(word.spell) && word.spell.length > 0 && word.spell[0]) {
    return {
      text: String(word.spell[0]),
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
    // A small manifest is necessary because browsers cannot enumerate
    // arbitrary files in a static directory.
    files = await loadJson("./json/index.json");
  } catch (error) {
    app.innerHTML = `
      <section class="home">
        <h1>Wiki Typer</h1>
        <p>json/index.json を読み込めませんでした。</p>
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
        <a class="panel home-button" href="./">⌂</a>

        <div class="panel stat average">
          <div class="stat-value">${formatSpeed(state.averageSpeed)}</div>
          <div class="stat-label">[average]<br>char / sec</div>
        </div>

        <div class="panel stat previous">
          <div class="stat-value">${formatSpeed(state.previousSpeed)}</div>
          <div class="stat-label">[previous]<br>char / sec</div>
        </div>
      </div>

      <div class="word-row ${target.type === "english" ? "active" : ""}"
           id="english-row">
        ${
          target.type === "english"
            ? `
              <span class="typing-display" id="typing-display">
                ${renderTarget(target.text, state.input)}
                <input
                  id="typing-input"
                  class="typing-input"
                  type="text"
                  inputmode="text"
                  autocomplete="off"
                  autocorrect="off"
                  autocapitalize="off"
                  spellcheck="false"
                  value="${escapeHtml(state.input)}"
                >
              </span>
            `
            : escapeHtml(word.spell?.[0] ?? "")
        }
      </div>

      <div class="word-row reading-row ${target.type === "reading" ? "active" : ""}"
           id="reading-row">
        ${
          target.type === "reading"
            ? `
              <span class="typing-display" id="typing-display">
                ${renderTarget(target.text, state.input)}
                <input
                  id="typing-input"
                  class="typing-input"
                  type="text"
                  inputmode="text"
                  autocomplete="off"
                  autocorrect="off"
                  autocapitalize="none"
                  spellcheck="false"
                  value="${escapeHtml(state.input)}"
                >
              </span>
            `
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
  input.focus();

  input.addEventListener("input", onInput);
  input.addEventListener("keydown", onKeyDown);
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

  // Enter only advances after an exact match.
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
  state.input = "";
  state.startedAt = null;

  renderGame();
}

async function startGame(dataName) {
  state.dataName = dataName;

  try {
    const data = await loadJson(`./json/${encodeURIComponent(dataName)}.json`);

    // Support either a raw array or { words: [...] }.
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
