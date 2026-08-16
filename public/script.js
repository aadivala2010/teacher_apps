var yearSelect = document.querySelector("#yearSelect");
var monthSelect = document.querySelector("#monthSelect");
var weekSelect = document.querySelector("#weekSelect");
var savedWeeksSelect = document.querySelector("#savedWeeksSelect");
var classInput = document.querySelector("#classInput");
var programInput = document.querySelector("#programInput");
var themeInput = document.querySelector("#themeInput");
var booksInput = document.querySelector("#booksInput");
var currentYearLabel = document.querySelector("#currentYearLabel");
var selectedWeekRange = document.querySelector("#selectedWeekRange");
var plannerStatus = document.querySelector("#plannerStatus");
var weekDays = document.querySelector("#weekDays");
var dailyActivities = document.querySelector("#dailyActivities");
var outdoorGrid = document.querySelector("#outdoorGrid");
var centersGrid = document.querySelector("#centersGrid");
var savePlanButton = document.querySelector("#savePlanButton");
var applyCurrentTemplateButton = document.querySelector("#applyCurrentTemplateButton");
var downloadDatabaseButton = document.querySelector("#downloadDatabaseButton");
var databaseModal = document.querySelector("#databaseModal");
var databaseWeekList = document.querySelector("#databaseWeekList");
var closeDatabaseModalButton = document.querySelector("#closeDatabaseModalButton");
var cancelDatabaseDownloadButton = document.querySelector("#cancelDatabaseDownloadButton");
var confirmDatabaseDownloadButton = document.querySelector("#confirmDatabaseDownloadButton");
var gridImageInput = document.querySelector("#gridImageInput");
var gridImageFilesInput = document.querySelector("#gridImageFilesInput");
var gridGenerateButton = document.querySelector("#gridGenerateButton");
var gridStatus = document.querySelector("#gridStatus");
var gridOrientationField = document.querySelector("#gridOrientationField");
var gridPrintCellsContainer = document.querySelector("#gridPrintCells");
var gridPrintGenerateButton = document.querySelector("#gridPrintGenerateButton");
var gridPrintClearButton = document.querySelector("#gridPrintClearButton");
var gridPrintStatus = document.querySelector("#gridPrintStatus");
var GRID_PRINT_SLOT_COUNT = 12;
var gridPrintSlots = new Array(GRID_PRINT_SLOT_COUNT).fill(null);

if (gridImageInput && /iPad|iPhone|iPod/.test(navigator.userAgent || "")) {
  gridImageInput.removeAttribute("webkitdirectory");
  gridImageInput.removeAttribute("directory");
}
var appTabButtons = document.querySelectorAll("[data-app-tab]");
var appViews = document.querySelectorAll("[data-app-view]");
var apiRoutes = {
  gridPdf: "/api/grid-pdf",
  gridPrintPdf: "/api/grid-print-pdf",
  plannerSave: "/api/planner-save",
  plannerUploadAttachment: "/api/planner-upload-attachment",
  plannerLoad: "/api/planner-load",
  plannerExportPdf: "/api/planner-export-pdf",
  plannerExportDocx: "/api/planner-export-docx",
  plannerExportDatabaseDocx: "/api/planner-export-database-docx",
  authSignup: "/api/auth-signup",
  authLogin: "/api/auth-login",
  authRefresh: "/api/auth-refresh",
  authMe: "/api/auth-me",
  syncSave: "/api/sync-save",
  syncLoad: "/api/sync-load",
  syncList: "/api/sync-list",
  syncDelete: "/api/sync-delete",
  syncAttachmentUpload: "/api/sync-upload-attachment",
};
var plannerDatabaseName = "teacherPlannerDb";
var plannerDatabaseVersion = 1;
var plannerStoreName = "plans";
var currentAttachments = {};
var maxServerSaveUploadBytes = 4 * 1024 * 1024;
var removedAttachmentFields = {};
var weekLoadSerial = 0;
var plannerDirty = false;
var activityDirty = false;
var UNSAVED_CHANGES_MESSAGE =
  "You have unsaved changes. They will be lost if you leave now.\n\nClick Cancel to go back and save, or OK to discard the changes.";

function markPlannerDirty() {
  if (!plannerDirty) {
    plannerDirty = true;
    setPlannerStatus("You have unsaved changes. Click \"Save Data\" before switching weeks or leaving this page.");
  }
}

function markActivityDirty() {
  if (!activityDirty) {
    activityDirty = true;
    setActivityStatus("You have unsaved changes. Click \"Save Data\" before switching dates or leaving this page.");
  }
}

var previousYearValue;
var previousMonthValue;
var previousWeekValue;
function syncPreviousWeekSelectors() {
  previousYearValue = yearSelect.value;
  previousMonthValue = monthSelect.value;
  previousWeekValue = weekSelect.value;
}

// Ask before discarding unsaved edits (e.g. changing the week dropdown or the
// activity date without saving first). Reverts the control via revertFn if the
// teacher cancels.
function confirmDiscardChanges(isDirty, revertFn) {
  if (!isDirty) {
    return true;
  }
  var proceed = window.confirm(UNSAVED_CHANGES_MESSAGE);
  if (!proceed && revertFn) {
    revertFn();
  }
  return proceed;
}

