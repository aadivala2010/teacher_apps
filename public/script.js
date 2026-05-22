const form = document.querySelector("#copierForm");
const submitButton = document.querySelector("#submitButton");
const formStatus = document.querySelector("#formStatus");
const docxInput = document.querySelector("#docxInput");
const pdfInput = document.querySelector("#pdfInput");
const coverExisting = document.querySelector("#coverExisting");
const toolButtons = document.querySelectorAll("[data-tool]");
const workspaceTitle = document.querySelector("#workspaceTitle");
const copierPanel = document.querySelector("#copierPanel");
const booksPanel = document.querySelector("#booksPanel");
const booksForm = document.querySelector("#booksForm");
const booksButton = document.querySelector("#booksButton");
const booksStatus = document.querySelector("#booksStatus");
const themeInput = document.querySelector("#themeInput");
const bookResults = document.querySelector("#bookResults");

const panels = {
  copier: copierPanel,
  books: booksPanel,
};

const isAppleTouchDevice =
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

const titles = {
  copier: "Lesson Plan Copier",
  books: "Book Theme Finder",
};

function setStatus(message, kind = "") {
  formStatus.textContent = message;
  formStatus.className = `form-status ${kind}`.trim();
}

function setBookStatus(message, kind = "") {
  booksStatus.textContent = message;
  booksStatus.className = `form-status ${kind}`.trim();
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function showTool(tool) {
  toolButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tool === tool);
  });
  Object.entries(panels).forEach(([key, panel]) => {
    panel.classList.toggle("active", key === tool);
  });
  workspaceTitle.textContent = titles[tool];
  if (tool !== "books") {
    bookResults.innerHTML = "";
  }
}

toolButtons.forEach((button) => {
  button.addEventListener("click", () => showTool(button.dataset.tool));
});

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);

  if (isAppleTouchDevice) {
    window.open(url, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return;
  }

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function outputName(pdfFile) {
  const name = pdfFile.name.replace(/\.pdf$/i, "");
  return `${name}-copied.pdf`;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const docxFile = docxInput.files[0];
  const pdfFile = pdfInput.files[0];
  if (!docxFile || !pdfFile) {
    setStatus("Select both files first.", "error");
    return;
  }

  const payload = new FormData();
  payload.append("docx", docxFile);
  payload.append("pdf", pdfFile);
  payload.append("coverExisting", coverExisting.checked ? "true" : "false");

  submitButton.disabled = true;
  setStatus("Processing the lesson plan...");

  try {
    const response = await fetch("/api/index?route=lesson-plan-copier", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      let message = "The lesson plan could not be processed.";
      try {
        const data = await response.json();
        if (data.error) {
          message = data.error;
        }
      } catch {
        message = await response.text();
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    downloadBlob(blob, outputName(pdfFile));
    setStatus(isAppleTouchDevice ? "Done. The finished PDF opened in a new tab." : "Done. The finished PDF downloaded.", "success");
  } catch (error) {
    setStatus(error.message || "Something went wrong.", "error");
  } finally {
    submitButton.disabled = false;
  }
});

booksForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const theme = themeInput.value.trim();
  if (!theme) {
    setBookStatus("Enter a theme first.", "error");
    return;
  }

  booksButton.disabled = true;
  bookResults.innerHTML = "";
  setBookStatus("Asking Gemini for book ideas...");

  try {
    const response = await fetch("/api/index?route=book-theme-finder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not generate books.");
    }

    bookResults.innerHTML = data.books.map((book, index) => `
      <article class="book-card">
        <h3>${index + 1}. ${escapeHtml(book.title)}</h3>
        <p class="author">By ${escapeHtml(book.author)}</p>
        <p>${escapeHtml(book.description)}</p>
        <a class="youtube-link" href="${escapeHtml(book.youtubeUrl)}" target="_blank" rel="noopener noreferrer">
          Find a YouTube read-aloud
        </a>
      </article>
    `).join("");
    setBookStatus(`Done. ${data.books.length} books generated for "${theme}".`, "success");
  } catch (error) {
    setBookStatus(error.message || "Something went wrong.", "error");
  } finally {
    booksButton.disabled = false;
  }
});
