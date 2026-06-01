var monthSelect = document.querySelector("#monthSelect");
var weekSelect = document.querySelector("#weekSelect");
var classInput = document.querySelector("#classInput");
var programInput = document.querySelector("#programInput");
var booksInput = document.querySelector("#booksInput");
var currentYearLabel = document.querySelector("#currentYearLabel");
var selectedWeekRange = document.querySelector("#selectedWeekRange");
var plannerStatus = document.querySelector("#plannerStatus");
var weekDays = document.querySelector("#weekDays");
var circleTimeGrid = document.querySelector("#circleTimeGrid");
var smallGroupOneGrid = document.querySelector("#smallGroupOneGrid");
var smallGroupTwoGrid = document.querySelector("#smallGroupTwoGrid");
var outdoorGrid = document.querySelector("#outdoorGrid");
var centersGrid = document.querySelector("#centersGrid");
var savePlanButton = document.querySelector("#savePlanButton");
var loadPlanButton = document.querySelector("#loadPlanButton");
var applyCurrentTemplateButton = document.querySelector("#applyCurrentTemplateButton");
var apiRoutes = {
  plannerExportPdf: "/api/planner-export-pdf",
};
var plannerDatabaseName = "teacherPlannerDb";
var plannerDatabaseVersion = 1;
var plannerStoreName = "plans";
var currentAttachments = {};

var assessmentOptions = [
  "Checklist",
  "Observation with Notes",
  "Portfolio",
];

var monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

var dayKeys = ["monday", "tuesday", "wednesday", "thursday", "friday"];
var dayLabels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

var centerConfig = [
  { key: "dramatic_play", label: "Dramatic Play" },
  { key: "construction", label: "Construction" },
  { key: "music", label: "Music" },
  { key: "art", label: "Art" },
  { key: "writing", label: "Writing" },
  { key: "manipulative_center", label: "Manipulative Center" },
  { key: "science", label: "Science" },
  { key: "sensory", label: "Sensory" },
  { key: "language_literacy", label: "Language Literacy" },
];

var currentYear = new Date().getFullYear();
var weekCache = {};

function setPlannerStatus(message, kind) {
  plannerStatus.textContent = message;
  plannerStatus.className = "status-text" + (kind ? " " + kind : "");
}

function plannerStorageKey(year, month, weekNumber) {
  return String(year) + "-" + String(month) + "-" + String(weekNumber);
}

function option(label, value) {
  var el = document.createElement("option");
  el.value = String(value);
  el.textContent = label;
  return el;
}

function titleCaseWeekRange(weekData) {
  return weekData.startLabel + " - " + weekData.endLabel;
}

function addDays(date, count) {
  var result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  result.setDate(result.getDate() + count);
  return result;
}

function nextMonday(date) {
  var result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  var day = result.getDay();
  var delta = day === 0 ? 1 : 8 - day;
  if (day === 1) {
    delta = 7;
  }
  result.setDate(result.getDate() + delta);
  return result;
}

function startOfMonday(date) {
  var result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  var day = result.getDay();
  var delta = day === 0 ? -6 : 1 - day;
  result.setDate(result.getDate() + delta);
  return result;
}

