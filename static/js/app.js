const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const modeBtns = document.querySelectorAll(".mode-btn");
const themeBtn = document.getElementById("theme-btn");
const exportBtn = document.getElementById("export-btn");
const toolsToggle = document.getElementById("tools-toggle");
const personaBtn = document.getElementById("persona-btn");
const personaModal = document.getElementById("persona-modal");
const personaInput = document.getElementById("persona-input");
const personaSave = document.getElementById("persona-save");
const personaCancel = document.getElementById("persona-cancel");
const newChatBtn = document.getElementById("new-chat-btn");
const conversationListEl = document.getElementById("conversation-list");
const conversationTitleEl = document.getElementById("conversation-title");
const fileInput = document.getElementById("file-input");
const attachBtn = document.getElementById("attach-btn");
const attachmentPreview = document.getElementById("attachment-preview");

let mode = "chat";
let toolsEnabled = false;
let currentConversation = null; // {id, title, system_prompt}
let conversationLog = []; // [{role, content, provider, el}]
let lastUserEntry = null;
let lastAssistantEntry = null;

// Holds at most one pending attachment between "file picked" and "message
// sent". Images are forwarded to the backend as base64 for vision models;
// text/markdown files are just read client-side and folded into the
// message text (simple "stuff the document into context" approach —
// no embeddings/vector store needed for a project this size).
let pendingAttachment = null; // {kind: 'image'|'document', mimeType, data, filename, previewUrl}

const CHAT_CHAIN = ["groq", "gemini", "openrouter"];
const IMAGE_CHAIN = ["pollinations", "huggingface"];

// Identifies this browser across visits (not the conversation itself —
// one browser can own many conversations).
function getBrowserId() {
  let id = localStorage.getItem("relay_browser_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("relay_browser_id", id);
  }
  return id;
}
const browserId = getBrowserId();

// --------------------------------------------------------------------
// Theme toggle
// --------------------------------------------------------------------
function applyTheme(theme) {
  document.documentElement.classList.toggle("light", theme === "light");
  themeBtn.textContent = theme === "light" ? "☀" : "☾";
  const hljsTheme = document.getElementById("hljs-theme");
  hljsTheme.href = theme === "light"
    ? "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css"
    : "https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github-dark.min.css";
}
function getStoredTheme() { return localStorage.getItem("relay_theme") || "dark"; }
applyTheme(getStoredTheme());
themeBtn.addEventListener("click", () => {
  const next = getStoredTheme() === "light" ? "dark" : "light";
  localStorage.setItem("relay_theme", next);
  applyTheme(next);
});

// --------------------------------------------------------------------
// Mode switch (chat / image)
// --------------------------------------------------------------------
modeBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeBtns.forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    mode = btn.dataset.mode;
    input.placeholder = mode === "chat" ? "Message Relay…" : "Describe an image…";
  });
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

// --------------------------------------------------------------------
// Tool calling toggle
// --------------------------------------------------------------------
toolsToggle.addEventListener("click", () => {
  toolsEnabled = !toolsEnabled;
  toolsToggle.classList.toggle("toggled", toolsEnabled);
});

// --------------------------------------------------------------------
// Attachments (image for vision, text/markdown for document Q&A)
// --------------------------------------------------------------------
attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileInput.value = ""; // allow picking the same file again later
  if (!file) return;

  const isImage = file.type.startsWith("image/");
  const isText = file.type.startsWith("text/") || /\.(txt|md)$/i.test(file.name);

  if (isImage) {
    const reader = new FileReader();
    reader.onload = () => {
      // reader.result is a data URL like "data:image/png;base64,AAAA..."
      const [, base64] = reader.result.split(",");
      pendingAttachment = {
        kind: "image",
        mimeType: file.type,
        data: base64,
        filename: file.name,
        previewUrl: reader.result,
      };
      renderAttachmentPreview();
    };
    reader.readAsDataURL(file);
  } else if (isText) {
    const reader = new FileReader();
    reader.onload = () => {
      // Cap document length so a huge file doesn't blow past a
      // provider's context window or your free-tier token budget.
      const MAX_CHARS = 12000;
      let content = reader.result;
      let truncated = false;
      if (content.length > MAX_CHARS) {
        content = content.slice(0, MAX_CHARS);
        truncated = true;
      }
      pendingAttachment = {
        kind: "document",
        filename: file.name,
        content,
        truncated,
      };
      renderAttachmentPreview();
    };
    reader.readAsText(file);
  } else {
    alert("Only images and .txt/.md files are supported right now.");
  }
});

