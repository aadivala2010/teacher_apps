var yearSelect = document.querySelector("#yearSelect");
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
var downloadDatabaseButton = document.querySelector("#downloadDatabaseButton");
var databaseModal = document.querySelector("#databaseModal");
var databaseWeekList = document.querySelector("#databaseWeekList");
var closeDatabaseModalButton = document.querySelector("#closeDatabaseModalButton");
var cancelDatabaseDownloadButton = document.querySelector("#cancelDatabaseDownloadButton");
var confirmDatabaseDownloadButton = document.querySelector("#confirmDatabaseDownloadButton");
var gridImageInput = document.querySelector("#gridImageInput");
var gridGenerateButton = document.querySelector("#gridGenerateButton");
var gridStatus = document.querySelector("#gridStatus");
var appTabButtons = document.querySelectorAll("[data-app-tab]");
var appViews = document.querySelectorAll("[data-app-view]");
var apiRoutes = {
  gridPdf: "/api/grid-pdf",
  plannerSave: "/api/planner-save",
  plannerUploadAttachment: "/api/planner-upload-attachment",
  plannerLoad: "/api/planner-load",
  plannerExportPdf: "/api/planner-export-pdf",
  plannerExportDocx: "/api/planner-export-docx",
  plannerExportDatabaseDocx: "/api/planner-export-database-docx",
};
var plannerDatabaseName = "teacherPlannerDb";
var plannerDatabaseVersion = 1;
var plannerStoreName = "plans";
var currentAttachments = {};
var maxServerSaveUploadBytes = 4 * 1024 * 1024;
var removedAttachmentFields = {};
var weekLoadSerial = 0;

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

function appNameFromHash() {
  var hash = (window.location.hash || "").replace("#", "").toLowerCase();
  return hash === "grid" ? "grid" : "planner";
}

function showApp(appName, updateHash) {
  var hasMatchingView = false;
  var i;
  var isActive;

  for (i = 0; i < appViews.length; i += 1) {
    if (appViews[i].getAttribute("data-app-view") === appName) {
      hasMatchingView = true;
    }
  }

  if (!hasMatchingView) {
    appName = "planner";
  }

  for (i = 0; i < appTabButtons.length; i += 1) {
    isActive = appTabButtons[i].getAttribute("data-app-tab") === appName;
    appTabButtons[i].classList.toggle("active", isActive);
    appTabButtons[i].setAttribute("aria-selected", isActive ? "true" : "false");
  }

  for (i = 0; i < appViews.length; i += 1) {
    isActive = appViews[i].getAttribute("data-app-view") === appName;
    appViews[i].hidden = !isActive;
    appViews[i].classList.toggle("active", isActive);
  }

  if (updateHash && window.location.hash !== "#" + appName) {
    window.history.replaceState(null, "", "#" + appName);
  }
}

function initializeAppTabs() {
  var i;

  for (i = 0; i < appTabButtons.length; i += 1) {
    appTabButtons[i].addEventListener("click", function () {
      showApp(this.getAttribute("data-app-tab"), true);
    });
  }

  window.addEventListener("hashchange", function () {
    showApp(appNameFromHash(), false);
  });

  showApp(appNameFromHash(), false);
}

var currentYear = new Date().getFullYear();
var weekCache = {};
var databaseExportPlans = [];
var supportedGridImageExtensions = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"];

function setPlannerStatus(message, kind) {
  plannerStatus.textContent = message;
  plannerStatus.className = "status-text" + (kind ? " " + kind : "");
}

function setGridStatus(message, kind) {
  if (!gridStatus) {
    return;
  }
  gridStatus.textContent = message;
  gridStatus.className = "status-text" + (kind ? " " + kind : "");
}