function firstWorkdayOfMonth(date) {
  var day = date.getDay();
  if (day === 0 || day === 6) {
    return nextMonday(date);
  }
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function formatDateLabel(date) {
  return monthNames[date.getMonth()].slice(0, 3) + " " + date.getDate();
}

function formatDateIso(date) {
  var month = String(date.getMonth() + 1).padStart(2, "0");
  var day = String(date.getDate()).padStart(2, "0");
  return date.getFullYear() + "-" + month + "-" + day;
}

function computeMonthWeeks(year, monthIndex) {
  var cacheKey = year + "-" + monthIndex;
  var firstOfMonth;
  var calendarStart;
  var start;
  var monthEnd;
  var weeks;
  var i;
  var end;
  var dates;
  var date;
  var j;

  if (weekCache[cacheKey]) {
    return weekCache[cacheKey];
  }

  firstOfMonth = new Date(year, monthIndex, 1);
  start = firstWorkdayOfMonth(firstOfMonth);
  monthEnd = new Date(year, monthIndex + 1, 0);
  weeks = [];

  for (i = 0; i < 5; i += 1) {
    calendarStart = startOfMonday(start);
    end = addDays(calendarStart, 4);
    if (end > monthEnd) {
      end = monthEnd;
    }
    dates = [];
    for (j = 0; j < 5; j += 1) {
      date = addDays(calendarStart, j);
      if (date < firstOfMonth || date > monthEnd) {
        dates.push(null);
      } else {
        dates.push(date);
      }
    }
    weeks.push({
      number: i + 1,
      start: start,
      end: end,
      startIso: formatDateIso(start),
      endIso: formatDateIso(end),
      startLabel: formatDateLabel(start),
      endLabel: formatDateLabel(end),
      dates: dates,
    });
    start = nextMonday(start);
  }

  weekCache[cacheKey] = weeks;
  return weeks;
}

function renderMonthOptions() {
  var i;
  monthSelect.innerHTML = "";
  for (i = 0; i < monthNames.length; i += 1) {
    monthSelect.appendChild(option(monthNames[i], i + 1));
  }
  monthSelect.value = String(new Date().getMonth() + 1);
}

function renderWeekOptions() {
  var weeks = computeMonthWeeks(currentYear, Number(monthSelect.value) - 1);
  var i;
  weekSelect.innerHTML = "";
  for (i = 0; i < weeks.length; i += 1) {
    weekSelect.appendChild(option("Week " + weeks[i].number, weeks[i].number));
  }
  if (!weekSelect.value) {
    weekSelect.value = "1";
  }
}

function selectedWeekData() {
  var month = Number(monthSelect.value) - 1;
  var weekNumber = Number(weekSelect.value);
  return computeMonthWeeks(currentYear, month)[weekNumber - 1];
}

function renderWeekDays() {
  var weekData = selectedWeekData();
  var html = "";
  var i;
  var dateLabel;

  selectedWeekRange.textContent = titleCaseWeekRange(weekData);

  for (i = 0; i < dayLabels.length; i += 1) {
    dateLabel = weekData.dates[i] ? formatDateLabel(weekData.dates[i]) : "Outside this month";
    html +=
      '<div class="day-chip">' +
      "<strong>" +
      dayLabels[i] +
      "</strong>" +
      "<span>" +
      dateLabel +
      "</span>" +
      "</div>";
  }
  weekDays.innerHTML = html;
}

function assessmentSelectHtml(fieldKey) {
  var html = '<select data-field="' + fieldKey + '" data-kind="assessment">';
  var i;
  html += '<option value="">Select assessment</option>';
  for (i = 0; i < assessmentOptions.length; i += 1) {
    html += '<option value="' + assessmentOptions[i] + '">' + assessmentOptions[i] + "</option>";
  }
  html += "</select>";
  return html;
}

function attachmentHtml(fieldKey) {
  return (
    '<div class="attachment-row">' +
    '<label for="attachment-' + fieldKey + '">Attachment</label>' +
    '<input id="attachment-' + fieldKey + '" type="file" data-field="' + fieldKey + '" data-kind="attachment" />' +
    '<div id="attachment-link-' + fieldKey + '" class="attachment-empty">No attachment uploaded</div>' +
    "</div>"
  );
}

function activityCardHtml(label, fieldKey, rows) {
  return (
    '<article class="activity-card">' +
    "<h3>" +
    label +
    "</h3>" +
    '<textarea rows="' + rows + '" data-field="' + fieldKey + '" data-kind="text"></textarea>' +
    assessmentSelectHtml(fieldKey) +
    attachmentHtml(fieldKey) +
    "</article>"
  );
}

function renderSectionGrids() {
  var html = "";
  var i;

  html = "";
  for (i = 0; i < dayLabels.length; i += 1) {
    html += activityCardHtml(dayLabels[i], "circle_time." + dayKeys[i], 6);
  }
  circleTimeGrid.innerHTML = html;

  html = "";
  for (i = 0; i < dayLabels.length; i += 1) {
    html += activityCardHtml(dayLabels[i], "small_group_1." + dayKeys[i], 6);
  }
  smallGroupOneGrid.innerHTML = html;

  html = "";
  for (i = 0; i < dayLabels.length; i += 1) {
    html += activityCardHtml(dayLabels[i], "small_group_2." + dayKeys[i], 6);
  }
  smallGroupTwoGrid.innerHTML = html;

  outdoorGrid.innerHTML = activityCardHtml("Outdoor Learning Experience", "outdoor_learning", 5);

  html = "";
  for (i = 0; i < centerConfig.length; i += 1) {
    html += activityCardHtml(centerConfig[i].label, "centers." + centerConfig[i].key, 5);
  }
  centersGrid.innerHTML = html;
}

function setAttachmentLink(fieldKey, attachment) {
  var target = document.querySelector("#attachment-link-" + fieldKey);
  if (!target) {
    return;
  }
  if (!attachment) {
    delete currentAttachments[fieldKey];
    target.className = "attachment-empty";
    target.textContent = "No attachment uploaded";
    return;
  }
  currentAttachments[fieldKey] = attachment;
  target.className = "";
  target.innerHTML =
    '<a class="attachment-link" href="' +
    (attachment.downloadUrl || attachment.dataUrl || "#") +
    '" target="_blank" rel="noopener noreferrer">' +
    attachment.filename +
    "</a>";
}

function setFieldValue(fieldKey, kind, value) {
  var element = document.querySelector('[data-field="' + fieldKey + '"][data-kind="' + kind + '"]');
  if (element) {
    element.value = value || "";
  }
}

function resetPlannerForm() {
  classInput.value = "";
  programInput.value = "";
  booksInput.value = "";
  currentAttachments = {};

  var textFields = document.querySelectorAll('[data-kind="text"]');
  var assessmentFields = document.querySelectorAll('[data-kind="assessment"]');
  var attachmentFields = document.querySelectorAll('[data-kind="attachment"]');
  var i;

  for (i = 0; i < textFields.length; i += 1) {
    textFields[i].value = "";
    setAttachmentLink(textFields[i].dataset.field, null);
  }
  for (i = 0; i < assessmentFields.length; i += 1) {
    assessmentFields[i].value = "";
  }
  for (i = 0; i < attachmentFields.length; i += 1) {
    attachmentFields[i].value = "";
  }
}

function applyPlannerRecord(record) {
  var attachments = record.attachments || {};
  var section;
  var key;
  var sectionName;

  classInput.value = record.className || "";
  programInput.value = record.programName || "";
  booksInput.value = record.books || "";

  for (sectionName in record.activities) {
    if (!Object.prototype.hasOwnProperty.call(record.activities, sectionName)) {
      continue;
    }
    section = record.activities[sectionName];
    for (key in section) {
      if (!Object.prototype.hasOwnProperty.call(section, key)) {
        continue;
      }
      if (sectionName === "centers") {
        setFieldValue("centers." + key, "text", section[key].text);
        setFieldValue("centers." + key, "assessment", section[key].assessment);
        setAttachmentLink("centers." + key, attachments["centers." + key]);
      } else {
        setFieldValue(sectionName + "." + key, "text", section[key].text);
        setFieldValue(sectionName + "." + key, "assessment", section[key].assessment);
        setAttachmentLink(sectionName + "." + key, attachments[sectionName + "." + key]);
      }
    }
  }

  setFieldValue("outdoor_learning", "text", record.outdoorLearning || "");
  setFieldValue("outdoor_learning", "assessment", record.outdoorAssessment || "");
  setAttachmentLink("outdoor_learning", attachments.outdoor_learning);
}

function plannerPayload() {
  var activities = {
    circle_time: {},
    small_group_1: {},
    small_group_2: {},
    centers: {},
  };
  var i;
  var fieldKey;

  for (i = 0; i < dayKeys.length; i += 1) {
    activities.circle_time[dayKeys[i]] = {
      text: document.querySelector('[data-field="circle_time.' + dayKeys[i] + '"][data-kind="text"]').value.trim(),
      assessment: document.querySelector('[data-field="circle_time.' + dayKeys[i] + '"][data-kind="assessment"]').value,
    };
    activities.small_group_1[dayKeys[i]] = {
      text: document.querySelector('[data-field="small_group_1.' + dayKeys[i] + '"][data-kind="text"]').value.trim(),
      assessment: document.querySelector('[data-field="small_group_1.' + dayKeys[i] + '"][data-kind="assessment"]').value,
    };
    activities.small_group_2[dayKeys[i]] = {
      text: document.querySelector('[data-field="small_group_2.' + dayKeys[i] + '"][data-kind="text"]').value.trim(),
      assessment: document.querySelector('[data-field="small_group_2.' + dayKeys[i] + '"][data-kind="assessment"]').value,
    };
  }

  for (i = 0; i < centerConfig.length; i += 1) {
    fieldKey = centerConfig[i].key;
    activities.centers[fieldKey] = {
      text: document.querySelector('[data-field="centers.' + fieldKey + '"][data-kind="text"]').value.trim(),
      assessment: document.querySelector('[data-field="centers.' + fieldKey + '"][data-kind="assessment"]').value,
    };
  }

  return {
    year: currentYear,
    month: Number(monthSelect.value),
    monthLabel: monthNames[Number(monthSelect.value) - 1],
    weekNumber: Number(weekSelect.value),
    weekStart: selectedWeekData().startIso,
    weekEnd: selectedWeekData().endIso,
    className: classInput.value.trim(),
    programName: programInput.value.trim(),
    books: booksInput.value.trim(),
    outdoorLearning: document.querySelector('[data-field="outdoor_learning"][data-kind="text"]').value.trim(),
    outdoorAssessment: document.querySelector('[data-field="outdoor_learning"][data-kind="assessment"]').value,
    activities: activities,
    clearAttachmentFields: [],
    templateName: monthNames[Number(monthSelect.value) - 1] + " Week " + weekSelect.value,
  };
}

function openPlannerDatabase() {
  return new Promise(function (resolve, reject) {
    var request = window.indexedDB.open(plannerDatabaseName, plannerDatabaseVersion);

    request.onupgradeneeded = function (event) {
      var db = event.target.result;
      if (!db.objectStoreNames.contains(plannerStoreName)) {
        db.createObjectStore(plannerStoreName, { keyPath: "storageKey" });
      }
    };

    request.onsuccess = function () {
      resolve(request.result);
    };

    request.onerror = function () {
      reject(new Error("Could not open the planner database on this device."));
    };
  });
}

function readFileAsDataUrl(file) {
  return new Promise(function (resolve, reject) {
    var reader = new FileReader();
    reader.onload = function () {
      resolve(String(reader.result || ""));
    };
    reader.onerror = function () {
      reject(new Error("Could not read one of the attachments."));
    };
    reader.readAsDataURL(file);
  });
}

async function collectAttachmentsForStorage() {
  var attachmentInputs = document.querySelectorAll('[data-kind="attachment"]');
  var attachments = {};
  var i;
  var input;
  var file;
  var dataUrl;

  for (var existingKey in currentAttachments) {
    if (Object.prototype.hasOwnProperty.call(currentAttachments, existingKey)) {
      attachments[existingKey] = currentAttachments[existingKey];
    }
  }

  for (i = 0; i < attachmentInputs.length; i += 1) {
    input = attachmentInputs[i];
    if (input.files && input.files[0]) {
      file = input.files[0];
      dataUrl = await readFileAsDataUrl(file);
      attachments[input.dataset.field] = {
        filename: file.name,
        mimeType: file.type || "application/octet-stream",
        dataUrl: dataUrl,
      };
    }
  }

  return attachments;
}

function savePlanToIndexedDb(record) {
  return openPlannerDatabase().then(function (db) {
    return new Promise(function (resolve, reject) {
      var transaction = db.transaction(plannerStoreName, "readwrite");
      var store = transaction.objectStore(plannerStoreName);
      var request;

      record.storageKey = plannerStorageKey(record.year, record.month, record.weekNumber);
      request = store.put(record);

      request.onsuccess = function () {
        resolve(record);
      };

      request.onerror = function () {
        reject(new Error("Could not save this week on this device."));
      };

      transaction.oncomplete = function () {
        db.close();
      };
    });
  });
}

function loadPlanFromIndexedDb(year, month, weekNumber) {
  return openPlannerDatabase().then(function (db) {
    return new Promise(function (resolve, reject) {
      var transaction = db.transaction(plannerStoreName, "readonly");
      var store = transaction.objectStore(plannerStoreName);
      var request = store.get(plannerStorageKey(year, month, weekNumber));

      request.onsuccess = function () {
        resolve(request.result || null);
      };

      request.onerror = function () {
        reject(new Error("Could not load the saved week from this device."));
      };

      transaction.oncomplete = function () {
        db.close();
      };
    });
  });
}

function suggestedFilenameFromHeaders(response) {
  var contentDisposition = response.headers.get("Content-Disposition") || "";
  var match = /filename="([^"]+)"/i.exec(contentDisposition);
  if (match && match[1]) {
    return match[1];
  }
  return "lesson-plan.pdf";
}