function renderAttachmentPreview() {
  attachmentPreview.innerHTML = "";
  if (!pendingAttachment) {
    attachmentPreview.classList.add("hidden");
    return;
  }
  attachmentPreview.classList.remove("hidden");

  const chip = document.createElement("div");
  chip.className = "attachment-chip";

  if (pendingAttachment.kind === "image") {
    const img = document.createElement("img");
    img.src = pendingAttachment.previewUrl;
    chip.appendChild(img);
    const label = document.createElement("span");
    label.textContent = pendingAttachment.filename;
    chip.appendChild(label);
  } else {
    const label = document.createElement("span");
    label.textContent = `📄 ${pendingAttachment.filename}${pendingAttachment.truncated ? " (truncated)" : ""}`;
    chip.appendChild(label);
  }

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "remove-attachment";
  removeBtn.textContent = "✕";
  removeBtn.addEventListener("click", () => {
    pendingAttachment = null;
    renderAttachmentPreview();
  });
  chip.appendChild(removeBtn);

  attachmentPreview.appendChild(chip);
}

// --------------------------------------------------------------------
// Message rendering helpers
// --------------------------------------------------------------------
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function addMessage(role, html) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = html;
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  return div;
}

function renderMarkdownInto(container, rawText) {
  container.innerHTML = marked.parse(rawText || "");
  container.querySelectorAll("pre code").forEach((block) => {
    hljs.highlightElement(block);
    const pre = block.parentElement;
    if (pre.parentElement.classList.contains("code-block-wrap")) return;
    const wrap = document.createElement("div");
    wrap.className = "code-block-wrap";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);
    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.textContent = "Copy";
    copyBtn.type = "button";
    copyBtn.addEventListener("click", () => copyText(block.textContent, copyBtn));
    wrap.appendChild(copyBtn);
  });
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  });
}

// Adds a user message bubble with an Edit action (only the latest user
// turn keeps its Edit button — older ones lose it once superseded).
// `attachmentNote` is display-only (e.g. an image thumbnail or a "📄 file
// attached" line) — it's never sent back to the server, since images
// aren't persisted and document text is already folded into `text`.
function addUserMessage(text, attachmentHtml) {
  const div = document.createElement("div");
  div.className = "msg user";
  const content = document.createElement("div");
  content.textContent = text;
  div.appendChild(content);

  if (attachmentHtml) {
    const extra = document.createElement("div");
    extra.innerHTML = attachmentHtml;
    div.appendChild(extra);
  }

  const actions = document.createElement("div");
  actions.className = "msg-actions";
  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "msg-action-btn";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => editUserMessage(entry));
  actions.appendChild(editBtn);
  div.appendChild(actions);

  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;

  if (lastUserEntry) lastUserEntry.el.querySelector(".msg-actions")?.remove();
  const entry = { role: "user", content: text, el: div };
  lastUserEntry = entry;
  conversationLog.push(entry);
  return entry;
}

