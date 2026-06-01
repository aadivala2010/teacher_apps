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
var applySavedTemplateButton = document.querySelector("#applySavedTemplateButton");
var apiRoutes = {
  plannerSave: "/api/planner-save",
  plannerLoad: "/api/planner-load",
  plannerExportPdf: "/api/planner-export-pdf",
  plannerExportSavedPdf: "/api/planner-export-saved-pdf",
};

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

function option(label, value) {
  var el = document.createElement("option");
  el.value = String(value);
  el.textContent = label;
  return el;
}

function titleCaseWeekRange(weekData) {
  return weekData.startLabel + " - " + weekData.endLabel;
}

function startOfMonday(date) {
  var result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  var day = result.getDay();
  var delta = day === 0 ? -6 : 1 - day;
  result.setDate(result.getDate() + delta);
  return result;
}

function addDays(date, count) {
  var result = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  result.setDate(result.getDate() + count);
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
  var firstWeekStart;
  var weeks;
  var i;
  var start;
  var end;
  var dates;
  var j;

  if (weekCache[cacheKey]) {
    return weekCache[cacheKey];
  }

  firstOfMonth = new Date(year, monthIndex, 1);
  firstWeekStart = startOfMonday(firstOfMonth);
  weeks = [];

  for (i = 0; i < 5; i += 1) {
    start = addDays(firstWeekStart, i * 7);
    end = addDays(start, 4);
    dates = [];
    for (j = 0; j < 5; j += 1) {
      dates.push(addDays(start, j));
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

  selectedWeekRange.textContent = titleCaseWeekRange(weekData);

  for (i = 0; i < dayLabels.length; i += 1) {
    html +=
      '<div class="day-chip">' +
      "<strong>" +
      dayLabels[i] +
      "</strong>" +
      "<span>" +
      formatDateLabel(weekData.dates[i]) +
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
    target.className = "attachment-empty";
    target.textContent = "No attachment uploaded";
    return;
  }
  target.className = "";
  target.innerHTML =
    '<a class="attachment-link" href="' +
    attachment.downloadUrl +
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
  var response;
  var data;
  savePlanButton.disabled = true;
  setPlannerStatus("Saving this week to the database...");
  try {
    response = await postMultipart(apiRoutes.plannerSave, plannerPayload());
    data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not save the planner.");
    }
    applyPlannerRecord(data.plan);
    setPlannerStatus("Week saved. You can load it again any time using this month and week.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not save the planner.", "error");
  } finally {
    savePlanButton.disabled = false;
  }
}

async function handleLoadPlan() {
  var response;
  var data;
  loadPlanButton.disabled = true;
  setPlannerStatus("Loading the saved week...");
  try {
    response = await postJson(apiRoutes.plannerLoad, {
      year: currentYear,
      month: Number(monthSelect.value),
      weekNumber: Number(weekSelect.value),
    });
    data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not load the saved week.");
    }
    resetPlannerForm();
    if (!data.plan) {
      setPlannerStatus("No saved week was found for this month and week.");
      return;
    }
    applyPlannerRecord(data.plan);
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
    response = await postJson(apiRoutes.plannerExportPdf, plannerPayload());
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

async function handleApplySavedTemplate() {
  var response;
  var blob;
  var errorData;
  var filename;
  applySavedTemplateButton.disabled = true;
  setPlannerStatus("Applying the saved week to your PDF template...");
  try {
    response = await postJson(apiRoutes.plannerExportSavedPdf, {
      year: currentYear,
      month: Number(monthSelect.value),
      weekNumber: Number(weekSelect.value),
      monthLabel: monthNames[Number(monthSelect.value) - 1],
    });
    if (!response.ok) {
      errorData = await response.json();
      throw new Error(errorData.error || "Could not apply the saved week to the template.");
    }
    blob = await response.blob();
    filename = suggestedFilenameFromHeaders(response);
    downloadBlob(blob, filename);
    setPlannerStatus("Your template PDF was created from the saved week.", "success");
  } catch (error) {
    setPlannerStatus(error.message || "Could not apply the saved week to the template.", "error");
  } finally {
    applySavedTemplateButton.disabled = false;
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
  applySavedTemplateButton.addEventListener("click", handleApplySavedTemplate);
}

initializePlanner();
