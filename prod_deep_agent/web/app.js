(function () {
  const API = "/api";
  let fromCheckpoint = null;

  const chat = document.getElementById("chat");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const threadId = document.getElementById("threadId");
  const userId = document.getElementById("userId");
  const newThreadBtn = document.getElementById("newThread");
  const loadHistoryBtn = document.getElementById("loadHistory");
  const historyOut = document.getElementById("historyOut");
  const checkpointId = document.getElementById("checkpointId");
  const setRollbackBtn = document.getElementById("setRollback");
  const memoryLsBtn = document.getElementById("memoryLs");
  const memoryLsOut = document.getElementById("memoryLsOut");
  const memoryPath = document.getElementById("memoryPath");
  const memoryReadBtn = document.getElementById("memoryRead");
  const memoryContent = document.getElementById("memoryContent");
  const memoryWriteBtn = document.getElementById("memoryWrite");
  const memoryReadOut = document.getElementById("memoryReadOut");

  function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.innerHTML = "<span class='role'>" + (role === "user" ? "Вы" : "Агент") + "</span><div>" + escapeHtml(text) + "</div>";
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function getThreadId() {
    let tid = (threadId.value || "").trim();
    if (!tid) {
      addMessage("assistant", "Укажите Thread ID или нажмите «Новый диалог».");
      return null;
    }
    return tid;
  }

  newThreadBtn.addEventListener("click", async function () {
    try {
      const r = await fetch(API + "/threads/new");
      const d = await r.json();
      threadId.value = d.thread_id || "";
    } catch (e) {
      historyOut.textContent = "Ошибка: " + e.message;
    }
  });

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage() {
    const tid = getThreadId();
    if (!tid) return;
    const text = (input.value || "").trim();
    if (!text) return;
    addMessage("user", text);
    input.value = "";
    sendBtn.disabled = true;
    try {
      const body = { thread_id: tid, message: text };
      if (userId.value.trim()) body.user_id = userId.value.trim();
      if (fromCheckpoint) {
        body.from_checkpoint = fromCheckpoint;
        fromCheckpoint = null;
      }
      const r = await fetch(API + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || data.message || r.statusText);
      addMessage("assistant", data.reply || "");
    } catch (e) {
      addMessage("assistant", "Ошибка: " + e.message);
    } finally {
      sendBtn.disabled = false;
    }
  }

  loadHistoryBtn.addEventListener("click", async function () {
    const tid = getThreadId();
    if (!tid) return;
    const uid = (userId.value || "").trim() || null;
    let url = API + "/threads/" + encodeURIComponent(tid) + "/history?limit=20";
    if (uid) url += "&user_id=" + encodeURIComponent(uid);
    try {
      const r = await fetch(url);
      const d = await r.json();
      historyOut.textContent = JSON.stringify(d.checkpoints || d, null, 2);
    } catch (e) {
      historyOut.textContent = "Ошибка: " + e.message;
    }
  });

  setRollbackBtn.addEventListener("click", function () {
    const cid = (checkpointId.value || "").trim();
    if (!cid) {
      historyOut.textContent = "Введите checkpoint_id из истории.";
      return;
    }
    fromCheckpoint = cid;
    historyOut.textContent = "Откат установлен. Следующее сообщение продолжит с выбранного шага.";
  });

  memoryLsBtn.addEventListener("click", async function () {
    const uid = (userId.value || "").trim() || null;
    const url = API + "/memory" + (uid ? "?user_id=" + encodeURIComponent(uid) : "");
    try {
      const r = await fetch(url);
      const d = await r.json();
      memoryLsOut.textContent = JSON.stringify(d.items || d, null, 2);
    } catch (e) {
      memoryLsOut.textContent = "Ошибка: " + e.message;
    }
  });

  memoryReadBtn.addEventListener("click", async function () {
    const path = (memoryPath.value || "/memories/preferences.txt").trim();
    const uid = (userId.value || "").trim() || null;
    const params = new URLSearchParams({ path });
    if (uid) params.set("user_id", uid);
    try {
      const r = await fetch(API + "/memory/read?" + params);
      const d = await r.json();
      memoryReadOut.textContent = d.content != null ? d.content : JSON.stringify(d);
      memoryContent.value = d.content != null ? d.content : "";
    } catch (e) {
      memoryReadOut.textContent = "Ошибка: " + e.message;
    }
  });

  memoryWriteBtn.addEventListener("click", async function () {
    const uid = (userId.value || "").trim() || null;
    const body = { path: (memoryPath.value || "").trim() || "/memories/preferences.txt", content: memoryContent.value };
    if (uid) body.user_id = uid;
    try {
      const r = await fetch(API + "/memory/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      memoryReadOut.textContent = r.ok ? "Записано." : ("Ошибка: " + (d.detail || JSON.stringify(d)));
    } catch (e) {
      memoryReadOut.textContent = "Ошибка: " + e.message;
    }
  });
})();
