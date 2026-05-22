var form = document.querySelector("#copierForm");
var submitButton = document.querySelector("#submitButton");
var formStatus = document.querySelector("#formStatus");
var docxInput = document.querySelector("#docxInput");
var pdfInput = document.querySelector("#pdfInput");
var coverExisting = document.querySelector("#coverExisting");
var toolButtons = document.querySelectorAll("[data-tool]");
var workspaceTitle = document.querySelector("#workspaceTitle");
var copierPanel = document.querySelector("#copierPanel");
var booksPanel = document.querySelector("#booksPanel");
var booksForm = document.querySelector("#booksForm");
var booksButton = document.querySelector("#booksButton");
var booksStatus = document.querySelector("#booksStatus");
var themeInput = document.querySelector("#themeInput");
var bookResults = document.querySelector("#bookResults");

var panels = {
  copier: copierPanel,
  books: booksPanel,
};

var isAppleTouchDevice =
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

var titles = {
  copier: "Lesson Plan Copier",
  books: "Book Theme Finder",
};

function setStatus(message, kind) {
  if (kind === undefined) {
    kind = "";
  }
  formStatus.textContent = message;
  formStatus.className = ("form-status " + kind).trim();
}

function setBookStatus(message, kind) {
  if (kind === undefined) {
    kind = "";
  }
  booksStatus.textContent = message;
  booksStatus.className = ("form-status " + kind).trim();
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, function (char) {
    return {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char];
  });
}

function showTool(tool) {
  var i;
  var key;

  for (i = 0; i < toolButtons.length; i += 1) {
    toolButtons[i].classList.toggle("active", toolButtons[i].dataset.tool === tool);
  }

  for (key in panels) {
    if (Object.prototype.hasOwnProperty.call(panels, key)) {
      panels[key].classList.toggle("active", key === tool);
    }
  }

  workspaceTitle.textContent = titles[tool];
  if (tool !== "books") {
    bookResults.innerHTML = "";
  }
}

function addToolButtonHandlers() {
  var i;

  for (i = 0; i < toolButtons.length; i += 1) {
    toolButtons[i].addEventListener("click", handleToolButtonClick);
  }
}

function handleToolButtonClick(event) {
  showTool(event.currentTarget.dataset.tool);
}

function downloadBlob(blob, filename) {
  var url = URL.createObjectURL(blob);
  var link;

  if (isAppleTouchDevice) {
    window.location.href = url;
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 60000);
    return;
  }

  link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function outputName(pdfFile) {
  var name = pdfFile.name.replace(/\.pdf$/i, "");
  return name + "-copied.pdf";
}

async function handleCopierSubmit(event) {
  var docxFile;
  var pdfFile;
  var payload;
  var response;
  var message;
  var data;
  var blob;
  var parseError;
  var errorMessage;

  event.preventDefault();

  docxFile = docxInput.files[0];
  pdfFile = pdfInput.files[0];
  if (!docxFile || !pdfFile) {
    setStatus("Select both files first.", "error");
    return;
  }

  payload = new FormData();
  payload.append("docx", docxFile);
  payload.append("pdf", pdfFile);
  payload.append("coverExisting", coverExisting.checked ? "true" : "false");

  submitButton.disabled = true;
  setStatus("Processing the lesson plan...");

  try {
    response = await fetch("/api/index?route=lesson-plan-copier", {
      method: "POST",
      body: payload,
    });

    if (!response.ok) {
      message = "The lesson plan could not be processed.";
      try {
        data = await response.json();
        if (data.error) {
          message = data.error;
        }
      } catch (caughtError) {
        parseError = caughtError;
        message = await response.text();
      }
      throw new Error(message);
    }

    blob = await response.blob();
    downloadBlob(blob, outputName(pdfFile));
    setStatus(
      isAppleTouchDevice
        ? "Done. The finished PDF opened in this tab."
        : "Done. The finished PDF downloaded.",
      "success"
    );
  } catch (caughtError) {
    errorMessage = caughtError && caughtError.message ? caughtError.message : "Something went wrong.";
    setStatus(errorMessage, "error");
  } finally {
    submitButton.disabled = false;
  }
}

async function handleBooksSubmit(event) {
  var theme;
  var response;
  var data;
  var html;
  var i;
  var book;
  var errorMessage;

  event.preventDefault();

  theme = themeInput.value.trim();
  if (!theme) {
    setBookStatus("Enter a theme first.", "error");
    return;
  }

  booksButton.disabled = true;
  bookResults.innerHTML = "";
  setBookStatus("Asking Gemini for book ideas...");

  try {
    response = await fetch("/api/index?route=book-theme-finder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: theme }),
    });

    data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not generate books.");
    }

    html = "";
    for (i = 0; i < data.books.length; i += 1) {
      book = data.books[i];
      html +=
        '<article class="book-card">' +
        "<h3>" +
        (i + 1) +
        ". " +
        escapeHtml(book.title) +
        "</h3>" +
        '<p class="author">By ' +
        escapeHtml(book.author) +
        "</p>" +
        "<p>" +
        escapeHtml(book.description) +
        "</p>" +
        '<a class="youtube-link" href="' +
        escapeHtml(book.youtubeUrl) +
        '" target="_blank" rel="noopener noreferrer">' +
        "Find a YouTube read-aloud" +
        "</a>" +
        "</article>";
    }
    bookResults.innerHTML = html;
    setBookStatus('Done. ' + data.books.length + ' books generated for "' + theme + '".', "success");
  } catch (caughtError) {
    errorMessage = caughtError && caughtError.message ? caughtError.message : "Something went wrong.";
    setBookStatus(errorMessage, "error");
  } finally {
    booksButton.disabled = false;
  }
}

addToolButtonHandlers();
form.addEventListener("submit", handleCopierSubmit);
booksForm.addEventListener("submit", handleBooksSubmit);
