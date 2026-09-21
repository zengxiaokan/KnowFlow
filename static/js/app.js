(() => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socketUrl = (path) => protocol + "://" + window.location.host + path;

  document.querySelectorAll("[data-modal-open]").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = document.getElementById(button.dataset.modalOpen);
      if (modal) modal.showModal();
    });
  });
  document.querySelectorAll("[data-modal-close]").forEach((button) => {
    button.addEventListener("click", () => button.closest("dialog")?.close());
  });

  const chatPanel = document.getElementById("chat-panel");
  const resizeHandle = document.getElementById("chat-resize-handle");
  if (chatPanel && resizeHandle && window.matchMedia("(min-width: 1051px)").matches) {
    const layout = chatPanel.closest(".detail-layout");
    const savedWidth = Number(window.localStorage.getItem("knowflow-chat-panel-width"));
    const setWidth = (width) => {
      const bounded = Math.max(320, Math.min(620, Math.round(width)));
      layout.style.setProperty("--chat-panel-width", bounded + "px");
      window.localStorage.setItem("knowflow-chat-panel-width", String(bounded));
      return bounded;
    };
    if (Number.isFinite(savedWidth) && savedWidth > 0) setWidth(savedWidth);
    resizeHandle.addEventListener("pointerdown", (event) => {
      const startX = event.clientX;
      const startWidth = chatPanel.getBoundingClientRect().width;
      resizeHandle.setPointerCapture(event.pointerId);
      document.body.classList.add("is-resizing-chat");
      const resize = (moveEvent) => setWidth(startWidth - (moveEvent.clientX - startX));
      const stop = () => {
        document.body.classList.remove("is-resizing-chat");
        resizeHandle.removeEventListener("pointermove", resize);
        resizeHandle.removeEventListener("pointerup", stop);
        resizeHandle.removeEventListener("pointercancel", stop);
      };
      resizeHandle.addEventListener("pointermove", resize);
      resizeHandle.addEventListener("pointerup", stop);
      resizeHandle.addEventListener("pointercancel", stop);
    });
  }

  document.querySelectorAll("[data-task-id]").forEach((target) => {
    const taskId = target.dataset.taskId;
    if (!taskId) return;
    const socket = new WebSocket(socketUrl("/ws/tasks/" + taskId + "/"));
    socket.onmessage = ({ data }) => {
      const event = JSON.parse(data);
      const row = document.querySelector('[data-task-row="' + event.id + '"]');
      if (!row) return;
      const status = row.querySelector("[data-task-status]");
      const progress = row.querySelector("[data-task-progress]");
      if (status) {
        const displayStatus = event.status === "succeeded" ? "ready" : event.status === "failed" ? "failed" : "processing";
        status.className = "status status-" + displayStatus;
        status.textContent = event.status === "succeeded" ? "已就绪" : event.status === "failed" ? "失败" : "处理中";
      }
      if (progress) progress.textContent = event.stage + " " + event.progress + "%";
      if (event.status === "succeeded") window.setTimeout(() => window.location.reload(), 550);
    };
  });

  const form = document.getElementById("question-form");
  if (!form) return;
  const log = document.getElementById("chat-log");
  const input = document.getElementById("question-input");
  const conversationInput = document.getElementById("conversation-id");
  const usageLabel = document.getElementById("usage-label");
  const submitButton = form.querySelector('button[type="submit"]');
  let conversationSocket;
  let pendingMessageId = null;

  const setSending = (sending) => {
    input.disabled = sending;
    if (submitButton) submitButton.disabled = sending;
  };

  const ensureAssistantActions = (article) => {
    if (article.querySelector(".message-actions")) return;
    const actions = document.createElement("div");
    actions.className = "message-actions";
    const copy = document.createElement("button");
    copy.className = "message-action";
    copy.type = "button";
    copy.dataset.copyAnswer = "";
    copy.textContent = "复制";
    actions.appendChild(copy);
    article.prepend(actions);
  };

  const addCodeCopyButtons = (root) => {
    root.querySelectorAll("pre").forEach((block) => {
      if (block.querySelector("[data-copy-code]")) return;
      const button = document.createElement("button");
      button.className = "code-copy";
      button.type = "button";
      button.dataset.copyCode = "";
      button.textContent = "复制代码";
      block.prepend(button);
    });
  };

  const copyText = async (text, button) => {
    try {
      await navigator.clipboard.writeText(text);
      const original = button.textContent;
      button.textContent = "已复制";
      window.setTimeout(() => { button.textContent = original; }, 1200);
    } catch (error) {
      button.textContent = "复制失败";
    }
  };

  const addMessage = (role, content, id) => {
    log.querySelector(".chat-empty")?.remove();
    const article = document.createElement("article");
    article.className = "chat-message " + role;
    if (id) article.dataset.messageId = id;
    const body = document.createElement("div");
    body.className = "message-content";
    body.textContent = content;
    article.appendChild(body);
    if (role === "assistant") ensureAssistantActions(article);
    log.appendChild(article);
    log.scrollTop = log.scrollHeight;
    return article;
  };

  const messageFor = (messageId) =>
    log.querySelector('[data-message-id="' + messageId + '"]');

  const showAssistantStatus = (messageId, text) => {
    let element = messageFor(messageId);
    if (!element) element = addMessage("assistant", text, messageId);
    element.classList.add("is-pending");
    element.querySelector(".message-content").textContent = text;
    return element;
  };

  const renderSources = (element, sources) => {
    if (!sources?.length || element.querySelector(".sources")) return;
    const container = document.createElement("div");
    container.className = "sources";
    sources.forEach((source, index) => {
      const item = document.createElement("span");
      item.textContent = "[" + (index + 1) + "] " + source.title + (source.heading ? " · " + source.heading : "");
      container.appendChild(item);
    });
    element.appendChild(container);
  };

  const connectConversation = (path) => {
    if (conversationSocket) conversationSocket.close();
    conversationSocket = new WebSocket(socketUrl(path));
    conversationSocket.onmessage = ({ data }) => {
      const event = JSON.parse(data);
      if (event.event === "answer.started") {
        const sourceHint = event.source_count ? "已找到 " + event.source_count + " 段相关资料，" : "";
        showAssistantStatus(event.message_id, sourceHint + "正在组织回答…");
      }
      if (event.event === "answer.delta") {
        let element = messageFor(event.message_id);
        if (!element) element = addMessage("assistant", "", event.message_id);
        if (element.classList.contains("is-pending")) {
          element.classList.remove("is-pending");
          element.querySelector(".message-content").textContent = "";
        }
        element.querySelector(".message-content").textContent += event.text;
        log.scrollTop = log.scrollHeight;
      }
      if (event.event === "answer.completed") {
        const element = messageFor(event.message_id);
        if (element && event.rendered_content) {
          element.classList.remove("is-pending");
          element.querySelector(".message-content").innerHTML = event.rendered_content;
          ensureAssistantActions(element);
          addCodeCopyButtons(element);
        }
        if (element) renderSources(element, event.sources);
        if (event.usage) {
          const suffix = event.usage.estimated ? "（估算）" : "";
          usageLabel.textContent = "本次约 " + (event.usage.input_tokens + event.usage.output_tokens) + " Token" + suffix;
        }
        if (event.message_id === pendingMessageId) {
          pendingMessageId = null;
          setSending(false);
        }
      }
      if (event.event === "answer.failed") {
        const element = messageFor(event.message_id);
        if (element) {
          element.classList.remove("is-pending");
          element.querySelector(".message-content").textContent = "回答失败：" + event.error;
        } else {
          addMessage("assistant", "回答失败：" + event.error, event.message_id);
        }
        if (event.message_id === pendingMessageId) {
          pendingMessageId = null;
          setSending(false);
        }
      }
    };
  };

  const initialConversation = document.getElementById("chat-panel").dataset.initialConversation;
  document.querySelectorAll(".chat-message.assistant").forEach((article) => {
    ensureAssistantActions(article);
    addCodeCopyButtons(article);
  });
  document.addEventListener("click", (event) => {
    const answerButton = event.target.closest("[data-copy-answer]");
    if (answerButton) {
      const content = answerButton.closest(".chat-message").querySelector(".message-content");
      copyText(content.innerText, answerButton);
      return;
    }
    const codeButton = event.target.closest("[data-copy-code]");
    if (codeButton) copyText(codeButton.closest("pre").querySelector("code").textContent, codeButton);
  });
  if (initialConversation) connectConversation("/ws/conversations/" + initialConversation + "/");
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    const requestData = new FormData(form);
    addMessage("user", text);
    const pending = addMessage("assistant", "正在发送问题…");
    pending.classList.add("is-pending");
    input.value = "";
    setSending(true);
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: requestData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) {
        pending.classList.remove("is-pending");
        pending.querySelector(".message-content").textContent = "提交失败：" + (await response.text());
        setSending(false);
        return;
      }
      const payload = await response.json();
      pendingMessageId = payload.assistant_message_id;
      pending.dataset.messageId = pendingMessageId;
      showAssistantStatus(pendingMessageId, "正在检索资料…");
      conversationInput.value = payload.conversation_id;
      connectConversation(payload.websocket_url);
    } catch (error) {
      pending.classList.remove("is-pending");
      pending.querySelector(".message-content").textContent = "提交失败：网络连接异常，请重试。";
      setSending(false);
    }
  });
})();