// Adds an assistant message bubble with a Regenerate action (only the
// latest assistant turn keeps it).
function addAssistantMessage(provider, rawText, extraHtml, toolCalls) {
  const div = document.createElement("div");
  div.className = "msg assistant";

  if (toolCalls && toolCalls.length > 0) {
    const trail = document.createElement("div");
    trail.className = "tool-call-trail";
    toolCalls.forEach((tc) => {
      const chip = document.createElement("div");
      chip.className = "tool-call-chip";
      const argsStr = Object.entries(tc.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ");
      chip.innerHTML = `🔧 <span class="tool-name">${escapeHtml(tc.name)}</span>(${escapeHtml(argsStr)}) → ${escapeHtml(String(tc.result))}`;
      trail.appendChild(chip);
    });
    div.appendChild(trail);
  }

  const tag = document.createElement("span");
  tag.className = "tag";
  tag.textContent = provider || "";
  div.appendChild(tag);

  const content = document.createElement("div");
  content.className = "msg-content";
  renderMarkdownInto(content, rawText);
  div.appendChild(content);

  if (extraHtml) {
    const extra = document.createElement("div");
    extra.innerHTML = extraHtml;
    div.appendChild(extra);
  }

  const actions = document.createElement("div");
  actions.className = "msg-actions";

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "msg-action-btn";
  copyBtn.textContent = "Copy";
  copyBtn.addEventListener("click", () => copyText(entryRef.content, copyBtn));
  actions.appendChild(copyBtn);

  const regenBtn = document.createElement("button");
  regenBtn.type = "button";
  regenBtn.className = "msg-action-btn";
  regenBtn.textContent = "Regenerate";
  regenBtn.addEventListener("click", () => regenerateLast());
  actions.appendChild(regenBtn);

  div.appendChild(actions);

  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;

  if (lastAssistantEntry) lastAssistantEntry.el.querySelector(".msg-actions")?.remove();
  const entryRef = { role: "assistant", provider, content: rawText, el: div, contentEl: content };
  lastAssistantEntry = entryRef;
  conversationLog.push(entryRef);
  return entryRef;
}

function setRelayState(chain, activeName, state) {
  chain.forEach((name) => {
    const chip = document.querySelector(`.relay-chip[data-provider="${name}"]`);
    if (!chip) return;
    chip.classList.remove("trying", "answered", "failed");
    if (name === activeName) chip.classList.add(state);
  });
}
function resetRelay(chain) {
  chain.forEach((name) => {
    const chip = document.querySelector(`.relay-chip[data-provider="${name}"]`);
    if (chip) chip.classList.remove("trying", "answered", "failed");
  });
}

// --------------------------------------------------------------------
// Conversations (sidebar)
// --------------------------------------------------------------------
async function fetchConversations() {
  const res = await fetch(`/api/conversations?browser_id=${browserId}`);
  const data = await res.json();
  return data.conversations || [];
}

function renderConversationList(conversations) {
  conversationListEl.innerHTML = "";
  conversations.forEach((conv) => {
    const item = document.createElement("div");
    item.className = "conv-item" + (currentConversation && conv.id === currentConversation.id ? " active" : "");

    const title = document.createElement("span");
    title.className = "conv-title";
    title.textContent = conv.title || "New chat";
    title.title = "Double-click to rename";
    item.appendChild(title);

    function startRename() {
      const inputEl = document.createElement("input");
      inputEl.type = "text";
      inputEl.className = "conv-title-input";
      inputEl.value = conv.title || "New chat";
      item.replaceChild(inputEl, title);
      inputEl.focus();
      inputEl.select();

      let saved = false;
      async function save() {
        if (saved) return;
        saved = true;
        const newTitle = inputEl.value.trim() || "New chat";
        if (newTitle !== conv.title) {
          await fetch(`/api/conversations/${conv.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: newTitle }),
          });
          conv.title = newTitle;
          if (currentConversation && currentConversation.id === conv.id) {
            currentConversation.title = newTitle;
            conversationTitleEl.textContent = newTitle;
          }
        }
        renderConversationList(await fetchConversations());
      }
      inputEl.addEventListener("blur", save);
      inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); inputEl.blur(); }
        if (e.key === "Escape") { saved = true; renderConversationList(conversations); }
      });
    }

    title.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      startRename();
    });

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "conv-rename";
    renameBtn.textContent = "✎";
    renameBtn.title = "Rename conversation";
    renameBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      startRename();
    });
    item.appendChild(renameBtn);

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "conv-delete";
    delBtn.textContent = "✕";
    delBtn.title = "Delete conversation";
    delBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${conv.title}"? This can't be undone.`)) return;
      await fetch(`/api/conversations/${conv.id}`, { method: "DELETE" });
      const remaining = await fetchConversations();
      if (remaining.length === 0) {
        await createConversation();
      } else if (currentConversation && currentConversation.id === conv.id) {
        await switchConversation(remaining[0].id);
      }
      renderConversationList(await fetchConversations());
    });
    item.appendChild(delBtn);

    item.addEventListener("click", () => switchConversation(conv.id));
    conversationListEl.appendChild(item);
  });
}

async function createConversation() {
  const res = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ browser_id: browserId, title: "New chat" }),
  });
  const data = await res.json();
  await switchConversation(data.conversation.id);
  renderConversationList(await fetchConversations());
}
newChatBtn.addEventListener("click", createConversation);

async function switchConversation(conversationId) {
  const conversations = await fetchConversations();
  const conv = conversations.find((c) => c.id === conversationId);
  if (!conv) return;

  currentConversation = conv;
  localStorage.setItem("relay_current_conversation", conversationId);
  conversationTitleEl.textContent = conv.title || "Relay";
  conversationLog = [];
  lastUserEntry = null;
  lastAssistantEntry = null;
  thread.innerHTML = "";
  renderConversationList(conversations);
  await loadHistory();
}

async function initConversations() {
  const conversations = await fetchConversations();
  if (conversations.length === 0) {
    await createConversation();
    return;
  }
  const savedId = localStorage.getItem("relay_current_conversation");
  const target = conversations.find((c) => c.id === savedId) || conversations[0];
  await switchConversation(target.id);
}

