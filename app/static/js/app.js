const statusBox = document.getElementById("page-status");
const appVersion = document.documentElement.dataset.appVersion || "dev";
window.__HCOPILOT_APP_VERSION__ = appVersion;

function setStatus(message, tone = "success") {
  if (!statusBox) return;
  const palette =
    tone === "error"
      ? ["bg-[#fff1ef]", "text-[#9f403d]"]
      : ["bg-[#eef8ef]", "text-[#305c37]"];
  statusBox.className = `mb-6 rounded-2xl px-4 py-3 text-sm font-medium ${palette.join(" ")}`;
  statusBox.textContent = message;
  statusBox.classList.remove("hidden");
}

function readErrorMessage(response, data, fallbackMessage) {
  if (data && typeof data.detail === "string" && data.detail.trim()) {
    return data.detail;
  }
  if (response.status === 422) {
    return "提交内容格式不正确，请检查输入项。";
  }
  if (response.status === 404) {
    return "目标数据不存在或已被删除。";
  }
  if (response.status >= 500) {
    return "服务器处理失败，请稍后重试。";
  }
  return fallbackMessage;
}

function splitListInput(value) {
  return (value || "")
    .replaceAll("，", ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeBloodPressureInput(value) {
  return String(value || "")
    .replaceAll("／", "/")
    .replace(/\s+/g, "");
}

function toPayload(form) {
  const payload = Object.fromEntries(new FormData(form).entries());
  if (form.dataset.apiForm === "records") {
    const selected = form.querySelector("[data-unit-select] option:checked");
    payload.unit = selected ? selected.dataset.unit || "" : "";
  }
  if (form.dataset.apiForm === "profile") {
    payload.allergies = splitListInput(payload.allergies);
    payload.medical_history = splitListInput(payload.medical_history);
    payload.long_term_medications = splitListInput(payload.long_term_medications);
  }
  return payload;
}

function validateForm(form, payload) {
  if (form.dataset.apiForm !== "records") {
    return null;
  }
  const recordType = String(payload.record_type || "").trim();
  if (!String(payload.value || "").trim()) {
    return "请填写记录数值。";
  }

  const rawValue = String(payload.value || "").trim();
  if (recordType === "blood_pressure") {
    const normalizedBloodPressure = normalizeBloodPressureInput(rawValue);
    payload.value = normalizedBloodPressure;
    const bloodPressurePattern = /^\d{2,3}\/\d{2,3}$/;
    if (!bloodPressurePattern.test(normalizedBloodPressure)) {
      return "血压请按“舒张压/收缩压”格式输入，例如 80/120。";
    }
    const [diastolicStr, systolicStr] = normalizedBloodPressure.split("/");
    const diastolic = Number(diastolicStr);
    const systolic = Number(systolicStr);
    if (!(diastolic >= 40 && diastolic <= 150 && systolic >= 70 && systolic <= 260 && diastolic < systolic)) {
      return "血压数值异常，请按“舒张压/收缩压”输入合理范围。";
    }
  } else {
    const numberValue = Number(rawValue);
    if (Number.isNaN(numberValue)) {
      return "记录数值必须是数字。";
    }
    const rangeMap = {
      temperature: { label: "体温", low: 30, high: 45, unit: "C" },
      blood_glucose: { label: "血糖", low: 1.5, high: 35, unit: "mmol/L" },
      heart_rate: { label: "心率", low: 25, high: 260, unit: "bpm" },
      weight: { label: "体重", low: 2, high: 500, unit: "kg" },
      spo2: { label: "血氧", low: 50, high: 100, unit: "%" },
    };
    const range = rangeMap[recordType];
    if (range && (numberValue < range.low || numberValue > range.high)) {
      return `${range.label}超出合理范围 ${range.low}-${range.high}${range.unit}`;
    }
  }
  const recordedAt = String(payload.recorded_at || "").trim();
  if (recordedAt && !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(recordedAt)) {
    return "记录时间格式应为 YYYY-MM-DDTHH:MM 或 YYYY-MM-DDTHH:MM:SS。";
  }
  if (recordedAt) {
    const recordTime = new Date(recordedAt);
    if (Number.isNaN(recordTime.getTime())) {
      return "记录时间无效，请检查输入。";
    }
    if (recordTime.getTime() > Date.now() + 5 * 60 * 1000) {
      return "记录时间不能晚于当前时间。";
    }
  }
  return null;
}

function renderProfileList(container, items, pillMode = false) {
  if (!container) return;
  container.innerHTML = "";
  if (!items || items.length === 0) {
    const empty = document.createElement("span");
    empty.className = "text-sm text-[#5c605a]";
    empty.textContent = "暂无记录";
    container.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const el = document.createElement("span");
    if (pillMode) {
      el.className = "rounded-full bg-white px-4 py-2 font-semibold text-[#9f403d]";
    } else {
      el.className = "block rounded-2xl bg-[#f4f4ef] px-4 py-3";
    }
    el.textContent = item;
    container.appendChild(el);
  });
}

function applyProfileUpdate(payload, data) {
  const basicInfo = data && data.basic_info ? data.basic_info : {};
  const setText = (selector, value) => {
    const node = document.querySelector(selector);
    if (node && value !== undefined && value !== null) {
      node.textContent = String(value);
    }
  };
  setText("[data-profile-name]", basicInfo.name ?? payload.display_name);
  setText("[data-profile-age]", basicInfo.age ?? payload.age_range);
  setText("[data-profile-height]", basicInfo.height_cm ?? payload.height_cm);
  setText("[data-profile-weight]", basicInfo.weight_kg ?? payload.weight_kg);

  const allergies = Array.isArray(data?.allergies) ? data.allergies : payload.allergies || [];
  const medicalHistory = Array.isArray(data?.medical_history)
    ? data.medical_history
    : payload.medical_history || [];
  renderProfileList(document.querySelector("[data-profile-allergies-list]"), allergies, true);
  renderProfileList(document.querySelector("[data-profile-history-list]"), medicalHistory, false);
}

async function submitApiForm(form) {
  const submitButton = form.querySelector("button[type='submit'], button:not([type])");
  const originalLabel = submitButton ? submitButton.textContent : "";
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.textContent = "提交中...";
  }

  try {
    const payload = toPayload(form);
    const validationError = validateForm(form, payload);
    if (validationError) {
      throw new Error(validationError);
    }
    const response = await fetch(form.action, {
      method: form.method || "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(readErrorMessage(response, data, "提交失败"));
    }
    if (form.dataset.apiForm === "profile") {
      applyProfileUpdate(payload, data);
      setStatus("档案已更新。");
      const profileView = document.querySelector("[data-profile-view]");
      const profileEdit = document.querySelector("[data-profile-edit]");
      const profileEditButton = document.querySelector("[data-profile-edit-toggle]");
      if (profileView && profileEdit && profileEditButton) {
        profileEdit.classList.add("hidden");
        profileView.classList.remove("hidden");
        profileEditButton.classList.remove("hidden");
      }
      return;
    }
    setStatus("已成功保存。");
    window.setTimeout(() => {
      window.location.reload();
    }, 350);
  } catch (error) {
    if (error instanceof TypeError) {
      setStatus("网络连接异常，请检查后重试。", "error");
    } else {
      setStatus(error.message || "提交失败", "error");
    }
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.textContent = originalLabel;
    }
  }
}