window.addEventListener("beforeunload", function (event) {
  if (plannerDirty || activityDirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

var authToken = localStorage.getItem("authToken") || "";
var authRefreshToken = localStorage.getItem("authRefreshToken") || "";
var authExpiresAt = Number(localStorage.getItem("authExpiresAt") || "0");
var authUser = null;
var isSyncing = false;
var refreshInFlight = null;

var assessmentOptions = [
  "Checklist",
  "Observation with Notes",
  "Portfolio",
];

var linksToLearningOptions = [
  {
    category: "Language & Literacy",
    items: [
      "Demonstrates an understanding of letters and the letter/sound relationship",
      "Recognizes common beginning and ending sounds",
      "Appropriately uses newly acquired vocabulary",
      "Knows some opposite words",
      "Identifies and uses rhyming words",
      "Reads/recognizes sight words",
      "Engages in conversations about high-interest topics",
      "Understands print concepts",
      "Discusses setting and characters, and recalls the sequence of events in a story",
      "Identifies features of a book and begins to recognize books written by specific authors",
      "Understands whether information in a story is fiction or nonfiction",
      "Recognizes the difference between words, letters, and numerals",
      "Writes words using inventive spelling",
      "Writes letters of the alphabet (uppercase and lowercase)",
      "Writes first and last name in proper case",
      "Writes numerals 1–50",
    ],
  },
  {
    category: "Mathematical Thinking",
    items: [
      "Counts and recognizes numerals 1–50",
      "Counts by tens",
      "Compares quantities, identifying more than, less than, or equal amounts",
      "Develops the concept of subtraction and addition",
      "Creates and interprets simple graphs",
      "Describes a five-step procedure in sequential order",
      "Identifies and describes 3D and 2D shapes by name and characteristics",
      "Follows simple directions related to spatial vocabulary",
      "Uses some ordinal numbers",
      "Orders days of the week and months of the year",
      "Identifies coins by sight and associated value",
      "Completes 25+ piece puzzles",
      "Repeats, extends, and creates simple patterns using concrete objects",
    ],
  },
  {
    category: "Wellness",
    items: [
      "Uses hands and eyes together to complete complex fine motor tasks",
      "Engages in complex body movements, promoting gross muscle development and balance",
      "Discusses and explores ways to keep his/her body safe and healthy",
    ],
  },
  {
    category: "Creative Expression",
    items: [
      "Shows increased awareness of musical components and vocabulary",
      "Participates in discussions about different genres of music and entertainment concepts",
      "Demonstrates spatial awareness while moving physically",
      "Creates an original piece of art",
      "Identifies different forms of visual art and artists",
      "Engages in imaginative play related to personal experiences and interests using props",
    ],
  },
  {
    category: "Social-Emotional Learning",
    items: [
      "Pays attention to others and initiates how they solve problems, ask for solutions, and use them",
      "Proactively suggests solutions for pragmatic situations",
      "Plays cooperatively with peers and shows concern toward the feelings of others",
      "Takes responsibility for meeting own needs",
      "Remains engaged in self-directed activities",
      "Actively engages in conversations with adults and peers",
      "Demonstrates control over emotions",
      "Establishes and sustains positive relationships",
    ],
  },
  {
    category: "Scientific Exploration",
    items: [
      "Understands how to have a positive/negative impact on the Earth's environment",
      "Participates in science experiments and makes predictions",
      "Understands seasonal changes and the impact on local weather",
      "Describes, classifies, and categorizes living and nonliving things",
      "Uses simple tools to investigate objects and materials",
      "Demonstrates appropriate use for various technology tools",
    ],
  },
  {
    category: "Citizens of the World",
    items: [
      "Explores and recognizes the meaning of various celebrations and traditions",
      "Recognizes the use of money as a means of exchange for goods and services",
      "Notices that people grow and change over time",
      "Demonstrates geographic knowledge",
      "Understands roles and identifies common places in the community",
      "Identifies important people throughout history",
      "Actively pursues knowledge about another country in the world",
      "Demonstrates acceptance of people who are similar and different",
      "Explores languages spoken throughout the world, including Spanish",
      "Understands that families and individuals have unique characteristics",
    ],
  },
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
  var i;
  for (i = 0; i < appViews.length; i += 1) {
    if (appViews[i].getAttribute("data-app-view") === hash) {
      return hash;
    }
  }
  return "planner";
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

var authButton = document.querySelector("#authButton");
var authModal = document.querySelector("#authModal");
var closeAuthModalButton = document.querySelector("#closeAuthModalButton");
var authEmailInput = document.querySelector("#authEmailInput");
var authPasswordInput = document.querySelector("#authPasswordInput");
var authSignInButton = document.querySelector("#authSignInButton");
var authSignUpButton = document.querySelector("#authSignUpButton");
var authStatus = document.querySelector("#authStatus");
var authUserInfo = document.querySelector("#authUserInfo");
var authUserEmail = document.querySelector("#authUserEmail");
var authSignOutButton = document.querySelector("#authSignOutButton");

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

function isImageType(mimeType) {
  return mimeType && mimeType.startsWith("image/") && mimeType !== "image/gif" && !mimeType.includes("svg");
}

async function compressImageIfNeeded(file, maxBytes) {
  maxBytes = maxBytes || 1048576;
  if (!isImageType(file.type) || file.size <= maxBytes) {
    return file;
  }
  return new Promise(function (resolve, reject) {
    var img = new Image();
    img.onload = function () {
      URL.revokeObjectURL(img.src);
      var canvas = document.createElement("canvas");
      var ctx = canvas.getContext("2d");
      var MAX_DIM = 1920;
      var w = img.width;
      var h = img.height;
      if (w > MAX_DIM || h > MAX_DIM) {
        var scale = Math.min(MAX_DIM / w, MAX_DIM / h);
        w = Math.round(w * scale);
        h = Math.round(h * scale);
      }
      canvas.width = w;
      canvas.height = h;
      ctx.drawImage(img, 0, 0, w, h);
      function tryQuality(quality) {
        canvas.toBlob(function (blob) {
          if (!blob) { resolve(file); return; }
          if (blob.size <= maxBytes || quality <= 0.05) {
            var name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
            resolve(new File([blob], name, { type: "image/jpeg" }));
          } else {
            tryQuality(Math.max(quality - 0.1, 0.05));
          }
        }, "image/jpeg", quality);
      }
      tryQuality(0.85);
    };
    img.onerror = function () { resolve(file); };
    img.src = URL.createObjectURL(file);
  });
}

function authHeaders() {
  return authToken ? { "Authorization": "Bearer " + authToken } : {};
}

function storeSession(session) {
  if (!session || !session.access_token) {
    return;
  }
  authToken = session.access_token;
  authRefreshToken = session.refresh_token || authRefreshToken;
  authExpiresAt = Number(session.expires_at || 0);
  localStorage.setItem("authToken", authToken);
  if (authRefreshToken) {
    localStorage.setItem("authRefreshToken", authRefreshToken);
  }
  localStorage.setItem("authExpiresAt", String(authExpiresAt));
}

// Refresh the access token when it is expired or within two minutes of
// expiring, so signed-in teachers keep syncing without being logged out.
async function ensureFreshToken() {
  if (!authToken || !authRefreshToken) {
    return authToken;
  }
  var nowSeconds = Math.floor(Date.now() / 1000);
  if (authExpiresAt && authExpiresAt - nowSeconds > 120) {
    return authToken;
  }
  if (refreshInFlight) {
    return refreshInFlight;
  }
  refreshInFlight = (async function () {
    try {
      var response = await fetch(apiRoutes.authRefresh, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: authRefreshToken }),
      });
      var data = await response.json();
      if (response.ok && data.session && data.session.access_token) {
        storeSession(data.session);
        if (data.user) {
          authUser = data.user;
        }
        return authToken;
      }
    } catch (e) {
      // Network error - keep the existing token and try again later.
      refreshInFlight = null;
      return authToken;
    }
    // Refresh was rejected: the session is truly gone.
    setAuthState(null);
    refreshInFlight = null;
    return "";
  })();
  var result = await refreshInFlight;
  refreshInFlight = null;
  return result;
}

function setAuthState(user) {
  authUser = user;
  if (user) {
    authButton.hidden = true;
    authUserInfo.hidden = false;
    authUserEmail.textContent = user.email;
  } else {
    authToken = "";
    authRefreshToken = "";
    authExpiresAt = 0;
    localStorage.removeItem("authToken");
    localStorage.removeItem("authRefreshToken");
    localStorage.removeItem("authExpiresAt");
    authUser = null;
    authButton.hidden = false;
    authUserInfo.hidden = true;
    authUserEmail.textContent = "";
  }
}

async function checkAuth() {
  if (!authToken) {
    setAuthState(null);
    return;
  }
  await ensureFreshToken();
  if (!authToken) {
    return;
  }
  try {
    var response = await fetch(apiRoutes.authMe, { headers: authHeaders() });
    var data = await response.json();
    if (data && data.user) {
      setAuthState(data.user);
    } else {
      // Token was rejected - attempt one refresh before giving up.
      var refreshed = await ensureFreshToken();
      if (refreshed) {
        var retry = await fetch(apiRoutes.authMe, { headers: authHeaders() });
        var retryData = await retry.json();
        if (retryData && retryData.user) {
          setAuthState(retryData.user);
          return;
        }
      }
      setAuthState(null);
    }
  } catch (e) {
    // Network hiccup - keep the session so offline/flaky use still works.
  }
}

function openAuthModal() {
  authEmailInput.value = "";
  authPasswordInput.value = "";
  authStatus.textContent = "";
  authStatus.className = "status-text";
  authModal.hidden = false;
  authEmailInput.focus();
}

function closeAuthModal() {
  authModal.hidden = true;
}

async function handleAuthSignIn() {
  var email = authEmailInput.value.trim();
  var password = authPasswordInput.value;
  if (!email || !password) {
    authStatus.textContent = "Enter your email and password.";
    authStatus.className = "status-text error";
    return;
  }
  authSignInButton.disabled = true;
  authStatus.textContent = "Signing in...";
  authStatus.className = "status-text";
  try {
    var response = await fetch(apiRoutes.authLogin, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password }),
    });
    var data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Sign in failed.");
    }
    storeSession(data.session);
    setAuthState(data.user);
    closeAuthModal();
    setPlannerStatus("Signed in as " + data.user.email + ". Syncing data...");
    syncAllLocalToCloud();
    syncAllLocalActivitiesToCloud();
  } catch (error) {
    authStatus.textContent = error.message || "Could not sign in.";
    authStatus.className = "status-text error";
  } finally {
    authSignInButton.disabled = false;
  }
}

