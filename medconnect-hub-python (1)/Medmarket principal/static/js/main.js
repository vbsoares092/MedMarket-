// Initialize Lucide icons
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();

  // Apply animation-delay from data-delay attribute (set by Jinja2 template)
  document.querySelectorAll("[data-delay]").forEach((el) => {
    el.style.animationDelay = el.dataset.delay + "s";
  });

  // Mobile menu toggle
  const mobileMenuBtn = document.getElementById("mobileMenuBtn");
  const mobileMenu = document.getElementById("mobileMenu");
  const menuIcon = document.getElementById("menuIcon");
  if (mobileMenuBtn && mobileMenu) {
    mobileMenuBtn.addEventListener("click", () => {
      const open = mobileMenu.style.display === "block";
      mobileMenu.style.display = open ? "none" : "block";
      menuIcon.setAttribute("data-lucide", open ? "menu" : "x");
      lucide.createIcons();
    });
  }

  // Chat panel
  const chatPanel = document.getElementById("chatPanel");
  const chatToggle = document.getElementById("chatToggle");
  const chatToggleMobile = document.getElementById("chatToggleMobile");
  const chatClose = document.getElementById("chatClose");

  function toggleChat() {
    chatPanel.classList.toggle("open");
    if (chatPanel.classList.contains("open")) scrollChatToBottom();
  }

  chatToggle?.addEventListener("click", toggleChat);
  chatToggleMobile?.addEventListener("click", toggleChat);
  chatClose?.addEventListener("click", () => chatPanel.classList.remove("open"));

  // Chat send
  const chatInput = document.getElementById("chatInput");
  const chatSend = document.getElementById("chatSend");
  const chatMessages = document.getElementById("chatMessages");

  function sendMessage() {
    const msg = chatInput?.value.trim();
    if (!msg) return;
    chatInput.value = "";

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok) appendChatMsg(data.message);
      });
  }

  function appendChatMsg(m) {
    const div = document.createElement("div");
    div.className = "chat-msg";
    div.innerHTML = `
      <div class="chat-avatar">${m.avatar}</div>
      <div class="chat-content">
        <div class="chat-meta">
          <span class="chat-user">${m.user}</span>
          <span class="chat-time">${m.time}</span>
        </div>
        <p class="chat-text">${escHtml(m.message)}</p>
      </div>`;
    chatMessages?.appendChild(div);
    scrollChatToBottom();
  }

  chatSend?.addEventListener("click", sendMessage);
  chatInput?.addEventListener("keydown", (e) => { if (e.key === "Enter") sendMessage(); });

  function scrollChatToBottom() {
    if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function escHtml(s) {
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }
});

// Debounced search (live filter on typing)
let searchTimer;
function debounceSearch(input) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    const form = document.getElementById("searchForm");
    if (form) form.submit();
  }, 400);
}