document.querySelectorAll("[data-unit-select]").forEach((select) => {
  const updateUnitDisplay = () => {
    const selected = select.options[select.selectedIndex];
    const display = select.form ? select.form.querySelector("[data-unit-display]") : null;
    const input = select.form ? select.form.querySelector("[data-record-value-input]") : null;
    if (display) {
      display.textContent = selected.dataset.unit || "";
    }
    if (input) {
      input.placeholder = selected.dataset.placeholder || "请输入数值";
    }
  };
  select.addEventListener("change", updateUnitDisplay);
  updateUnitDisplay();
});

document.querySelectorAll("form[data-api-form]").forEach((form) => {
  if (form.dataset.apiForm === "copilot") return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitApiForm(form);
  });
});

function createChatMessageElement(role, text = "") {
  const wrapper = document.createElement("div");
  wrapper.dataset.chatMessage = "";
  wrapper.dataset.role = role;
  wrapper.className = role === "assistant" ? "max-w-[85%]" : "ml-auto max-w-[85%]";

  const bubble = document.createElement("div");
  bubble.className =
    role === "assistant"
      ? "rounded-[24px] bg-[#f4f4ef] px-6 py-5 text-[#2f342e] shadow-[0_10px_30px_rgba(31,48,36,0.06)]"
      : "rounded-[24px] bg-[#3c6842] px-6 py-5 text-[#e4ffe2] shadow-[0_10px_30px_rgba(31,48,36,0.08)]";

  const content = document.createElement("p");
  content.className = "whitespace-pre-wrap leading-7";
  content.textContent = text;
  bubble.appendChild(content);
  wrapper.appendChild(bubble);

  return { wrapper, bubble, content };
}