async function handleAuthSignUp() {
  var email = authEmailInput.value.trim();
  var password = authPasswordInput.value;
  if (!email || !password) {
    authStatus.textContent = "Enter your email and password.";
    authStatus.className = "status-text error";
    return;
  }
  if (password.length < 6) {
    authStatus.textContent = "Password must be at least 6 characters.";
    authStatus.className = "status-text error";
    return;
  }
  authSignUpButton.disabled = true;
  authStatus.textContent = "Creating account...";
  authStatus.className = "status-text";
  try {
    var response = await fetch(apiRoutes.authSignup, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password }),
    });
    var data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Could not create account.");
    }
    storeSession(data.session);
    setAuthState(data.user);
    closeAuthModal();
    setPlannerStatus("Account created and signed in as " + data.user.email + ". Syncing data...");
    syncAllLocalToCloud();
    syncAllLocalActivitiesToCloud();
  } catch (error) {
    authStatus.textContent = error.message || "Could not create account.";
    authStatus.className = "status-text error";
  } finally {
    authSignUpButton.disabled = false;
  }
}

function handleAuthSignOut() {
  setAuthState(null);
  setPlannerStatus("Signed out. Data will no longer sync to the cloud.");
}

async function uploadAttachmentToCloud(fieldKey, attachment, planLookup) {
  if (!attachment) {
    return attachment;
  }
  var url = attachment.downloadUrl || "";
  if (url && !url.startsWith("/api/")) {
    return attachment;
  }
  if (url.startsWith("/api/sync-attachment")) {
    return attachment;
  }
  var blob;
  if (attachment.dataUrl) {
    blob = await dataUrlToBlob(attachment.dataUrl);
  } else if (url.startsWith("/api/")) {
    try {
      var resp = await fetch(url);
      if (resp.ok) {
        blob = await resp.blob();
      }
    } catch (e) {
      return attachment;
    }
  }
  if (!blob) {
    return attachment;
  }
  var file = new File([blob], attachment.filename || "attachment", { type: attachment.mimeType || blob.type || "application/octet-stream" });
  file = await compressImageIfNeeded(file);
  blob = file;
  var formData = new FormData();
  formData.append("fieldKey", fieldKey);
  formData.append("planLookup", JSON.stringify(planLookup));
  formData.append("attachment", blob, attachment.filename || "attachment");
  try {
    var response = await fetch(apiRoutes.syncAttachmentUpload, {
      method: "POST",
      headers: { "Authorization": "Bearer " + authToken },
      body: formData,
    });
    if (response.ok) {
      var data = await response.json();
      if (data.attachment) {
        return data.attachment;
      }
    }
  } catch (e) {
    // Upload failed, return original
  }
  return attachment;
}

async function syncPlanToCloud(record) {
  await ensureFreshToken();
  if (!authToken || !authUser) {
    return null;
  }
  try {
    var attachments = record.attachments || {};
    var planLookup = { year: record.year, month: record.month, weekNumber: record.weekNumber };
    var hasChanges = false;
    for (var key in attachments) {
      if (Object.prototype.hasOwnProperty.call(attachments, key)) {
        var originalDataUrl = attachments[key] && attachments[key].dataUrl;
        var uploaded = await uploadAttachmentToCloud(key, attachments[key], planLookup);
        if (uploaded !== attachments[key]) {
          if (originalDataUrl && !uploaded.dataUrl) {
            uploaded.dataUrl = originalDataUrl;
          }
          attachments[key] = uploaded;
          hasChanges = true;
        }
      }
    }
    if (hasChanges) {
      record.attachments = attachments;
    }

    var response = await fetch(apiRoutes.syncSave, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
      body: JSON.stringify(record),
    });
    var data = await response.json();
    if (response.ok && data.plan) {
      return data.plan;
    }
  } catch (e) {
    // Cloud sync failed silently - local data is safe
  }
  return null;
}

async function loadPlanFromCloud(year, month, weekNumber) {
  await ensureFreshToken();
  if (!authToken || !authUser) {
    return null;
  }
  try {
    var response = await fetch(apiRoutes.syncLoad, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
      body: JSON.stringify({ year: year, month: month, weekNumber: weekNumber }),
    });
    var data = await response.json();
    if (response.ok && data.plan) {
      return data.plan;
    }
  } catch (e) {
    // Cloud load failed silently
  }
  return null;
}

async function syncAllLocalToCloud() {
  if (!authToken || !authUser || isSyncing) {
    return;
  }
  isSyncing = true;
  try {
    var localPlans = await loadAllPlansFromIndexedDb();
    if (!localPlans || !localPlans.length) {
      setPlannerStatus("Signed in. No local data to sync.");
      return;
    }
    setPlannerStatus("Syncing " + localPlans.length + " saved week(s) to the cloud...");
    var synced = 0;
    for (var i = 0; i < localPlans.length; i += 1) {
      var record = JSON.parse(JSON.stringify(localPlans[i]));
      delete record.storageKey;
      var result = await syncPlanToCloud(record);
      if (result) {
        synced += 1;
      }
    }
    setPlannerStatus("Synced " + synced + " of " + localPlans.length + " week(s) to the cloud.", "success");
  } catch (e) {
    setPlannerStatus("Cloud sync completed with some issues.", "success");
  } finally {
    isSyncing = false;
    refreshSavedWeeksDropdown();
  }
}

function plannerStorageKey(year, month, weekNumber) {
  return String(year) + "-" + String(month) + "-" + String(weekNumber);
}

