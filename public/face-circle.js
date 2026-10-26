(function () {
  "use strict";

  var root = document.querySelector("#faceCircleApp");
  var canvas = root.querySelector("#faceCanvas");
  var context = canvas.getContext("2d");
  var files = root.querySelector("#faceFiles");
  var status = root.querySelector("#faceStatus");
  var zoom = root.querySelector("#faceZoom");
  var strip = root.querySelector("#faceThumbnails");
  var photos = [];
  var index = 0;
  var currentImage = null;
  var busy = false;
  var selection = 0;
  var drag = null;

  function message(text, error) {
    status.textContent = text;
    status.className = "status-text" + (error ? " error" : "");
  }

  function loadImage(url) {
    return new Promise(function (resolve, reject) {
      var image = new Image();
      image.onload = function () { resolve(image); };
      image.onerror = function () { reject(new Error("This photo could not be opened. Try a JPG, PNG, or WebP image.")); };
      image.src = url;
    });
  }

  function toBlob(source, type, quality) {
    return new Promise(function (resolve, reject) {
      source.toBlob(function (blob) {
        if (blob) resolve(blob);
        else reject(new Error("Could not prepare this photo. Please try a smaller image."));
      }, type, quality);
    });
  }

  // Offsets are fractions of the circle diameter, independent of screen size.
  function dimensions(photo) {
    var scale = Math.max(1 / photo.width, 1 / photo.height) * photo.zoom;
    return { width: photo.width * scale, height: photo.height * scale };
  }

  function clamp(photo) {
    var size = dimensions(photo);
    photo.x = Math.max(-(size.width - 1) / 2, Math.min((size.width - 1) / 2, photo.x));
    photo.y = Math.max(-(size.height - 1) / 2, Math.min((size.height - 1) / 2, photo.y));
  }

  function paint(target, image, photo) {
    var ctx = target.getContext("2d");
    var diameter = target.width;
    var size = dimensions(photo);
    ctx.clearRect(0, 0, diameter, diameter);
    ctx.save();
    ctx.beginPath();
    ctx.arc(diameter / 2, diameter / 2, diameter / 2, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, diameter, diameter);
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(image, (0.5 - size.width / 2 + photo.x) * diameter,
      (0.5 - size.height / 2 + photo.y) * diameter, size.width * diameter, size.height * diameter);
    ctx.restore();
  }

  function draw() {
    if (!currentImage || !photos[index]) return;
    clamp(photos[index]);
    paint(canvas, currentImage, photos[index]);
    zoom.value = photos[index].zoom;
    root.querySelector("#faceZoomValue").value = Math.round(photos[index].zoom * 100) + "%";
  }

  function controls() {
    root.querySelector("#faceEditor").hidden = !photos.length;
    root.querySelector("#faceEmpty").hidden = !!photos.length;
    root.querySelector("#faceExport").disabled = busy || !photos.length || !currentImage;
    root.querySelector("#faceRemove").disabled = busy || !photos.length;
    root.querySelector("#faceClear").disabled = busy || !photos.length;
    root.querySelector("#faceChoose").disabled = busy;
    root.querySelector("#facePrevious").disabled = busy || index === 0;
    root.querySelector("#faceNext").disabled = busy || index >= photos.length - 1;
    zoom.disabled = busy || !currentImage;
    root.querySelectorAll("[data-face-move], #faceReset").forEach(function (button) {
      button.disabled = busy || !currentImage;
    });
    strip.querySelectorAll("button").forEach(function (button, i) {
      button.disabled = busy;
      button.setAttribute("aria-pressed", String(i === index));
    });
    root.querySelector("#faceCounter").textContent = photos.length ? (index + 1) + " / " + photos.length : "";
    root.querySelector("#faceName").textContent = photos.length ? photos[index].name : "";
  }

  async function selectPhoto(next) {
    var token = ++selection;
    index = next;
    currentImage = null;
    context.clearRect(0, 0, canvas.width, canvas.height);
    controls();
    if (!photos.length) return;
    try {
      var image = await loadImage(photos[index].url);
      if (token !== selection) return;
      currentImage = image;
      draw();
      controls();
      var thumbnail = strip.children[index];
      if (thumbnail) {
        strip.scrollLeft = thumbnail.offsetLeft - strip.offsetLeft - strip.clientWidth / 2 + thumbnail.clientWidth / 2;
      }
    } catch (error) {
      if (token === selection) message(error.message, true);
    }
  }

  function thumbnails() {
    strip.replaceChildren();
    photos.forEach(function (photo, i) {
      var button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-label", "Edit photo " + (i + 1) + ": " + photo.name);
      var image = document.createElement("img");
      image.src = photo.thumbnail;
      image.alt = "";
      button.appendChild(image);
      var number = document.createElement("span");
      number.textContent = i + 1;
      button.appendChild(number);
      button.addEventListener("click", function () { selectPhoto(i); });
      strip.appendChild(button);
    });
  }

  root.querySelector("#faceChoose").addEventListener("click", function () { files.click(); });
  files.addEventListener("change", async function () {
    if (busy) return;
    var incoming = Array.from(files.files);
    files.value = "";
    if (!incoming.length) return;
    busy = true;
    controls();
    var start = photos.length;
    var failed = [];
    for (var i = 0; i < incoming.length; i += 1) {
      var file = incoming[i];
      var url = URL.createObjectURL(file);
      message("Preparing photo " + (i + 1) + " of " + incoming.length + "…");
      try {
        var image = await loadImage(url);
        // Keep only compressed files and small thumbnails in memory between edits.
        var prepared = document.createElement("canvas");
        var scale = Math.min(1, 2400 / Math.max(image.naturalWidth, image.naturalHeight));
        prepared.width = Math.max(1, Math.round(image.naturalWidth * scale));
        prepared.height = Math.max(1, Math.round(image.naturalHeight * scale));
        var ctx = prepared.getContext("2d");
        ctx.fillStyle = "white";
        ctx.fillRect(0, 0, prepared.width, prepared.height);
        ctx.drawImage(image, 0, 0, prepared.width, prepared.height);
        var blob = await toBlob(prepared, "image/jpeg", 0.95);
        var photo = { name: file.name, width: prepared.width, height: prepared.height,
          url: URL.createObjectURL(blob), zoom: 1, x: 0, y: 0 };
        var thumb = document.createElement("canvas");
        thumb.width = thumb.height = 96;
        paint(thumb, prepared, photo);
        photo.thumbnail = thumb.toDataURL("image/png");
        photos.push(photo);
        prepared.width = prepared.height = 0;
      } catch (error) {
        failed.push(file.name);
      } finally {
        URL.revokeObjectURL(url);
      }
    }
    thumbnails();
    busy = false;
    await selectPhoto(start < photos.length ? start : Math.max(0, photos.length - 1));
    message(failed.length ? "Could not open: " + failed.join(", ") + ". Try JPG, PNG, or WebP. Other photos are ready."
      : photos.length + " photo(s) ready. Each crop is kept as you browse.", !!failed.length);
  });

  canvas.addEventListener("pointerdown", function (event) {
    if (busy || !currentImage || drag || (event.pointerType === "mouse" && event.button !== 0)) return;
    canvas.focus({ preventScroll: true });
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", function (event) {
    if (!drag || drag.id !== event.pointerId || busy || !currentImage) return;
    var diameter = canvas.getBoundingClientRect().width;
    photos[index].x += (event.clientX - drag.x) / diameter;
    photos[index].y += (event.clientY - drag.y) / diameter;
    drag.x = event.clientX;
    drag.y = event.clientY;
    draw();
  });
  ["pointerup", "pointercancel", "lostpointercapture"].forEach(function (name) {
    canvas.addEventListener(name, function () { drag = null; });
  });

  function move(direction, step) {
    if (busy || !currentImage) return;
    if (direction === "left") photos[index].x -= step;
    if (direction === "right") photos[index].x += step;
    if (direction === "up") photos[index].y -= step;
    if (direction === "down") photos[index].y += step;
    draw();
  }
  canvas.addEventListener("keydown", function (event) {
    var direction = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down" }[event.key];
    if (direction) {
      event.preventDefault();
      move(direction, event.shiftKey ? 0.05 : 0.01);
    }
  });
  root.querySelectorAll("[data-face-move]").forEach(function (button) {
    button.addEventListener("click", function () { move(button.dataset.faceMove, 0.025); });
  });
  zoom.addEventListener("input", function () {
    if (busy || !currentImage) return;
    photos[index].zoom = Number(zoom.value);
    draw();
  });
  root.querySelector("#faceReset").addEventListener("click", function () {
    if (busy || !currentImage) return;
    photos[index].zoom = 1;
    photos[index].x = photos[index].y = 0;
    draw();
  });
  root.querySelector("#facePrevious").addEventListener("click", function () { selectPhoto(index - 1); });
  root.querySelector("#faceNext").addEventListener("click", function () { selectPhoto(index + 1); });
  root.querySelector("#faceRemove").addEventListener("click", function () {
    URL.revokeObjectURL(photos[index].url);
    photos.splice(index, 1);
    thumbnails();
    selectPhoto(Math.max(0, Math.min(index, photos.length - 1)));
    message(photos.length ? "Photo removed. Remaining crops are kept." : "Select one or more photos to get started.");
  });
  root.querySelector("#faceClear").addEventListener("click", function () {
    photos.forEach(function (photo) { URL.revokeObjectURL(photo.url); });
    photos = [];
    thumbnails();
    selectPhoto(0);
    message("Select one or more photos to get started.");
  });

  root.querySelector("#faceExport").addEventListener("click", async function () {
    if (busy || !photos.length || !currentImage) return;
    busy = true;
    controls();
    try {
      if (!window.PDFLib) throw new Error("The PDF tool could not load. Refresh the app and try again.");
      var pdf = await PDFLib.PDFDocument.create();
      var output = document.createElement("canvas");
      output.width = output.height = 900; // 3 inches at 300 pixels per inch.
      for (var i = 0; i < photos.length; i += 1) {
        message("Creating page " + (i + 1) + " of " + photos.length + "…");
        var image = await loadImage(photos[i].url);
        paint(output, image, photos[i]);
        var png = await toBlob(output, "image/png");
        var embedded = await pdf.embedPng(await png.arrayBuffer());
        // PDF uses 72 points per inch: Letter = 612 x 792; diameter = 216.
        var page = pdf.addPage([612, 792]);
        page.drawImage(embedded, { x: 198, y: 288, width: 216, height: 216 });
      }
      downloadBlob(new Blob([await pdf.save()], { type: "application/pdf" }), "face-circle.pdf");
      message("PDF exported: " + photos.length + " page(s). Print at Actual size / 100% for 3-inch circles.");
    } catch (error) {
      message(error.message || "Could not export the PDF. Try again with fewer photos.", true);
    } finally {
      busy = false;
      controls();
    }
  });
  controls();
}());