function createAssistantStreamElement() {
  const wrapper = document.createElement("div");
  wrapper.className = "max-w-[88%]";
  wrapper.dataset.chatMessage = "";
  wrapper.dataset.role = "assistant";

  const processWrap = document.createElement("div");
  processWrap.className = "mb-3 rounded-2xl border border-[#dbe7dc] bg-[#f7faf6] px-4 py-3";

  const processDetails = document.createElement("details");
  processDetails.className = "group";
  processDetails.dataset.processDetails = "";

  const processSummary = document.createElement("summary");
  processSummary.className = "cursor-pointer list-none text-xs font-medium tracking-[0.02em] text-[#5c605a]";
  processSummary.dataset.processSummary = "";
  processSummary.textContent = "已提交，正在准备回复";

  const processLog = document.createElement("div");
  processLog.className = "mt-3 space-y-2 text-xs text-[#5c605a]";
  processLog.dataset.processLog = "";

  processDetails.appendChild(processSummary);
  processDetails.appendChild(processLog);
  processWrap.appendChild(processDetails);

  const bubble = document.createElement("div");
  bubble.className = "rounded-[24px] bg-[#f4f4ef] px-6 py-5 text-[#2f342e] shadow-[0_10px_30px_rgba(31,48,36,0.06)]";

  const content = document.createElement("p");
  content.className = "whitespace-pre-wrap leading-7";
  content.textContent = "";

  bubble.appendChild(content);
  wrapper.appendChild(processWrap);
  wrapper.appendChild(bubble);

  return { wrapper, content, processSummary, processLog, processDetails };
}

function appendProcessLog(processLog, processSummary, processDetails, text) {
  if (!processLog || !text) return;
  const row = document.createElement("p");
  row.textContent = text;
  processLog.appendChild(row);
  processSummary.textContent = text;
  if (processLog.childElementCount > 1) {
    processDetails.classList.remove("hidden");
  }
}