async function listPlansFromCloud() {
  await ensureFreshToken();
  if (!authToken || !authUser) {
    return [];
  }
  try {
    var response = await fetch(apiRoutes.syncList, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
      body: "{}",
    });
    var data = await response.json();
    if (response.ok && data.plans) {
      return data.plans;
    }
  } catch (e) {
    // Cloud list failed silently - local list still works
  }
  return [];
}

// Fill the Saved Weeks dropdown with every saved week (local + cloud), newest first.
async function refreshSavedWeeksDropdown() {
  if (!savedWeeksSelect) {
    return;
  }
  var byKey = {};
  function collect(plan) {
    if (plan && plan.year && plan.month && plan.weekNumber) {
      byKey[plannerStorageKey(plan.year, plan.month, plan.weekNumber)] = plan;
    }
  }
  try {
    (await loadAllPlansFromIndexedDb()).forEach(collect);
  } catch (e) {
    // No local database yet
  }
  (await listPlansFromCloud()).forEach(collect);

  var plans = sortedPlansOldestFirst(Object.keys(byKey).map(function (key) { return byKey[key]; })).reverse();
  savedWeeksSelect.innerHTML = "";
  savedWeeksSelect.appendChild(option("Load Saved Week", ""));
  plans.forEach(function (plan) {
    var label = databasePlanLabel(plan);
    if (plan.theme) {
      label += " - " + plan.theme;
    }
    savedWeeksSelect.appendChild(option(label, plannerStorageKey(plan.year, plan.month, plan.weekNumber)));
  });
  savedWeeksSelect.value = "";
}

async function handleSavedWeekPicked() {
  var key = savedWeeksSelect.value;
  if (!key) {
    return;
  }
  if (!confirmDiscardChanges(plannerDirty, function () { savedWeeksSelect.value = ""; })) {
    return;
  }
  var parts = key.split("-");
  yearSelect.value = parts[0];
  monthSelect.value = parts[1];
  renderWeekOptions();
  weekSelect.value = parts[2];
  savedWeeksSelect.value = "";
  await handleSelectedWeekChanged();
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
  var month = String(date.getMonth() + 1).padStart(2, "0");
  var day = String(date.getDate()).padStart(2, "0");
  return month + "/" + day + "/" + date.getFullYear();
}