function downloadBlob(blob, filename) {
  var url = URL.createObjectURL(blob);
  var isAppleMobile = /iPad|iPhone|iPod/.test(navigator.userAgent || "");
  var link;
  if (isAppleMobile) {
    window.location.href = url;
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 2000);
    return;
  }
  link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  setTimeout(function () {
    URL.revokeObjectURL(url);
    document.body.removeChild(link);
  }, 1000);
}

async function handleSavePlan() {
  var payload;
  var attachments;
  var record;
  savePlanButton.disabled = true;
  setPlannerStatus("Saving this week on this device...");
  try {
    payload = plannerPayload();
    attachments = await collectAttachmentsForStorage();
    record = JSON.parse(JSON.stringify(payload));
    record.attachments = attachments;
    await savePlanToIndexedDb(record);
    applyPlannerRecord(record);
    setPlannerStatus("Week saved on this device. You can load it again any time using this month and week.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not save the planner.", "error");
  } finally {
    savePlanButton.disabled = false;
  }
}

async function handleLoadPlan() {
  var data;
  loadPlanButton.disabled = true;
  setPlannerStatus("Loading the saved week...");
  try {
    data = await loadPlanFromIndexedDb(currentYear, Number(monthSelect.value), Number(weekSelect.value));
    resetPlannerForm();
    if (!data) {
      setPlannerStatus("No saved week was found on this device for this month and week.");
      return;
    }
    applyPlannerRecord(data);
    setPlannerStatus("Saved week loaded.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not load the saved week.", "error");
  } finally {
    loadPlanButton.disabled = false;
  }
}