// Auto-titles a brand-new conversation from the first message sent in it.
async function maybeAutoTitle(firstMessageText) {
  if (!currentConversation || currentConversation.title !== "New chat") return;
  const title = firstMessageText.slice(0, 40) + (firstMessageText.length > 40 ? "…" : "");
  await fetch(`/api/conversations/${currentConversation.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  currentConversation.title = title;
  conversationTitleEl.textContent = title;
  renderConversationList(await fetchConversations());
}

// --------------------------------------------------------------------
// Persona modal
// --------------------------------------------------------------------
personaBtn.addEventListener("click", () => {
  personaInput.value = currentConversation ? currentConversation.system_prompt || "" : "";
  personaModal.classList.remove("hidden");
});
personaCancel.addEventListener("click", () => personaModal.classList.add("hidden"));
personaSave.addEventListener("click", async () => {
  if (!currentConversation) return;
  const system_prompt = personaInput.value.trim();
  await fetch(`/api/conversations/${currentConversation.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ system_prompt }),
  });
  currentConversation.system_prompt = system_prompt;
  personaModal.classList.add("hidden");
});

// --------------------------------------------------------------------
// Export
// --------------------------------------------------------------------
exportBtn.addEventListener("click", () => {
  if (conversationLog.length === 0) {
    alert("Nothing to export yet.");
    return;
  }
  const lines = conversationLog.map((m) => {
    const speaker = m.role === "user" ? "You" : `Assistant (${m.provider || "unknown"})`;
    return `### ${speaker}\n\n${m.content}\n`;
  });
  const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `relay-conversation-${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  URL.revokeObjectURL(url);
});

// --------------------------------------------------------------------
// Edit last user message
// --------------------------------------------------------------------
async function editUserMessage(entry) {
  if (!currentConversation) return;
  const isLastOverall = conversationLog[conversationLog.length - 1] === entry;
  const hasReplyAfter = !isLastOverall; // an assistant entry was pushed after it
  const count = hasReplyAfter ? 2 : 1;

  await fetch("/api/history/delete_last", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: currentConversation.id, count }),
  });

  // Remove from DOM + local log: this entry and everything after it.
  const idx = conversationLog.indexOf(entry);
  const removed = conversationLog.splice(idx);
  removed.forEach((e) => e.el.remove());
  lastUserEntry = conversationLog.slice().reverse().find((e) => e.role === "user") || null;
  lastAssistantEntry = conversationLog.slice().reverse().find((e) => e.role === "assistant") || null;

  input.value = entry.content;
  input.dispatchEvent(new Event("input"));
  input.focus();
}

// --------------------------------------------------------------------
// Load past history on conversation switch
// --------------------------------------------------------------------
async function loadHistory() {
  if (!currentConversation) return;
  try {
    const res = await fetch(`/api/history?conversation_id=${currentConversation.id}`);
    const data = await res.json();
    if (!data.messages) return;

    for (const m of data.messages) {
      if (m.role === "user") {
        addUserMessage(m.content);
      } else if (m.kind === "image") {
        addAssistantMessage(m.provider, m.content, "<em>(image not stored — regenerate if needed)</em>");
      } else {
        addAssistantMessage(m.provider, m.content);
      }
    }
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

// --------------------------------------------------------------------
// Submit handling
// --------------------------------------------------------------------
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if ((!text && !pendingAttachment) || !currentConversation) return;

  const attachment = pendingAttachment;
  pendingAttachment = null;
  renderAttachmentPreview();

  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;

  const wasNewChat = currentConversation.title === "New chat";

  if (mode === "image") {
    // Image *generation* mode ignores attachments — they're for chat
    // input (vision / document context), not part of the prompt here.
    addUserMessage(text || "(generate an image)");
    if (wasNewChat) await maybeAutoTitle(text);
    await runImage(text);
    sendBtn.disabled = false;
    return;
  }

  if (attachment && attachment.kind === "image") {
    const displayText = text || "(what's in this image?)";
    addUserMessage(displayText, `<img class="msg-user-image" src="${attachment.previewUrl}" alt="attached image">`);
    if (wasNewChat) await maybeAutoTitle(displayText);
    await runChat(displayText, { mimeType: attachment.mimeType, data: attachment.data });
  } else if (attachment && attachment.kind === "document") {
    const question = text || "Summarize this document.";
    const displayNote = `<div class="msg-attachment-note">📄 ${escapeHtml(attachment.filename)}${attachment.truncated ? " (truncated to fit context)" : ""} attached</div>`;
    addUserMessage(question, displayNote);
    if (wasNewChat) await maybeAutoTitle(question);
    const augmented = `Attached document "${attachment.filename}":\n\n${attachment.content}\n\n---\n\nQuestion: ${question}`;
    await runChat(augmented);
  } else {
    addUserMessage(text);
    if (wasNewChat) await maybeAutoTitle(text);
    if (toolsEnabled) {
      await runChatWithTools(text);
    } else {
      await runChat(text);
    }
  }

  sendBtn.disabled = false;
});

// Shared SSE stream consumer for both a normal send and a regenerate.
async function consumeStream(url, body) {
  resetRelay(CHAT_CHAIN);
  document.querySelector(`.relay-chip[data-provider="groq"]`).classList.add("trying");

  const thinking = addMessage("thinking", "Relaying…");
  let entryRef = null;
  let rawText = "";

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok || !res.body) {
      thinking.remove();
      const errData = await res.json().catch(() => ({}));
      addMessage("error", escapeHtml(errData.error || "Failed to reach the server."));
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const evt of events) {
        if (!evt.startsWith("data: ")) continue;
        const data = JSON.parse(evt.slice(6));

        if (data.type === "provider") {
          thinking.remove();
          setRelayState(CHAT_CHAIN, data.provider, "answered");
          entryRef = addAssistantMessage(data.provider, "");
        } else if (data.type === "delta" && entryRef) {
          rawText += data.text;
          entryRef.contentEl.textContent = rawText;
          thread.scrollTop = thread.scrollHeight;
        } else if (data.type === "error") {
          thinking.remove();
          setRelayState(CHAT_CHAIN, null, "failed");
          addMessage("error", `All providers failed: ${escapeHtml(data.detail || "unknown error")}`);
        } else if (data.type === "done" && entryRef) {
          renderMarkdownInto(entryRef.contentEl, rawText);
          entryRef.content = rawText;
        }
      }
    }
  } catch (err) {
    thinking.remove();
    addMessage("error", `Network error: ${escapeHtml(String(err))}`);
  }
}

async function runChat(message, image) {
  const body = { conversation_id: currentConversation.id, message };
  if (image) body.image = { mime_type: image.mimeType, data: image.data };
  await consumeStream("/api/chat/stream", body);
}

// Tool calling is non-streaming (see providers.py for why), so this posts
// once and renders the whole reply — plus a trail of which tools got
// called — when the response comes back, instead of typing it out live.
async function runChatWithTools(message) {
  resetRelay(CHAT_CHAIN);
  document.querySelector(`.relay-chip[data-provider="groq"]`).classList.add("trying");

  const thinking = addMessage("thinking", "Thinking, maybe using a tool…");

  try {
    const res = await fetch("/api/chat/tools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: currentConversation.id, message }),
    });
    const data = await res.json();
    thinking.remove();

    if (!res.ok) {
      setRelayState(CHAT_CHAIN, null, "failed");
      addMessage("error", `Tool-capable providers failed: ${escapeHtml(data.detail || "unknown error")}`);
      return;
    }

    setRelayState(CHAT_CHAIN, data.provider, "answered");
    addAssistantMessage(data.provider, data.reply, null, data.tool_calls);
  } catch (err) {
    thinking.remove();
    addMessage("error", `Network error: ${escapeHtml(String(err))}`);
  }
}

async function regenerateLast() {
  if (!currentConversation || !lastAssistantEntry) return;
  const idx = conversationLog.indexOf(lastAssistantEntry);
  if (idx !== -1) {
    conversationLog.splice(idx, 1);
    lastAssistantEntry.el.remove();
  }
  lastAssistantEntry = conversationLog.slice().reverse().find((e) => e.role === "assistant") || null;
  await consumeStream("/api/chat/regenerate", { conversation_id: currentConversation.id });
}

async function runImage(prompt) {
  resetRelay(IMAGE_CHAIN);
  document.querySelector(`.relay-chip[data-provider="pollinations"]`).classList.add("trying");

  const thinking = addMessage("thinking", "Generating…");

  try {
    const res = await fetch("/api/image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: currentConversation.id, prompt }),
    });
    const data = await res.json();
    thinking.remove();

    if (!res.ok) {
      setRelayState(IMAGE_CHAIN, null, "failed");
      addMessage("error", `All image providers failed: ${escapeHtml(data.detail || "unknown error")}`);
      return;
    }

    setRelayState(IMAGE_CHAIN, data.provider, "answered");
    const imgHtml = `<img src="data:image/png;base64,${data.image_base64}" alt="${escapeHtml(prompt)}">`;
    addAssistantMessage(data.provider, `[image] ${prompt}`, imgHtml);
  } catch (err) {
    thinking.remove();
    addMessage("error", `Network error: ${escapeHtml(String(err))}`);
  }
}

// --------------------------------------------------------------------
// Boot
// --------------------------------------------------------------------
initConversations();