function isSupportedGridImage(file) {
  var name = String(file.name || "").toLowerCase();
  var i;
  for (i = 0; i < supportedGridImageExtensions.length; i += 1) {
    if (name.endsWith(supportedGridImageExtensions[i])) {
      return true;
    }
  }
  return false;
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

function firstWorkdayOfMonth(date) {
  var day = date.getDay();
  if (day === 0 || day === 6) {
    return nextMonday(date);
  }
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function endOfWorkWeek(date) {
  var result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  var day = result.getDay();
  var daysUntilFriday = Math.max(0, 5 - day);
  result.setDate(result.getDate() + daysUntilFriday);
  return result;
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
  var start;
  var monthEnd;
  var weeks;
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

  while (weeks.length < 5 && start <= monthEnd) {
    end = endOfWorkWeek(start);
    if (end > monthEnd) {
      end = monthEnd;
    }
    dates = [];
    for (j = 0; j < 5; j += 1) {
      date = addDays(start, j);
      if (date < firstOfMonth || date > monthEnd) {
        dates.push(null);
      } else {
        dates.push(date);
      }
    }
    weeks.push({
      number: weeks.length + 1,
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

function renderYearOptions() {
  var startYear = currentYear - 2;
  var endYear = currentYear + 5;
  var year;
  yearSelect.innerHTML = "";
  for (year = startYear; year <= endYear; year += 1) {
    yearSelect.appendChild(option(String(year), year));
  }
  yearSelect.value = String(currentYear);
}

function selectedYear() {
  return Number(yearSelect.value || currentYear);
}

function renderWeekOptions() {
  var previousValue = weekSelect.value;
  var weeks = computeMonthWeeks(selectedYear(), Number(monthSelect.value) - 1);
  var i;
  weekSelect.innerHTML = "";
  for (i = 0; i < weeks.length; i += 1) {
    weekSelect.appendChild(option("Week " + weeks[i].number, weeks[i].number));
  }
  if (previousValue && Number(previousValue) <= weeks.length) {
    weekSelect.value = previousValue;
  }
  if (!weekSelect.value) {
    weekSelect.value = "1";
  }
}

function selectedWeekData() {
  var month = Number(monthSelect.value) - 1;
  var weekNumber = Number(weekSelect.value);
  return computeMonthWeeks(selectedYear(), month)[weekNumber - 1];
}

function renderWeekDays() {
  var weekData = selectedWeekData();
  var html = "";
  var i;
  var dateLabel;

  currentYearLabel.textContent = String(selectedYear());
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

function setAttachmentLink(fieldKey, attachment, markRemoved) {
  var target = document.getElementById("attachment-link-" + fieldKey);
  var link;
  var controls;
  var removeButton;
  var input;
  if (!target) {
    return;
  }
  if (!attachment) {
    delete currentAttachments[fieldKey];
    if (markRemoved) {
      removedAttachmentFields[fieldKey] = true;
    }
    target.className = "attachment-empty";
    target.textContent = "No attachment uploaded";
    input = document.getElementById("attachment-" + fieldKey);
    if (input) {
      input.value = "";
    }
    return;
  }
  delete removedAttachmentFields[fieldKey];
  currentAttachments[fieldKey] = attachment;
  target.className = "attachment-actions";
  target.textContent = "";
  controls = document.createElement("div");
  controls.className = "attachment-control-row";
  link = document.createElement("a");
  link.className = "attachment-link";
  link.href = attachment.downloadUrl || attachment.dataUrl || "#";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "Open";
  controls.appendChild(link);
  removeButton = document.createElement("button");
  removeButton.className = "attachment-remove";
  removeButton.type = "button";
  removeButton.dataset.field = fieldKey;
  removeButton.textContent = "Remove";
  controls.appendChild(removeButton);
  target.appendChild(document.createTextNode(attachment.filename || "Attachment"));
  target.appendChild(controls);
}

function handleAttachmentInputChange(event) {
  var input = event.target;
  var file;
  if (!input || input.getAttribute("data-kind") !== "attachment") {
    return;
  }
  file = input.files && input.files[0];
  if (!file) {
    setAttachmentLink(input.dataset.field, null, true);
    return;
  }
  delete removedAttachmentFields[input.dataset.field];
  setAttachmentLink(input.dataset.field, {
    filename: file.name,
    mimeType: file.type || "application/octet-stream",
    dataUrl: URL.createObjectURL(file),
  });
}

function handleAttachmentRemoveClick(event) {
  var target = event.target;
  var button;
  if (!target || !target.closest) {
    return;
  }
  button = target.closest(".attachment-remove");
  if (!button) {
    return;
  }
  setAttachmentLink(button.dataset.field, null, true);
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
  removedAttachmentFields = {};

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
  removedAttachmentFields = {};

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
    year: selectedYear(),
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
    clearAttachmentFields: Object.keys(removedAttachmentFields),
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

function blobToDataUrl(blob) {
  return new Promise(function (resolve, reject) {
    var reader = new FileReader();
    reader.onload = function () {
      resolve(String(reader.result || ""));
    };
    reader.onerror = function () {
      reject(new Error("Could not read one of the saved attachments."));
    };
    reader.readAsDataURL(blob);
  });
}

function dataUrlToBlob(dataUrl) {
  return fetch(dataUrl).then(function (response) {
    return response.blob();
  });
}

async function uploadStoredAttachment(fieldKey, attachment) {
  var blob;
  var formData;
  var response;
  var data;

  if (!attachment || attachment.downloadUrl || !attachment.dataUrl) {
    return attachment;
  }
  blob = await dataUrlToBlob(attachment.dataUrl);
  if (blob.size > maxServerSaveUploadBytes) {
    return {
      filename: attachment.filename || "attachment",
      mimeType: attachment.mimeType || blob.type || "application/octet-stream",
    };
  }
  formData = new FormData();
  formData.append("fieldKey", fieldKey);
  formData.append("attachment", blob, attachment.filename || "attachment");
  response = await fetch(apiRoutes.plannerUploadAttachment, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    return {
      filename: attachment.filename || "attachment",
      mimeType: attachment.mimeType || blob.type || "application/octet-stream",
    };
  }
  data = await response.json();
  return data.attachment || attachment;
}

async function preparePlansForDatabaseExport(plans) {
  var prepared = JSON.parse(JSON.stringify(plans));
  var i;
  var key;
  var attachments;
  var savedPlan;
  var uploaded;
  var planChanged;

  for (i = 0; i < prepared.length; i += 1) {
    planChanged = false;
    savedPlan = JSON.parse(JSON.stringify(prepared[i]));
    attachments = prepared[i].attachments || {};
    for (key in attachments) {
      if (!Object.prototype.hasOwnProperty.call(attachments, key)) {
        continue;
      }
      if (attachments[key] && attachments[key].dataUrl && !attachments[key].downloadUrl) {
        uploaded = await uploadStoredAttachment(key, attachments[key]);
        attachments[key] = uploaded;
        if (uploaded && uploaded.downloadUrl) {
          if (!savedPlan.attachments) {
            savedPlan.attachments = {};
          }
          savedPlan.attachments[key] = uploaded;
          planChanged = true;
        }
      }
    }
    prepared[i].attachments = attachments;
    if (planChanged) {
      await savePlanToIndexedDb(savedPlan);
    }
  }
  return prepared;
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
      setAttachmentLink(input.dataset.field, attachments[input.dataset.field]);
    }
  }

  return attachments;
}

async function collectAttachmentsForPayload() {
  var attachments = {};
  var attachmentInputs = document.querySelectorAll('[data-kind="attachment"]');
  var existingKey;
  var item;
  var response;
  var blob;
  var i;
  var input;
  var file;

  for (existingKey in currentAttachments) {
    if (!Object.prototype.hasOwnProperty.call(currentAttachments, existingKey)) {
      continue;
    }
    item = currentAttachments[existingKey];
    if (item.dataUrl) {
      attachments[existingKey] = item;
    } else if (item.downloadUrl) {
      response = await fetch(item.downloadUrl);
      if (response.ok) {
        blob = await response.blob();
        attachments[existingKey] = {
          filename: item.filename || "attachment",
          mimeType: item.mimeType || blob.type || "application/octet-stream",
          dataUrl: await blobToDataUrl(blob),
        };
      }
    }
  }

  for (i = 0; i < attachmentInputs.length; i += 1) {
    input = attachmentInputs[i];
    if (input.files && input.files[0]) {
      file = input.files[0];
      attachments[input.dataset.field] = {
        filename: file.name,
        mimeType: file.type || "application/octet-stream",
        dataUrl: await readFileAsDataUrl(file),
      };
      setAttachmentLink(input.dataset.field, attachments[input.dataset.field]);
    }
  }

  return attachments;
}

async function plannerPayloadWithAttachments() {
  var payload = plannerPayload();
  payload.attachments = await collectAttachmentsForPayload();
  return payload;
}

function appendAttachmentFiles(formData) {
  var attachmentInputs = document.querySelectorAll('[data-kind="attachment"]');
  var i;
  var input;

  for (i = 0; i < attachmentInputs.length; i += 1) {
    input = attachmentInputs[i];
    if (input.files && input.files[0]) {
      formData.append("attachment::" + input.dataset.field, input.files[0]);
    }
  }
}

function selectedAttachmentByteTotal() {
  var attachmentInputs = document.querySelectorAll('[data-kind="attachment"]');
  var total = 0;
  var i;
  var input;

  for (i = 0; i < attachmentInputs.length; i += 1) {
    input = attachmentInputs[i];
    if (input.files && input.files[0]) {
      total += input.files[0].size || 0;
    }
  }
  return total;
}

async function postMultipart(url, payload) {
  var formData = new FormData();
  formData.append("payload", JSON.stringify(payload));
  appendAttachmentFiles(formData);
  return fetch(url, {
    method: "POST",
    body: formData,
  });
}

async function postJson(url, payload) {
  return fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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

function loadAllPlansFromIndexedDb() {
  return openPlannerDatabase().then(function (db) {
    return new Promise(function (resolve, reject) {
      var transaction = db.transaction(plannerStoreName, "readonly");
      var store = transaction.objectStore(plannerStoreName);
      var request = store.getAll();

      request.onsuccess = function () {
        resolve(request.result || []);
      };

      request.onerror = function () {
        reject(new Error("Could not read the saved database from this browser."));
      };

      transaction.oncomplete = function () {
        db.close();
      };
    });
  });
}

function sortedPlansOldestFirst(plans) {
  return plans.slice().sort(function (a, b) {
    if (Number(a.year) !== Number(b.year)) {
      return Number(a.year) - Number(b.year);
    }
    if (Number(a.month) !== Number(b.month)) {
      return Number(a.month) - Number(b.month);
    }
    return Number(a.weekNumber) - Number(b.weekNumber);
  });
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function databasePlanLabel(plan) {
  var monthLabel = plan.monthLabel || monthNames[Number(plan.month) - 1] || "Month";
  return String(plan.year) + " " + monthLabel + " Week " + String(plan.weekNumber);
}

function databasePlanDetail(plan) {
  var parts = [];
  if (plan.weekStart && plan.weekEnd) {
    parts.push(plan.weekStart + " to " + plan.weekEnd);
  }
  if (plan.className) {
    parts.push(plan.className);
  }
  if (plan.programName) {
    parts.push(plan.programName);
  }
  return parts.join(" | ");
}

function renderDatabaseWeekChoices(plans) {
  var html = "";
  var i;

  for (i = 0; i < plans.length; i += 1) {
    html +=
      '<label class="week-select-row">' +
      '<input type="checkbox" data-export-index="' + i + '" checked />' +
      '<span>' +
      '<strong>' + escapeHtml(databasePlanLabel(plans[i])) + '</strong>' +
      '<small>' + escapeHtml(databasePlanDetail(plans[i])) + '</small>' +
      '</span>' +
      '</label>';
  }
  databaseWeekList.innerHTML = html;
}

function openDatabaseModal(plans) {
  databaseExportPlans = plans;
  renderDatabaseWeekChoices(plans);
  databaseModal.hidden = false;
  confirmDatabaseDownloadButton.focus();
}

function closeDatabaseModal() {
  databaseModal.hidden = true;
  databaseExportPlans = [];
  databaseWeekList.innerHTML = "";
}

function selectedDatabasePlans() {
  var inputs = databaseWeekList.querySelectorAll("[data-export-index]");
  var selected = [];
  var i;
  var index;

  for (i = 0; i < inputs.length; i += 1) {
    if (inputs[i].checked) {
      index = Number(inputs[i].getAttribute("data-export-index"));
      selected.push(databaseExportPlans[index]);
    }
  }
  return selected;
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

async function handleDownloadDatabase() {
  var plans;

  downloadDatabaseButton.disabled = true;
  setPlannerStatus("Loading saved weeks...");
  try {
    plans = sortedPlansOldestFirst(await loadAllPlansFromIndexedDb());
    if (!plans.length) {
      setPlannerStatus("No saved weeks were found in this browser database.");
      return;
    }
    openDatabaseModal(plans);
    setPlannerStatus("Choose which saved weeks to download.");
  } catch (error) {
    setPlannerStatus(error.message || "Could not download the database.", "error");
  } finally {
    downloadDatabaseButton.disabled = false;
  }
}

async function handleGridGenerate() {
  var files = Array.prototype.slice.call((gridImageInput && gridImageInput.files) || []);
  var imageFiles = files.filter(isSupportedGridImage).sort(function (a, b) {
    var aName = a.webkitRelativePath || a.name || "";
    var bName = b.webkitRelativePath || b.name || "";
    return aName.localeCompare(bName, undefined, { numeric: true, sensitivity: "base" });
  });
  var formData;
  var response;
  var errorData;
  var blob;
  var i;

  if (!imageFiles.length) {
    setGridStatus("Select a folder with supported image files first.", "error");
    return;
  }

  gridGenerateButton.disabled = true;
  setGridStatus("Creating 2x2.pdf...");
  try {
    formData = new FormData();
    for (i = 0; i < imageFiles.length; i += 1) {
      formData.append("images::" + i, imageFiles[i], imageFiles[i].webkitRelativePath || imageFiles[i].name);
    }
    response = await fetch(apiRoutes.gridPdf, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      errorData = await response.json();
      throw new Error(errorData.error || "Could not generate the 2x2 PDF.");
    }
    blob = await response.blob();
    downloadBlob(blob, "2x2.pdf");
    setGridStatus("2x2.pdf was created with " + imageFiles.length + " image" + (imageFiles.length === 1 ? "." : "s."), "success");
  } catch (error) {
    setGridStatus(error.message || "Could not generate the 2x2 PDF.", "error");
  } finally {
    gridGenerateButton.disabled = false;
  }
}

async function handleConfirmDatabaseDownload() {
  var plans = selectedDatabasePlans();
  var preparedPlans;
  var exportData;
  var response;
  var errorData;
  var blob;
  var filename;

  if (!plans.length) {
    setPlannerStatus("Select at least one saved week to download.");
    return;
  }
  confirmDatabaseDownloadButton.disabled = true;
  setPlannerStatus("Preparing attachment links...");
  try {
    preparedPlans = await preparePlansForDatabaseExport(plans);
  } catch (error) {
    setPlannerStatus(error.message || "Could not prepare attachment links.", "error");
    confirmDatabaseDownloadButton.disabled = false;
    return;
  }
  exportData = {
    exportedAt: new Date().toISOString(),
    baseUrl: window.location.origin,
    source: window.location.hostname || "local",
    order: "oldest-to-newest-by-year-month-week",
    savedWeeks: preparedPlans,
  };
  setPlannerStatus("Creating your Word database...");
  try {
    response = await postJson(apiRoutes.plannerExportDatabaseDocx, exportData);
    if (!response.ok) {
      errorData = await response.json();
      throw new Error(errorData.error || "Could not create the Word database.");
    }
    blob = await response.blob();
    filename = suggestedFilenameFromHeaders(response);
    downloadBlob(blob, filename);
    closeDatabaseModal();
    setPlannerStatus("Selected saved weeks downloaded as a Word database.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not create the Word database.", "error");
  } finally {
    confirmDatabaseDownloadButton.disabled = false;
  }
}

async function handleSavePlan() {
  var payload;
  var attachments;
  var record;
  var response;
  var data;
  savePlanButton.disabled = true;
  setPlannerStatus("Saving this week...");
  try {
    payload = plannerPayload();
    if (selectedAttachmentByteTotal() <= maxServerSaveUploadBytes) {
      try {
        response = await postMultipart(apiRoutes.plannerSave, payload);
        data = await response.json();
        if (response.ok && data.plan) {
          await savePlanToIndexedDb(data.plan);
          applyPlannerRecord(data.plan);
          setPlannerStatus("Week saved to the website backend. Attachments are ready for database links.", "success");
          return;
        }
      } catch (serverError) {
        // Fall back to browser storage if the hosted backend rejects or times out.
      }
    }

    attachments = await collectAttachmentsForStorage();
    record = JSON.parse(JSON.stringify(payload));
    record.attachments = attachments;
    await savePlanToIndexedDb(record);
    applyPlannerRecord(record);
    setPlannerStatus("Week saved on this device. Attachments will be uploaded when you download the Word database.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not save the planner.", "error");
  } finally {
    savePlanButton.disabled = false;
  }
}

async function handleLoadPlan() {
  loadPlanButton.disabled = true;
  setPlannerStatus("Loading the saved week...");
  try {
    if (!(await loadSelectedWeekIntoForm())) {
      setPlannerStatus("No saved week was found on this device for this month and week.");
      return;
    }
    setPlannerStatus("Saved week loaded.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not load the saved week.", "error");
  } finally {
    loadPlanButton.disabled = false;
  }
}

function selectedWeekLookup() {
  return {
    year: selectedYear(),
    month: Number(monthSelect.value),
    weekNumber: Number(weekSelect.value),
  };
}

async function loadSelectedWeekIntoForm() {
  var lookup = selectedWeekLookup();
  var response;
  var serverData;
  var data;

  resetPlannerForm();
  try {
    response = await postJson(apiRoutes.plannerLoad, lookup);
    serverData = await response.json();
    if (response.ok && serverData.plan) {
      applyPlannerRecord(serverData.plan);
      await savePlanToIndexedDb(serverData.plan);
      return true;
    }
  } catch (serverError) {
    // Fall back to browser storage when the backend has no saved copy.
  }

  data = await loadPlanFromIndexedDb(lookup.year, lookup.month, lookup.weekNumber);
  if (!data) {
    return false;
  }
  applyPlannerRecord(data);
  return true;
}

async function handleSelectedWeekChanged() {
  var serial = weekLoadSerial + 1;
  weekLoadSerial = serial;
  renderWeekDays();
  resetPlannerForm();
  setPlannerStatus("Loading selected week...");
  try {
    if (await loadSelectedWeekIntoForm()) {
      if (serial === weekLoadSerial) {
        setPlannerStatus("Saved week loaded.", "success");
      }
      return;
    }
    if (serial === weekLoadSerial) {
      setPlannerStatus("New blank week ready.");
    }
  } catch (error) {
    if (serial === weekLoadSerial) {
      setPlannerStatus(error.message || "Could not load this week.", "error");
    }
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
  initializeAppTabs();
  renderYearOptions();
  currentYearLabel.textContent = String(selectedYear());
  renderMonthOptions();
  renderWeekOptions();
  renderWeekDays();
  renderSectionGrids();
  document.addEventListener("change", handleAttachmentInputChange);
  document.addEventListener("click", handleAttachmentRemoveClick);
  if (gridGenerateButton) {
    gridGenerateButton.addEventListener("click", handleGridGenerate);
  }

  yearSelect.addEventListener("change", function () {
    renderWeekOptions();
    handleSelectedWeekChanged();
  });

  monthSelect.addEventListener("change", function () {
    renderWeekOptions();
    handleSelectedWeekChanged();
  });

  weekSelect.addEventListener("change", handleSelectedWeekChanged);
  savePlanButton.addEventListener("click", handleSavePlan);
  loadPlanButton.addEventListener("click", handleLoadPlan);
  applyCurrentTemplateButton.addEventListener("click", handleApplyCurrentTemplate);
  downloadDatabaseButton.addEventListener("click", handleDownloadDatabase);
  closeDatabaseModalButton.addEventListener("click", closeDatabaseModal);
  cancelDatabaseDownloadButton.addEventListener("click", closeDatabaseModal);
  confirmDatabaseDownloadButton.addEventListener("click", handleConfirmDatabaseDownload);
  databaseModal.addEventListener("click", function (event) {
    if (event.target === databaseModal) {
      closeDatabaseModal();
    }
  });
  handleSelectedWeekChanged();
}

initializePlanner();