async function handleApplyCurrentTemplate() {
  var response;
  var blob;
  var errorData;
  var filename;
  applyCurrentTemplateButton.disabled = true;
  setPlannerStatus("Applying the current planner data to your PDF template...");
  try {
    response = await fetch(apiRoutes.plannerExportPdf, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(plannerPayload()),
    });
    if (!response.ok) {
      errorData = await response.json();
      throw new Error(errorData.error || "Could not apply the current data to the template.");
    }
    blob = await response.blob();
    filename = suggestedFilenameFromHeaders(response);
    downloadBlob(blob, filename);
    setPlannerStatus("Your template PDF was created from the current data.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not apply the current data to the template.", "error");
  } finally {
    applyCurrentTemplateButton.disabled = false;
  }
}

function initializePlanner() {
  currentYearLabel.textContent = String(currentYear);
  renderMonthOptions();
  renderWeekOptions();
  renderWeekDays();
  renderSectionGrids();

  monthSelect.addEventListener("change", function () {
    renderWeekOptions();
    renderWeekDays();
  });

  weekSelect.addEventListener("change", renderWeekDays);
  savePlanButton.addEventListener("click", handleSavePlan);
  loadPlanButton.addEventListener("click", handleLoadPlan);
  applyCurrentTemplateButton.addEventListener("click", handleApplyCurrentTemplate);
}

initializePlanner();