function formatIsoToDisplay(isoDate) {
  if (!isoDate) return "";
  var parts = isoDate.split("-");
  return parts[1] + "/" + parts[2] + "/" + parts[0];
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

function isToday(date) {
  var now = new Date();
  return !!date && date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth() && date.getDate() === now.getDate();
}

function renderWeekDays() {
  var weekData = selectedWeekData();
  var html = "";
  var i;
  var dateLabel;
  var chipClass;

  currentYearLabel.textContent = String(selectedYear());
  selectedWeekRange.textContent = titleCaseWeekRange(weekData);

  for (i = 0; i < dayLabels.length; i += 1) {
    dateLabel = weekData.dates[i] ? formatDateLabel(weekData.dates[i]) : "Outside this month";
    chipClass = "day-chip" + (isToday(weekData.dates[i]) ? " is-today" : "");
    html +=
      '<div class="' + chipClass + '">' +
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

function linksToLearningSelectHtml(fieldKey) {
  var html = '<select data-field="' + fieldKey + '" data-kind="links-to-learning">';
  var g, i;
  html += '<option value="">Links to learning</option>';
  for (g = 0; g < linksToLearningOptions.length; g += 1) {
    html += '<optgroup label="' + linksToLearningOptions[g].category + '">';
    for (i = 0; i < linksToLearningOptions[g].items.length; i += 1) {
      html += '<option value="' + linksToLearningOptions[g].items[i] + '">' + linksToLearningOptions[g].items[i] + "</option>";
    }
    html += "</optgroup>";
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
    linksToLearningSelectHtml(fieldKey) +
    attachmentHtml(fieldKey) +
    "</article>"
  );
}

function renderSectionGrids() {
  var html = "";
  var i;

  for (i = 0; i < dayLabels.length; i += 1) {
    html +=
      '<section class="day-section" aria-labelledby="day-heading-' + dayKeys[i] + '">' +
      '<h3 id="day-heading-' + dayKeys[i] + '" class="day-section-heading">' + dayLabels[i] + "</h3>" +
      '<div class="day-activity-grid">' +
      activityCardHtml("Circle Time", "circle_time." + dayKeys[i], 6) +
      activityCardHtml("Small Group Learning Experience 1", "small_group_1." + dayKeys[i], 6) +
      activityCardHtml("Small Group Learning Experience 2", "small_group_2." + dayKeys[i], 6) +
      "</div>" +
      "</section>";
  }
  dailyActivities.innerHTML = html;

  outdoorGrid.innerHTML = activityCardHtml("Outdoor Learning Experience", "outdoor_learning", 5);

  html = "";
  for (i = 0; i < centerConfig.length; i += 1) {
    html += activityCardHtml(centerConfig[i].label, "centers." + centerConfig[i].key, 5);
  }
  centersGrid.innerHTML = html;

  var linksToLearningSelects = document.querySelectorAll('[data-kind="links-to-learning"]');
  for (i = 0; i < linksToLearningSelects.length; i += 1) {
    linksToLearningSelects[i].addEventListener("change", function () {
      var fieldKey = this.dataset.field;
      var textarea = document.querySelector('[data-field="' + fieldKey + '"][data-kind="text"]');
      if (textarea && this.value) {
        textarea.value += (textarea.value ? " " : "") + "Links to learning: " + this.value;
        this.value = "";
      }
    });
  }
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
  if (link.href.indexOf("/api/sync-attachment") !== -1 && authToken) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      fetch(link.href, { headers: { "Authorization": "Bearer " + authToken } })
        .then(function (r) { if (!r.ok) throw new Error(); return r.blob(); })
        .then(function (blob) { window.open(URL.createObjectURL(blob), "_blank"); })
        .catch(function () { alert("Could not open the attachment. Make sure you are signed in."); });
    });
  }
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
  markPlannerDirty();
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
  themeInput.value = "";
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
  themeInput.value = record.theme || "";
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
    theme: themeInput.value.trim(),
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
  var file = new File([blob], attachment.filename || "attachment", { type: attachment.mimeType || blob.type || "application/octet-stream" });
  file = await compressImageIfNeeded(file);
  blob = file;
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
      file = await compressImageIfNeeded(input.files[0]);
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
      file = await compressImageIfNeeded(input.files[0]);
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

async function appendAttachmentFiles(formData) {
  var attachmentInputs = document.querySelectorAll('[data-kind="attachment"]');
  var i;
  var input;
  var file;

  for (i = 0; i < attachmentInputs.length; i += 1) {
    input = attachmentInputs[i];
    if (input.files && input.files[0]) {
      file = await compressImageIfNeeded(input.files[0]);
      formData.append("attachment::" + input.dataset.field, file);
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
  await appendAttachmentFiles(formData);
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
    parts.push(formatIsoToDisplay(plan.weekStart) + " to " + formatIsoToDisplay(plan.weekEnd));
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
  // Use an anchor with the download attribute on every platform. This keeps the
  // teacher on the app instead of replacing the page with the file (the old
  // iPad/iPhone behavior). iOS Safari has supported a[download] since 16.4.
  var url = URL.createObjectURL(blob);
  var link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  setTimeout(function () {
    URL.revokeObjectURL(url);
    document.body.removeChild(link);
  }, 1500);
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

async function gridErrorMessageFromResponse(response) {
  var text;
  try {
    text = await response.text();
  } catch (readError) {
    return "Server error (" + response.status + ").";
  }
  try {
    return JSON.parse(text).error || "Could not generate the 2x2 PDF.";
  } catch (parseError) {
    return "Server error (" + response.status + "): " + text.slice(0, 200);
  }
}

// Keep each upload comfortably under the hosted 4.5 MB request limit. The
// server packs every image in a single request into one multi-page 2x2 PDF, so
// batching by size (not a fixed count) means most folders come out as one file.
var GRID_MAX_REQUEST_BYTES = 4000000;

function batchGridFilesBySize(files) {
  var batches = [];
  var current = [];
  var currentBytes = 0;
  var i;
  var size;
  for (i = 0; i < files.length; i += 1) {
    size = files[i].size || 0;
    if (current.length && currentBytes + size > GRID_MAX_REQUEST_BYTES) {
      batches.push(current);
      current = [];
      currentBytes = 0;
    }
    current.push(files[i]);
    currentBytes += size;
  }
  if (current.length) {
    batches.push(current);
  }
  return batches;
}

function selectedGridLayout() {
  var checked = document.querySelector('input[name="gridLayout"]:checked');
  return checked ? checked.value : "grid";
}

function selectedGridOrientation() {
  var checked = document.querySelector('input[name="gridOrientation"]:checked');
  return checked ? checked.value : "side";
}

function updateGridOrientationVisibility() {
  if (gridOrientationField) {
    gridOrientationField.hidden = selectedGridLayout() !== "two-per-page";
  }
}

async function handleGridGenerate() {
  var folderFiles = Array.prototype.slice.call((gridImageInput && gridImageInput.files) || []);
  var individualFiles = Array.prototype.slice.call((gridImageFilesInput && gridImageFilesInput.files) || []);
  var files = folderFiles.concat(individualFiles);
  var imageFiles = files.filter(isSupportedGridImage).sort(function (a, b) {
    var aName = a.webkitRelativePath || a.name || "";
    var bName = b.webkitRelativePath || b.name || "";
    return aName.localeCompare(bName, undefined, { numeric: true, sensitivity: "base" });
  });
  var layout = selectedGridLayout();
  var orientation = selectedGridOrientation();
  var baseName = layout === "two-per-page" ? "2-per-page" : "2x2";
  var batches;
  var formData;
  var response;
  var blob;
  var i;

  if (!imageFiles.length) {
    setGridStatus("Select a folder with supported image files first.", "error");
    return;
  }

  gridGenerateButton.disabled = true;
  try {
    setGridStatus("Compressing images...");
    for (i = 0; i < imageFiles.length; i += 1) {
      imageFiles[i] = await compressImageIfNeeded(imageFiles[i]);
    }
    batches = batchGridFilesBySize(imageFiles);
    for (i = 0; i < batches.length; i += 1) {
      setGridStatus(
        batches.length > 1
          ? "Creating PDF " + (i + 1) + " of " + batches.length + "..."
          : "Creating " + baseName + ".pdf..."
      );
      formData = new FormData();
      formData.append("layout", layout);
      formData.append("orientation", orientation);
      batches[i].forEach(function (file, index) {
        formData.append("images::" + index, file, file.webkitRelativePath || file.name);
      });
      response = await fetch(apiRoutes.gridPdf, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await gridErrorMessageFromResponse(response));
      }
      blob = await response.blob();
      downloadBlob(blob, batches.length > 1 ? baseName + "-part-" + (i + 1) + ".pdf" : baseName + ".pdf");
    }
    setGridStatus(
      (batches.length > 1
        ? batches.length + " PDF files were created (too many images for one file) with "
        : baseName + ".pdf was created with ") +
        imageFiles.length + " image" + (imageFiles.length === 1 ? "." : "s."),
      "success"
    );
  } catch (error) {
    setGridStatus(error.message || "Could not generate the PDF.", "error");
  } finally {
    gridGenerateButton.disabled = false;
  }
}

function setGridPrintStatus(message, kind) {
  if (!gridPrintStatus) {
    return;
  }
  gridPrintStatus.textContent = message;
  gridPrintStatus.className = "status-text" + (kind ? " " + kind : "");
}

function renderGridPrintCells() {
  if (!gridPrintCellsContainer) {
    return;
  }
  gridPrintCellsContainer.innerHTML = "";
  var i;
  var cell;
  var input;
  var img;
  var placeholder;
  for (i = 0; i < GRID_PRINT_SLOT_COUNT; i += 1) {
    cell = document.createElement("div");
    cell.className = "grid-print-cell" + (gridPrintSlots[i] ? " filled" : "");

    input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.dataset.slotIndex = String(i);
    cell.appendChild(input);

    if (gridPrintSlots[i]) {
      img = document.createElement("img");
      img.src = URL.createObjectURL(gridPrintSlots[i]);
      img.alt = "Photo " + (i + 1);
      cell.appendChild(img);
    } else {
      placeholder = document.createElement("span");
      placeholder.textContent = "+ Add photo";
      cell.appendChild(placeholder);
    }

    gridPrintCellsContainer.appendChild(cell);
  }
}

function handleGridPrintCellChange(event) {
  var input = event.target;
  var file;
  var index;
  if (!input || input.type !== "file" || !input.dataset || input.dataset.slotIndex === undefined) {
    return;
  }
  index = Number(input.dataset.slotIndex);
  file = input.files && input.files[0];
  if (!file) {
    return;
  }
  if (!isSupportedGridImage(file)) {
    setGridPrintStatus("That file type isn't supported.", "error");
    return;
  }
  gridPrintSlots[index] = file;
  renderGridPrintCells();
}

function handleGridPrintClear() {
  gridPrintSlots = new Array(GRID_PRINT_SLOT_COUNT).fill(null);
  renderGridPrintCells();
  setGridPrintStatus("Add up to 12 photos, then generate grid-print.pdf.");
}

async function handleGridPrintGenerate() {
  var formData;
  var response;
  var blob;
  var i;
  var hasPhoto = gridPrintSlots.some(function (file) {
    return !!file;
  });

  if (!hasPhoto) {
    setGridPrintStatus("Add at least one photo first.", "error");
    return;
  }

  gridPrintGenerateButton.disabled = true;
  try {
    setGridPrintStatus("Compressing photos...");
    for (i = 0; i < GRID_PRINT_SLOT_COUNT; i += 1) {
      if (gridPrintSlots[i]) {
        // 12 slots must fit Vercel's 4.5MB request limit, so budget ~300KB each.
        gridPrintSlots[i] = await compressImageIfNeeded(gridPrintSlots[i], 300 * 1024);
      }
    }
    setGridPrintStatus("Creating grid-print.pdf...");
    formData = new FormData();
    for (i = 0; i < GRID_PRINT_SLOT_COUNT; i += 1) {
      if (gridPrintSlots[i]) {
        formData.append("slot::" + i, gridPrintSlots[i], gridPrintSlots[i].name);
      }
    }
    response = await fetch(apiRoutes.gridPrintPdf, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(await gridErrorMessageFromResponse(response));
    }
    blob = await response.blob();
    downloadBlob(blob, "grid-print.pdf");
    setGridPrintStatus("grid-print.pdf was created.", "success");
  } catch (error) {
    setGridPrintStatus(error.message || "Could not generate the PDF.", "error");
  } finally {
    gridPrintGenerateButton.disabled = false;
  }
}

function initializeGridPrint() {
  renderGridPrintCells();
  if (gridPrintCellsContainer) {
    gridPrintCellsContainer.addEventListener("change", handleGridPrintCellChange);
  }
  if (gridPrintGenerateButton) {
    gridPrintGenerateButton.addEventListener("click", handleGridPrintGenerate);
  }
  if (gridPrintClearButton) {
    gridPrintClearButton.addEventListener("click", handleGridPrintClear);
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

function savedWeekMessage(cloudResult) {
  if (authToken && authUser) {
    if (cloudResult) {
      return "Week saved on this device and synced to your account.";
    }
    return "Week saved on this device. Cloud sync didn't finish - check your internet connection, then save again.";
  }
  return "Week saved on this device. Sign in to also back it up to your account.";
}

async function handleSavePlan() {
  var payload;
  var attachments;
  var record;
  var response;
  var data;
  var key;
  var cloudResult;
  savePlanButton.disabled = true;
  setPlannerStatus("Saving this week...");
  try {
    payload = plannerPayload();
    if (selectedAttachmentByteTotal() <= maxServerSaveUploadBytes) {
      attachments = await collectAttachmentsForStorage();
      try {
        response = await postMultipart(apiRoutes.plannerSave, payload);
        data = await response.json();
        if (response.ok && data.plan) {
          if (data.plan.attachments) {
            for (key in attachments) {
              if (Object.prototype.hasOwnProperty.call(attachments, key) && attachments[key].dataUrl) {
                if (data.plan.attachments[key] && !data.plan.attachments[key].dataUrl) {
                  data.plan.attachments[key].dataUrl = attachments[key].dataUrl;
                }
              }
            }
          } else {
            data.plan.attachments = attachments;
          }
          await savePlanToIndexedDb(data.plan);
          applyPlannerRecord(data.plan);
          cloudResult = await syncPlanToCloud(data.plan);
          plannerDirty = false;
          setPlannerStatus(savedWeekMessage(cloudResult), "success");
          return;
        }
      } catch (serverError) {
        // Fall back to browser storage if the hosted backend rejects or times out.
      }
    }

    if (!attachments) {
      attachments = await collectAttachmentsForStorage();
    }
    record = JSON.parse(JSON.stringify(payload));
    record.attachments = attachments;
    await savePlanToIndexedDb(record);
    applyPlannerRecord(record);
    cloudResult = await syncPlanToCloud(record);
    plannerDirty = false;
    setPlannerStatus(savedWeekMessage(cloudResult), "success");
    refreshSavedWeeksDropdown();
  } catch (error) {
    setPlannerStatus(error.message || "Could not save the planner.", "error");
  } finally {
    savePlanButton.disabled = false;
  }
}

function selectedWeekLookup() {
  return {
    year: selectedYear(),
    month: Number(monthSelect.value),
    weekNumber: Number(weekSelect.value),
  };
}

// Returns true (loaded a saved week), false (blank week), or "stale" when a
// newer call to this function started before this one finished - the newer
// call owns the form now, so this one must not overwrite it.
async function loadSelectedWeekIntoForm() {
  weekLoadSerial += 1;
  var serial = weekLoadSerial;
  function stillCurrent() {
    return serial === weekLoadSerial;
  }
  var lookup = selectedWeekLookup();
  var response;
  var serverData;
  var data;
  var cloudData;

  resetPlannerForm();

  // Try cloud first if signed in
  if (authToken && authUser) {
    cloudData = await loadPlanFromCloud(lookup.year, lookup.month, lookup.weekNumber);
    if (!stillCurrent()) {
      return "stale";
    }
    if (cloudData) {
      applyPlannerRecord(cloudData);
      await savePlanToIndexedDb(cloudData);
      return true;
    }
  }

  // Then try server
  try {
    response = await postJson(apiRoutes.plannerLoad, lookup);
    serverData = await response.json();
    if (!stillCurrent()) {
      return "stale";
    }
    if (response.ok && serverData.plan) {
      applyPlannerRecord(serverData.plan);
      await savePlanToIndexedDb(serverData.plan);
      return true;
    }
  } catch (serverError) {
    // Fall back to browser storage when the backend has no saved copy.
  }

  // Finally try local IndexedDB
  data = await loadPlanFromIndexedDb(lookup.year, lookup.month, lookup.weekNumber);
  if (!stillCurrent()) {
    return "stale";
  }
  if (!data) {
    return false;
  }
  applyPlannerRecord(data);
  return true;
}

async function handleSelectedWeekChanged() {
  renderWeekDays();
  setPlannerStatus("Loading selected week...");
  try {
    var result = await loadSelectedWeekIntoForm();
    if (result === "stale") {
      return;
    }
    plannerDirty = false;
    syncPreviousWeekSelectors();
    setPlannerStatus(result ? "Saved week loaded." : "New blank week ready.", result ? "success" : "");
  } catch (error) {
    plannerDirty = false;
    syncPreviousWeekSelectors();
    setPlannerStatus(error.message || "Could not load this week.", "error");
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

var activityDateInput = document.querySelector("#activityDate");
var addSkillFieldButton = document.querySelector("#addSkillFieldButton");
var addLinkFieldButton = document.querySelector("#addLinkFieldButton");
var activityFieldsContainer = document.querySelector("#activityFieldsContainer");
var skillFieldsContainer = document.querySelector("#skillFieldsContainer");
var linkFieldsContainer = document.querySelector("#linkFieldsContainer");
var loadActivityButton = document.querySelector("#loadActivityButton");
var saveActivityButton = document.querySelector("#saveActivityButton");
var applyActivityTemplateButton = document.querySelector("#applyActivityTemplateButton");
var downloadActivityDatabaseButton = document.querySelector("#downloadActivityDatabaseButton");
var activityStatus = document.querySelector("#activityStatus");

var activityDatabaseName = "activityDescriptorDb";
var activityDatabaseVersion = 1;
var activityStoreName = "activities";
var currentActivityData = null;

var defaultLinks = [
  "Language and Literacy",
  "Wellness",
  "Creative Expression",
  "Mathematics",
  "Social Emotional",
];

function setActivityStatus(message, kind) {
  if (!activityStatus) {
    return;
  }
  activityStatus.textContent = message;
  activityStatus.className = "status-text" + (kind ? " " + kind : "");
}

function initActivityDatabase() {
  return new Promise(function (resolve, reject) {
    var request = indexedDB.open(activityDatabaseName, activityDatabaseVersion);
    request.onerror = function () {
      reject(new Error("Could not open activity database."));
    };
    request.onsuccess = function () {
      resolve(request.result);
    };
    request.onupgradeneeded = function (event) {
      var db = event.target.result;
      if (!db.objectStoreNames.contains(activityStoreName)) {
        db.createObjectStore(activityStoreName, { keyPath: "date" });
      }
    };
  });
}

function saveActivityToIndexedDb(record) {
  return initActivityDatabase().then(function (db) {
    return new Promise(function (resolve, reject) {
      var transaction = db.transaction([activityStoreName], "readwrite");
      var store = transaction.objectStore(activityStoreName);
      var request = store.put(record);
      request.onerror = function () {
        reject(new Error("Could not save activity."));
      };
      request.onsuccess = function () {
        resolve(record);
      };
    });
  });
}

function loadActivityFromIndexedDb(date) {
  return initActivityDatabase().then(function (db) {
    return new Promise(function (resolve, reject) {
      var transaction = db.transaction([activityStoreName], "readonly");
      var store = transaction.objectStore(activityStoreName);
      var request = store.get(date);
      request.onerror = function () {
        reject(new Error("Could not load activity."));
      };
      request.onsuccess = function () {
        resolve(request.result || null);
      };
    });
  });
}

function loadAllActivitiesFromIndexedDb() {
  return initActivityDatabase().then(function (db) {
    return new Promise(function (resolve, reject) {
      var transaction = db.transaction([activityStoreName], "readonly");
      var store = transaction.objectStore(activityStoreName);
      var request = store.getAll();
      request.onerror = function () {
        reject(new Error("Could not load activities."));
      };
      request.onsuccess = function () {
        resolve(request.result || []);
      };
    });
  });
}

function activityPayload() {
  var date = activityDateInput.value;
  var activities = [];
  var skills = [];
  var links = [];
  var i;
  var inputs;

  inputs = activityFieldsContainer.querySelectorAll("textarea");
  for (i = 0; i < inputs.length; i += 1) {
    activities.push(inputs[i].value.trim());
  }

  inputs = skillFieldsContainer.querySelectorAll("textarea");
  for (i = 0; i < inputs.length; i += 1) {
    skills.push(inputs[i].value.trim());
  }

  inputs = linkFieldsContainer.querySelectorAll("textarea");
  for (i = 0; i < inputs.length; i += 1) {
    links.push(inputs[i].value.trim());
  }

  return {
    date: date,
    activities: activities,
    skills: skills,
    links: links,
  };
}

function renderSectionFields(container, items, sectionLabel) {
  container.innerHTML = "";
  var i;
  for (i = 0; i < items.length; i += 1) {
    addFieldToContainer(container, items[i], i, sectionLabel);
  }
  if (items.length === 0) {
    addFieldToContainer(container, "", 0, sectionLabel);
  }
}

function addFieldToContainer(container, value, index, sectionLabel) {
  var fieldItem = document.createElement("div");
  fieldItem.className = "activity-field-item";
  fieldItem.innerHTML =
    '<label class="field"><span>' + sectionLabel + " " + (index + 1) + '</span>' +
    '<textarea placeholder="Enter text..." data-field-index="' + index + '"></textarea></label>' +
    '<button class="activity-field-remove" type="button" data-field-index="' + index + '">−</button>';

  fieldItem.querySelector("textarea").value = value;

  fieldItem.querySelector(".activity-field-remove").addEventListener("click", function (e) {
    e.preventDefault();
    removeFieldFromContainer(container, index, sectionLabel);
  });

  container.appendChild(fieldItem);
}

function removeFieldFromContainer(container, index, sectionLabel) {
  var inputs = container.querySelectorAll("textarea");
  var newItems = [];
  var i;
  for (i = 0; i < inputs.length; i += 1) {
    if (i !== index) {
      newItems.push(inputs[i].value.trim());
    }
  }
  renderSectionFields(container, newItems, sectionLabel);
  markActivityDirty();
}

function addFieldToSection(container, sectionLabel) {
  var inputs = container.querySelectorAll("textarea");
  var items = [];
  var i;
  for (i = 0; i < inputs.length; i += 1) {
    items.push(inputs[i].value.trim());
  }
  items.push("");
  renderSectionFields(container, items, sectionLabel);
  markActivityDirty();
}

function resetActivityForm() {
  activityDateInput.value = "";
  renderSectionFields(activityFieldsContainer, [], "Activity");
  renderSectionFields(skillFieldsContainer, [], "Skill");
  renderSectionFields(linkFieldsContainer, defaultLinks.slice(), "Link");
  currentActivityData = null;
}

async function loadSelectedActivityIntoForm() {
  var date = activityDateInput.value;
  if (!date) {
    resetActivityForm();
    return false;
  }
  var record = await loadActivityFromIndexedDb(date);
  if (!record && authToken && authUser) {
    try {
      var cloudRecord = await loadActivityFromCloud(date);
      if (cloudRecord) {
        await saveActivityToIndexedDb(cloudRecord);
        record = cloudRecord;
      }
    } catch (e) {
      // cloud load failed, continue with local miss
    }
  }
  if (!record) {
    renderSectionFields(activityFieldsContainer, [], "Activity");
    renderSectionFields(skillFieldsContainer, [], "Skill");
    renderSectionFields(linkFieldsContainer, defaultLinks.slice(), "Link");
    return false;
  }
  currentActivityData = record;
  renderSectionFields(activityFieldsContainer, record.activities || [], "Activity");
  renderSectionFields(skillFieldsContainer, record.skills || [], "Skill");
  renderSectionFields(linkFieldsContainer, record.links && record.links.length ? record.links : defaultLinks.slice(), "Link");
  return true;
}

async function handleLoadActivity() {
  if (!confirmDiscardChanges(activityDirty)) {
    return;
  }
  loadActivityButton.disabled = true;
  setActivityStatus("Loading saved activity...");
  try {
    if (!(await loadSelectedActivityIntoForm())) {
      activityDirty = false;
      setActivityStatus("No saved activity was found for this date.");
      return;
    }
    activityDirty = false;
    setActivityStatus("Activity loaded.", "success");
  } catch (error) {
    setActivityStatus(error.message || "Could not load the activity.", "error");
  } finally {
    loadActivityButton.disabled = false;
  }
}

async function syncActivityToCloud(record) {
  await ensureFreshToken();
  if (!authToken || !authUser) {
    return null;
  }
  try {
    var response = await fetch("/api/activity-descriptor-sync-save", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
      body: JSON.stringify(record),
    });
    var data = await response.json();
    if (response.ok && data.activity) {
      return data.activity;
    }
  } catch (e) {
    // silent
  }
  return null;
}

async function loadActivityFromCloud(date) {
  await ensureFreshToken();
  if (!authToken || !authUser) {
    return null;
  }
  try {
    var response = await fetch("/api/activity-descriptor-sync-load", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + authToken },
      body: JSON.stringify({ date: date }),
    });
    var data = await response.json();
    if (response.ok && data.activity) {
      return data.activity;
    }
  } catch (e) {
    // silent
  }
  return null;
}

async function syncAllLocalActivitiesToCloud() {
  if (!authToken || !authUser) {
    return;
  }
  try {
    var localActivities = await loadAllActivitiesFromIndexedDb();
    if (!localActivities || !localActivities.length) {
      return;
    }
    for (var i = 0; i < localActivities.length; i += 1) {
      await syncActivityToCloud(localActivities[i]);
    }
  } catch (e) {
    // silent
  }
}

async function handleSaveActivity() {
  var payload;
  var record;
  saveActivityButton.disabled = true;
  setActivityStatus("Saving this activity...");
  try {
    payload = activityPayload();
    if (!payload.date) {
      throw new Error("Please enter a date.");
    }
    record = JSON.parse(JSON.stringify(payload));
    await saveActivityToIndexedDb(record);
    currentActivityData = record;
    syncActivityToCloud(record);
    activityDirty = false;
    setActivityStatus("Activity saved." + (authToken && authUser ? " Syncing to cloud..." : ""), "success");
  } catch (error) {
    setActivityStatus(error.message || "Could not save the activity.", "error");
  } finally {
    saveActivityButton.disabled = false;
  }
}

async function handleApplyActivityTemplate() {
  var response;
  var blob;
  var errorData;
  var filename;
  applyActivityTemplateButton.disabled = true;
  setActivityStatus("Applying activity data to template...");
  try {
    response = await fetch("/api/activity-descriptor-export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(activityPayload()),
    });
    if (!response.ok) {
      errorData = await response.json();
      throw new Error(errorData.error || "Could not apply the data to the template.");
    }
    blob = await response.blob();
    filename = suggestedFilenameFromHeaders(response);
    downloadBlob(blob, filename);
    setActivityStatus("Activity descriptor template created.", "success");
  } catch (error) {
    setActivityStatus(error.message || "Could not apply the data to the template.", "error");
  } finally {
    applyActivityTemplateButton.disabled = false;
  }
}

async function handleDownloadActivityDatabase() {
  downloadActivityDatabaseButton.disabled = true;
  setActivityStatus("Exporting all activities...");
  try {
    var activities = await loadAllActivitiesFromIndexedDb();
    if (!activities || !activities.length) {
      setActivityStatus("No saved activities to export.");
      return;
    }
    var jsonStr = JSON.stringify(activities, null, 2);
    var blob = new Blob([jsonStr], { type: "application/json" });
    downloadBlob(blob, "activity_descriptor_database.json");
    setActivityStatus("Activity database exported.", "success");
  } catch (error) {
    setActivityStatus(error.message || "Could not export the database.", "error");
  } finally {
    downloadActivityDatabaseButton.disabled = false;
  }
}

function initializeActivityDescriptor() {
  if (!activityDateInput) {
    return;
  }
  resetActivityForm();

  if (addSkillFieldButton) {
    addSkillFieldButton.addEventListener("click", function (e) {
      e.preventDefault();
      addFieldToSection(skillFieldsContainer, "Skill");
    });
  }

  if (addLinkFieldButton) {
    addLinkFieldButton.addEventListener("click", function (e) {
      e.preventDefault();
      addFieldToSection(linkFieldsContainer, "Link");
    });
  }

  if (loadActivityButton) {
    loadActivityButton.addEventListener("click", handleLoadActivity);
  }

  if (saveActivityButton) {
    saveActivityButton.addEventListener("click", handleSaveActivity);
  }

  if (applyActivityTemplateButton) {
    applyActivityTemplateButton.addEventListener("click", handleApplyActivityTemplate);
  }

  if (downloadActivityDatabaseButton) {
    downloadActivityDatabaseButton.addEventListener("click", handleDownloadActivityDatabase);
  }

  var previousActivityDateValue = activityDateInput.value;
  activityDateInput.addEventListener("change", function () {
    if (!confirmDiscardChanges(activityDirty, function () { activityDateInput.value = previousActivityDateValue; })) {
      return;
    }
    previousActivityDateValue = activityDateInput.value;
    loadSelectedActivityIntoForm().then(function () {
      activityDirty = false;
    });
  });

  var activityDescriptorApp = document.querySelector("#activityDescriptorApp");
  if (activityDescriptorApp) {
    activityDescriptorApp.addEventListener("input", function (event) {
      if (event.target !== activityDateInput) {
        markActivityDirty();
      }
    });
    activityDescriptorApp.addEventListener("change", function (event) {
      if (event.target !== activityDateInput) {
        markActivityDirty();
      }
    });
  }
}

function initializePlanner() {
  initializeAppTabs();
  initializeActivityDescriptor();
  checkAuth();
  renderYearOptions();
  currentYearLabel.textContent = String(selectedYear());
  renderMonthOptions();
  renderWeekOptions();
  renderWeekDays();
  renderSectionGrids();
  document.addEventListener("change", handleAttachmentInputChange);
  document.addEventListener("click", handleAttachmentRemoveClick);

  var plannerAppEl = document.querySelector("#plannerApp");
  if (plannerAppEl) {
    plannerAppEl.addEventListener("input", function (event) {
      if (event.target !== yearSelect && event.target !== monthSelect && event.target !== weekSelect) {
        markPlannerDirty();
      }
    });
    plannerAppEl.addEventListener("change", function (event) {
      if (event.target !== yearSelect && event.target !== monthSelect && event.target !== weekSelect) {
        markPlannerDirty();
      }
    });
  }

  if (gridGenerateButton) {
    gridGenerateButton.addEventListener("click", handleGridGenerate);
  }
  document.querySelectorAll('input[name="gridLayout"]').forEach(function (radio) {
    radio.addEventListener("change", updateGridOrientationVisibility);
  });
  updateGridOrientationVisibility();

  initializeGridPrint();

  if (authButton) {
    authButton.addEventListener("click", openAuthModal);
  }
  if (closeAuthModalButton) {
    closeAuthModalButton.addEventListener("click", closeAuthModal);
  }
  if (authSignInButton) {
    authSignInButton.addEventListener("click", handleAuthSignIn);
  }
  if (authSignUpButton) {
    authSignUpButton.addEventListener("click", handleAuthSignUp);
  }
  if (authSignOutButton) {
    authSignOutButton.addEventListener("click", handleAuthSignOut);
  }
  if (authModal) {
    authModal.addEventListener("click", function (event) {
      if (event.target === authModal) {
        closeAuthModal();
      }
    });
  }

  syncPreviousWeekSelectors();

  yearSelect.addEventListener("change", function () {
    if (!confirmDiscardChanges(plannerDirty, function () { yearSelect.value = previousYearValue; })) {
      return;
    }
    renderWeekOptions();
    handleSelectedWeekChanged();
  });

  monthSelect.addEventListener("change", function () {
    if (!confirmDiscardChanges(plannerDirty, function () { monthSelect.value = previousMonthValue; })) {
      return;
    }
    renderWeekOptions();
    handleSelectedWeekChanged();
  });

  weekSelect.addEventListener("change", function () {
    if (!confirmDiscardChanges(plannerDirty, function () { weekSelect.value = previousWeekValue; })) {
      return;
    }
    handleSelectedWeekChanged();
  });
  if (savedWeeksSelect) {
    savedWeeksSelect.addEventListener("change", handleSavedWeekPicked);
  }
  refreshSavedWeeksDropdown();
  savePlanButton.addEventListener("click", handleSavePlan);
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
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") {
      return;
    }
    if (authModal && !authModal.hidden) {
      closeAuthModal();
    } else if (databaseModal && !databaseModal.hidden) {
      closeDatabaseModal();
    }
  });
  handleSelectedWeekChanged();
}

initializePlanner();
