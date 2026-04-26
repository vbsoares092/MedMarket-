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

/* ══════════════════════════════════════════════════════════════════════════
   MedCart — LocalStorage-based scheduling cart
   Allows adding a consulta + one or more exames from the same clinic.
   ══════════════════════════════════════════════════════════════════════════ */
const MedCart = (() => {
  'use strict';

  const KEY = 'medmarket_cart';

  function _load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || { clinic_id: null, clinic_name: '', items: [] }; }
    catch { return { clinic_id: null, clinic_name: '', items: [] }; }
  }

  function _save(cart) {
    localStorage.setItem(KEY, JSON.stringify(cart));
  }

  function _esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function _fmt(n) {
    return 'R$ ' + Number(n).toLocaleString('pt-BR');
  }

  function updateBadge() {
    const cart  = _load();
    const badge = document.getElementById('cartBadge');
    if (!badge) return;
    const count = (cart.items || []).length;
    badge.textContent = count;
    badge.style.display = count > 0 ? 'block' : 'none';
  }

  function render() {
    const cart   = _load();
    const body   = document.getElementById('cartBody');
    const ftr    = document.getElementById('cartFtr');
    const empty  = document.getElementById('cartEmpty');
    const total  = document.getElementById('cartTotal');
    if (!body) return;

    const items  = cart.items || [];
    if (items.length === 0) {
      if (empty)  empty.style.display  = '';
      if (ftr)    ftr.style.display    = 'none';
      // Remove previous item nodes
      body.querySelectorAll('.cart-item,.cart-clinic-label').forEach(el => el.remove());
      lucide.createIcons();
      return;
    }

    if (empty) empty.style.display = 'none';
    if (ftr)   ftr.style.display   = '';

    // Clear previous items
    body.querySelectorAll('.cart-item,.cart-clinic-label').forEach(el => el.remove());

    // Clinic label
    const label = document.createElement('div');
    label.className = 'cart-clinic-label';
    label.innerHTML = `<i data-lucide="building-2"></i>${_esc(cart.clinic_name)}`;
    body.prepend(label);

    let sum = 0;
    items.forEach((item, idx) => {
      sum += Number(item.price) || 0;
      const isExame = item.tipo === 'exame';
      const div = document.createElement('div');
      div.className = 'cart-item';
      div.dataset.idx = idx;
      div.innerHTML = `
        <div class="cart-item-icon cart-item-icon--${item.tipo}">
          <i data-lucide="${isExame ? 'microscope' : 'stethoscope'}"></i>
        </div>
        <div class="cart-item-info">
          <div class="cart-item-name">${_esc(item.title)}</div>
          <div class="cart-item-meta">
            <span class="cart-item-tipo cart-item-tipo--${item.tipo}">${_esc(item.tipo)}</span>
            ${item.specialty ? `<span>${_esc(item.specialty)}</span>` : ''}
          </div>
        </div>
        <div class="cart-item-price">${_fmt(item.price)}</div>
        <button class="cart-item-remove" title="Remover" onclick="MedCart.remove(${idx})">
          <i data-lucide="x"></i>
        </button>`;
      body.appendChild(div);
    });

    if (total) total.textContent = _fmt(sum);
    lucide.createIcons();
  }

  function add(btn) {
    const id         = Number(btn.dataset.id);
    const title      = btn.dataset.title      || '';
    const tipo       = btn.dataset.tipo       || 'consulta';
    const price      = Number(btn.dataset.price) || 0;
    const specialty  = btn.dataset.specialty  || '';
    const clinicId   = Number(btn.dataset.clinicId);
    const clinicName = btn.dataset.clinicName || '';

    const cart = _load();

    // If cart belongs to a different clinic, confirm clear
    if (cart.clinic_id && cart.clinic_id !== clinicId && cart.items.length > 0) {
      if (!confirm(`Seu carrinho contém itens de "${cart.clinic_name}". Deseja limpá-lo e adicionar da nova clínica?`)) return;
      cart.items = [];
    }

    // Check if already in cart
    const exists = cart.items.some(i => i.id === id);
    if (exists) {
      open();
      return;
    }

    cart.clinic_id   = clinicId;
    cart.clinic_name = clinicName;
    cart.items.push({ id, title, tipo, price, specialty });
    _save(cart);

    // Visual feedback on button
    btn.classList.add('btn-add-cart--added');
    const origHTML = btn.innerHTML;
    btn.innerHTML = btn.innerHTML.replace(/Adicionar ao Carrinho|<i[^>]*><\/i>\s*$/g, '')
      .trim();
    // Simpler: just swap icon+text
    const icoEl = btn.querySelector('i');
    if (icoEl) { icoEl.setAttribute('data-lucide', 'check'); lucide.createIcons(); }
    const textNode = [...btn.childNodes].find(n => n.nodeType === 3 && n.textContent.trim());
    if (textNode) textNode.textContent = ' Adicionado';

    updateBadge();
    render();
    // Auto-open drawer
    open();
  }

  function remove(idx) {
    const cart = _load();
    cart.items.splice(idx, 1);
    if (cart.items.length === 0) { cart.clinic_id = null; cart.clinic_name = ''; }
    _save(cart);
    updateBadge();
    render();
    // Re-enable cart buttons on page
    _syncButtons();
  }

  function clear() {
    _save({ clinic_id: null, clinic_name: '', items: [] });
    updateBadge();
    render();
    _syncButtons();
  }

  function _syncButtons() {
    const cart = _load();
    document.querySelectorAll('.btn-add-cart').forEach(btn => {
      const id = Number(btn.dataset.id);
      const inCart = (cart.items || []).some(i => i.id === id);
      if (!inCart) {
        btn.classList.remove('btn-add-cart--added');
        lucide.createIcons();
      }
    });
  }

  function open() {
    const drawer  = document.getElementById('cartDrawer');
    const overlay = document.getElementById('cartOverlay');
    if (drawer)  drawer.classList.add('cart-open');
    if (overlay) overlay.classList.add('cart-open');
    render();
  }

  function close() {
    const drawer  = document.getElementById('cartDrawer');
    const overlay = document.getElementById('cartOverlay');
    if (drawer)  drawer.classList.remove('cart-open');
    if (overlay) overlay.classList.remove('cart-open');
  }

  function checkout() {
    const cart = _load();
    if (!cart.items || cart.items.length === 0) return;
    // Navigate to the first item's listing page so user can pick date/time
    const first = cart.items[0];
    window.location.href = '/listing/' + first.id + '?from_cart=1';
  }

  // Init: update badge on page load and sync buttons
  document.addEventListener('DOMContentLoaded', () => {
    updateBadge();
    // Mark already-in-cart buttons
    const cart = _load();
    document.querySelectorAll('.btn-add-cart').forEach(btn => {
      const id = Number(btn.dataset.id);
      if ((cart.items || []).some(i => i.id === id)) {
        btn.classList.add('btn-add-cart--added');
      }
    });
  });

  return { add, remove, clear, open, close, checkout, updateBadge, render };
})();