function scrollChatFeed(feed) {
  if (!feed) return;
  feed.scrollIntoView({ block: "end", behavior: "smooth" });
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function truncateText(text, size) {
  const normalized = String(text || "").trim().replace(/\s+/g, " ");
  if (!normalized) return "";
  return normalized.length > size ? `${normalized.slice(0, size)}...` : normalized;
}

function resolveCopilotFinalText({ finalAnswer, hasError }) {
  if (finalAnswer) return finalAnswer;
  if (hasError) return "生成失败，请稍后重试。";
  return "暂时没有生成结果，请稍后再试。";
}

function createReminderEmptyState() {
  const template = document.querySelector("[data-reminder-empty-state-template]");
  const templateNode = template?.content?.firstElementChild;
  if (templateNode) {
    return templateNode.cloneNode(true);
  }
  const emptyState = document.createElement("p");
  emptyState.className = "text-sm text-[#5c605a]";
  emptyState.dataset.reminderEmptyState = "";
  emptyState.textContent = "还没有提醒，先创建一个吧。";
  return emptyState;
}

function refreshReminderEmptyState(list, createEmptyState = createReminderEmptyState) {
  if (!list) return;
  const cards = list.querySelectorAll("[data-reminder-card]");
  const emptyState = list.querySelector("[data-reminder-empty-state]");
  if (cards.length === 0) {
    if (!emptyState) {
      list.appendChild(createEmptyState());
    }
    return;
  }
  if (emptyState) {
    emptyState.remove();
  }
}

function handleReminderDeleteSuccess({ card, list, createEmptyState = createReminderEmptyState }) {
  if (card) {
    card.remove();
  }
  refreshReminderEmptyState(list, createEmptyState);
}

function handleReminderDeleteFailure({ button }) {
  if (button) {
    button.disabled = false;
  }
}

function formatSessionTime(value) {
  if (!value) {
    return new Date().toISOString().slice(0, 19);
  }
  return value;
}

function upsertSessionCard(sessionId, userId, userMessage, assistantMessage) {
  const list = document.querySelector("[data-session-list]");
  if (!list || !sessionId) return;
  let card = list.querySelector(`[data-session-card][data-session-id="${CSS.escape(sessionId)}"]`);
  if (!card) {
    card = document.createElement("div");
    card.dataset.sessionCard = "";
    card.dataset.sessionId = sessionId;
    card.className = "rounded-2xl bg-[#eef8ef] px-4 py-3";
    card.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <a href="/copilot?user_id=${encodeURIComponent(userId)}&session_id=${encodeURIComponent(sessionId)}" class="block min-w-0 flex-1" data-session-link>
          <p class="font-semibold text-[#2f342e]" data-session-title></p>
          <p class="mt-1 text-xs text-[#5c605a]" data-session-time></p>
          <p class="mt-1 text-xs text-[#5c605a]" data-session-preview></p>
        </a>
        <button type="button" class="shrink-0 rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#9f403d]" data-delete-session data-user-id="${userId}" data-session-id="${sessionId}">删除</button>
      </div>
    `;
  }
  card.classList.remove("bg-[#f4f4ef]");
  card.classList.add("bg-[#eef8ef]");
  const title = card.querySelector("[data-session-title]");
  const time = card.querySelector("[data-session-time]");
  let preview = card.querySelector("[data-session-preview]");
  if (!preview) {
    preview = document.createElement("p");
    preview.className = "mt-1 text-xs text-[#5c605a]";
    preview.dataset.sessionPreview = "";
    card.querySelector("[data-session-link]")?.appendChild(preview);
  }
  if (title) title.textContent = truncateText(userMessage || assistantMessage, 16) || "未命名会话";
  if (time) time.textContent = formatSessionTime();
  if (preview) preview.textContent = truncateText(assistantMessage || userMessage, 28);
  list.prepend(card);
  bindDeleteSessionButtons(card.querySelectorAll("[data-delete-session]"));
}

function setCopilotSubmitting(form, submitting) {
  const submitButton = form.querySelector("button[type='submit'], button:not([type])");
  const textarea = form.querySelector("textarea[name='message']");
  if (submitButton) {
    submitButton.disabled = submitting;
    submitButton.textContent = submitting ? "生成中" : "发送消息";
  }
  if (textarea) {
    textarea.disabled = submitting;
  }
}

function parseSseChunks(buffer, onEvent) {
  let rest = buffer;
  let boundaryIndex = rest.indexOf("\n\n");
  while (boundaryIndex !== -1) {
    const rawEvent = rest.slice(0, boundaryIndex);
    rest = rest.slice(boundaryIndex + 2);
    const lines = rawEvent.split(/\n/);
    let eventName = "message";
    const dataLines = [];
    lines.forEach((line) => {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      }
      if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    });
    if (dataLines.length > 0) {
      try {
        const payload = JSON.parse(dataLines.join("\n"));
        onEvent(eventName, payload);
      } catch (_error) {
        // Ignore malformed event frames and keep reading.
      }
    }
    boundaryIndex = rest.indexOf("\n\n");
  }
  return rest;
}

async function submitCopilotForm(form) {
  const messageInput = form.querySelector("textarea[name='message']");
  const userIdInput = form.querySelector("input[name='user_id']");
  const sessionIdInput = form.querySelector("input[name='session_id']");
  const feed = document.querySelector("[data-chat-feed]");
  const emptyState = document.querySelector("[data-chat-empty-state]");
  const message = String(messageInput?.value || "").trim();
  if (!message || !feed || !userIdInput || !sessionIdInput) return;

  emptyState?.remove();
  const userMessageEl = createChatMessageElement("user", message);
  feed.appendChild(userMessageEl.wrapper);

  const assistantEl = createAssistantStreamElement();
  feed.appendChild(assistantEl.wrapper);
  scrollChatFeed(feed);
  messageInput.value = "";
  setCopilotSubmitting(form, true);

  let finalAnswer = "";
  let hasStreamError = false;
  const streamEndpoint = form.dataset.streamEndpoint || "/api/copilot/message/stream";

  try {
    const response = await fetch(streamEndpoint, {
      method: form.method || "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        user_id: userIdInput.value,
        session_id: sessionIdInput.value,
        message,
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error("流式回复不可用，请稍后重试。");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let done = false;

    while (!done) {
      const chunk = await reader.read();
      done = chunk.done;
      buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !done });
      buffer = parseSseChunks(buffer, (_eventName, payload) => {
        const eventType = payload.type || _eventName;
        if (payload.session_id && sessionIdInput.value !== payload.session_id) {
          sessionIdInput.value = payload.session_id;
        }
        if (eventType === "assistant_delta") {
          finalAnswer += payload.text || "";
          assistantEl.content.textContent = finalAnswer;
        } else if (eventType === "assistant_done") {
          finalAnswer = payload.text || finalAnswer;
          assistantEl.content.textContent = finalAnswer;
        } else if (eventType === "error") {
          hasStreamError = true;
          appendProcessLog(
            assistantEl.processLog,
            assistantEl.processSummary,
            assistantEl.processDetails,
            payload.text || "生成失败"
          );
          setStatus(payload.text || "生成失败", "error");
        } else if (eventType === "status" || eventType === "tool" || eventType === "agent") {
          appendProcessLog(
            assistantEl.processLog,
            assistantEl.processSummary,
            assistantEl.processDetails,
            payload.text || payload.detail || eventType
          );
        }
      });
      scrollChatFeed(feed);
    }

    assistantEl.content.textContent = resolveCopilotFinalText({ finalAnswer, hasError: hasStreamError });
    upsertSessionCard(sessionIdInput.value, userIdInput.value, message, finalAnswer);
  } catch (error) {
    assistantEl.content.textContent = "生成失败，请稍后重试。";
    appendProcessLog(assistantEl.processLog, assistantEl.processSummary, assistantEl.processDetails, "生成失败，请稍后重试。");
    if (error instanceof TypeError) {
      setStatus("网络连接异常，请检查后重试。", "error");
    } else {
      setStatus(error.message || "生成失败，请稍后重试。", "error");
    }
  } finally {
    setCopilotSubmitting(form, false);
    scrollChatFeed(feed);
  }
}

const copilotForm = document.querySelector("[data-copilot-form]");
if (copilotForm) {
  copilotForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitCopilotForm(copilotForm);
  });
}

window.__HCOPILOT_TEST_HOOKS__ = {
  createReminderEmptyState,
  refreshReminderEmptyState,
  handleReminderDeleteSuccess,
  handleReminderDeleteFailure,
  resolveCopilotFinalText,
};

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(readErrorMessage(response, data, "操作失败"));
  }
  return data;
}

function bindDeleteSessionButtons(buttons) {
  buttons.forEach((button) => {
    if (button.dataset.boundDeleteSession === "true") return;
    button.dataset.boundDeleteSession = "true";
    button.addEventListener("click", async () => {
      const userId = button.dataset.userId || "demo-user";
      const sessionId = button.dataset.sessionId;
      if (!sessionId || !window.confirm("确定删除这个会话吗？")) return;
      try {
        await postJson(`/api/copilot/session/${sessionId}/delete`, { user_id: userId });
        setStatus("会话已删除。");
        window.setTimeout(() => {
          window.location.href = `/copilot?user_id=${encodeURIComponent(userId)}&session_id=${Date.now()}&new_session=1`;
        }, 250);
      } catch (error) {
        setStatus(error.message || "删除失败", "error");
      }
    });
  });
}

bindDeleteSessionButtons(document.querySelectorAll("[data-delete-session]"));

document.querySelectorAll("[data-clear-sessions]").forEach((button) => {
  button.addEventListener("click", async () => {
    const userId = button.dataset.userId || "demo-user";
    if (!window.confirm("确定清空所有对话吗？")) return;
    try {
      await postJson("/api/copilot/sessions/clear", { user_id: userId });
      setStatus("所有会话已清空。");
      window.setTimeout(() => {
        window.location.href = `/copilot?user_id=${encodeURIComponent(userId)}&session_id=${Date.now()}&new_session=1`;
      }, 250);
    } catch (error) {
      setStatus(error.message || "清空失败", "error");
    }
  });
});

document.querySelectorAll("[data-toggle-reminder]").forEach((button) => {
  const card = button.closest("[data-reminder-card]");
  const statusBadge = card ? card.querySelector("[data-reminder-status]") : null;
  const setReminderUi = (isActive) => {
    button.dataset.enabled = isActive ? "false" : "true";
    button.textContent = isActive ? "暂停" : "启用";
    button.classList.remove("bg-[#fff1ef]", "text-[#9f403d]", "bg-[#eef8ef]", "text-[#305c37]");
    if (isActive) {
      button.classList.add("bg-[#fff1ef]", "text-[#9f403d]");
    } else {
      button.classList.add("bg-[#eef8ef]", "text-[#305c37]");
    }
    if (statusBadge) {
      statusBadge.textContent = isActive ? "active" : "paused";
      statusBadge.classList.remove("bg-[#e8f7ea]", "text-[#2f6d3a]", "bg-[#fff1ef]", "text-[#9f403d]");
      if (isActive) {
        statusBadge.classList.add("bg-[#e8f7ea]", "text-[#2f6d3a]");
      } else {
        statusBadge.classList.add("bg-[#fff1ef]", "text-[#9f403d]");
      }
    }
  };

  button.addEventListener("click", async () => {
    const reminderId = button.dataset.reminderId;
    if (!reminderId) return;
    const previousTarget = button.dataset.enabled;
    const previousIsActive = previousTarget === "false";
    const enabled = previousTarget === "true";
    button.disabled = true;
    setReminderUi(enabled);
    try {
      const result = await postJson(`/api/reminders/${reminderId}/toggle`, { enabled });
      if (result && typeof result.status === "string") {
        setReminderUi(result.status === "active");
      }
      setStatus(enabled ? "提醒已启用。" : "提醒已暂停。");
    } catch (error) {
      setReminderUi(previousIsActive);
      if (error instanceof TypeError) {
        setStatus("网络连接异常，请检查后重试。", "error");
      } else {
        setStatus(error.message || "提醒状态更新失败", "error");
      }
    } finally {
      button.disabled = false;
    }
  });
});

document.querySelectorAll("[data-delete-reminder]").forEach((button) => {
  button.addEventListener("click", async () => {
    const userId = button.dataset.userId || "demo-user";
    const reminderId = button.dataset.reminderId;
    if (!reminderId || !window.confirm("确定删除这个提醒吗？")) return;
    const card = button.closest("[data-reminder-card]");
    const list = card ? card.parentElement : document.querySelector("[data-reminder-list]");
    button.disabled = true;
    try {
      await postJson(`/api/reminders/${reminderId}/delete`, { user_id: userId });
      setStatus("提醒已删除。");
      handleReminderDeleteSuccess({ card, list });
    } catch (error) {
      handleReminderDeleteFailure({ button });
      if (error instanceof TypeError) {
        setStatus("网络连接异常，请检查后重试。", "error");
      } else {
        setStatus(error.message || "提醒删除失败", "error");
      }
    }
  });
});

const profileView = document.querySelector("[data-profile-view]");
const profileEdit = document.querySelector("[data-profile-edit]");
const profileEditButton = document.querySelector("[data-profile-edit-toggle]");
const profileCancelButton = document.querySelector("[data-profile-edit-cancel]");

if (profileView && profileEdit && profileEditButton) {
  profileEditButton.addEventListener("click", () => {
    profileView.classList.add("hidden");
    profileEdit.classList.remove("hidden");
    profileEditButton.classList.add("hidden");
  });
}

if (profileView && profileEdit && profileCancelButton && profileEditButton) {
  profileCancelButton.addEventListener("click", () => {
    profileEdit.classList.add("hidden");
    profileView.classList.remove("hidden");
    profileEditButton.classList.remove("hidden");
  });
}

document.querySelectorAll("[data-delete-record]").forEach((button) => {
  button.addEventListener("click", async () => {
    const userId = button.dataset.userId || "demo-user";
    const recordId = button.dataset.recordId;
    if (!recordId || !window.confirm("确定删除这条记录吗？")) return;
    const card = button.closest("[data-record-card]");
    button.disabled = true;
    try {
      await postJson(`/api/records/${recordId}/delete`, { user_id: userId });
      setStatus("记录已删除。");
      if (card) {
        card.remove();
      }
      refreshRecordEmptyState();
    } catch (error) {
      if (String(error.message || "").includes("不存在")) {
        if (card) {
          card.remove();
        }
        refreshRecordEmptyState();
        setStatus("记录已不存在，页面已同步更新。");
      } else {
        setStatus(error.message || "删除记录失败", "error");
      }
    } finally {
      button.disabled = false;
    }
  });
});

document.querySelectorAll("[data-clear-records]").forEach((button) => {
  button.addEventListener("click", async () => {
    const userId = button.dataset.userId || "demo-user";
    if (!window.confirm("确定清除全部记录吗？")) return;
    const list = document.querySelector("[data-record-list]");
    button.disabled = true;
    try {
      await postJson("/api/records/clear", { user_id: userId });
      setStatus("记录已清除。");
      if (list) {
        list.querySelectorAll("[data-record-card]").forEach((card) => card.remove());
      }
      refreshRecordEmptyState();
    } catch (error) {
      try {
        await postJson("/api/records/clear-all", { user_id: userId });
        setStatus("记录已清除。");
        if (list) {
          list.querySelectorAll("[data-record-card]").forEach((card) => card.remove());
        }
        refreshRecordEmptyState();
      } catch (_fallbackError) {
        setStatus(error.message || "清除记录失败", "error");
      }
    } finally {
      button.disabled = false;
    }
  });
});

function refreshRecordEmptyState() {
  const list = document.querySelector("[data-record-list]");
  const empty = document.querySelector("[data-record-empty-state]");
  if (!list || !empty) return;
  const hasCards = list.querySelectorAll("[data-record-card]").length > 0;
  empty.classList.toggle("hidden", hasCards);
}
