const state = { username: null, password: null, role: null, items: [], categories: [], cart: new Map(), category: 'All', sessions: [], sessionId: null, checkoutInProgress: false, checkoutKey: null, checkoutFingerprint: null };
const imageUrls = {
  'Masala Dosa': 'photo-1630383249896-424e482df921', 'Paneer Biryani': 'photo-1563379091339-03246963d96c',
  'Idli Sambar': 'photo-1589301760014-d929f3979dbc', 'Chole Bhature': 'photo-1626132647523-66f5bf380027',
  'Veg Hakka Noodles': 'photo-1585032226651-759b368d7246', 'Chicken Tikka Roll': 'photo-1603894584373-5ac82b2ae398',
  'Mango Lassi': 'photo-1546173159-315724a31696', 'Gulab Jamun': 'photo-1666190092159-9bdf1e8e7c56',
  'Palak Paneer': 'photo-1631452180519-c014fe946bc7', 'Filter Coffee': 'photo-1570968915860-54d5c301fa9f'
};
const $ = (selector) => document.querySelector(selector);
const money = (value) => `₹${Number(value).toFixed(0)}`;

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.username) headers.set('Authorization', `Basic ${btoa(`${state.username}:${state.password}`)}`);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...options, headers });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || payload.detail || 'Request could not be completed.');
  return payload;
}

function setSignedIn(user) {
  state.username = user.username;
  state.password = user.password;
  state.role = user.role;
  $('#auth-area').replaceChildren();
  const label = document.createElement('span'); label.className = 'signed-label'; label.textContent = user.username;
  const signout = document.createElement('button'); signout.className = 'button button-dark'; signout.textContent = 'Sign out';
  signout.addEventListener('click', () => { state.username = state.password = state.role = null; state.sessionId = null; $('#auth-area').replaceChildren(); const button = document.createElement('button'); button.id = 'login-open'; button.className = 'button button-dark'; button.textContent = 'Sign in'; button.addEventListener('click', openLogin); $('#auth-area').append(button); $('#admin-panel').hidden = true; renderOrders([]); renderCart(); });
  $('#auth-area').append(label, signout);
  $('#admin-panel').hidden = user.role !== 'admin';
}

function openLogin() { $('#login-dialog').showModal(); }
$('#login-open').addEventListener('click', openLogin);
$('#login-close').addEventListener('click', () => $('#login-dialog').close());
$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const username = $('#username').value.trim(), password = $('#password').value;
  state.username = username; state.password = password;
  try { const user = await api('/api/me'); setSignedIn({ ...user, password }); $('#login-dialog').close(); $('#login-error').textContent = ''; await Promise.all([loadOrders(), loadSessions()]); }
  catch (error) { state.username = state.password = null; $('#login-error').textContent = error.message; }
});

async function loadMenu() {
  try {
    if (!state.categories.length) {
      const allItems = await api('/api/menu_items');
      state.categories = [...new Set(allItems.map((item) => item.category))];
    }
    const query = new URLSearchParams();
    if (state.category !== 'All') query.set('category', state.category);
    if ($('#veg-only').checked) query.set('vegetarian', 'true');
    if ($('#max-price').value) query.set('max_price', $('#max-price').value);
    if ($('#search').value.trim()) query.set('keyword', $('#search').value.trim());
    state.items = await api(`/api/menu_items?${query}`); renderMenu(); $('#catalog-status').textContent = `${state.items.length} dishes available`;
  }
  catch (error) { $('#catalog-status').textContent = error.message; }
}
function renderCategories() {
  const categories = ['All', ...state.categories];
  const container = $('#category-filters'); container.replaceChildren();
  categories.forEach((category) => { const button = document.createElement('button'); button.textContent = category; button.className = state.category === category ? 'active' : ''; button.addEventListener('click', () => { state.category = category; loadMenu(); }); container.append(button); });
}
function renderMenu() {
  renderCategories();
  const grid = $('#menu-grid'); grid.replaceChildren();
  if (!state.items.length) { const empty = document.createElement('p'); empty.className = 'quiet-empty'; empty.textContent = 'No dishes match those filters.'; grid.append(empty); return; }
  state.items.forEach((item, index) => {
    const card = document.createElement('article'); card.className = 'food-card'; card.style.animationDelay = `${Math.min(index * 35, 200)}ms`;
    const image = document.createElement('img'); image.className = 'food-photo'; image.alt = item.name; image.loading = 'lazy'; image.src = `https://images.unsplash.com/${imageUrls[item.name] || 'photo-1547592180-85f173990554'}?auto=format&fit=crop&w=700&q=80`; image.onerror = () => { image.onerror = null; image.src = 'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=700&q=80'; };
    const topline = document.createElement('div'); topline.className = 'food-topline'; const category = document.createElement('span'); category.className = 'food-category'; category.textContent = item.category;
    topline.append(category); if (item.is_vegetarian) { const veg = document.createElement('span'); veg.className = 'veg-tag'; veg.setAttribute('aria-label', 'Vegetarian'); topline.append(veg); }
    const title = document.createElement('h3'); title.textContent = item.name;
    const description = document.createElement('p'); description.className = 'food-description'; description.textContent = item.description;
    const bottom = document.createElement('div'); bottom.className = 'food-bottom'; const priceGroup = document.createElement('div'); const price = document.createElement('div'); price.className = 'food-price'; price.textContent = money(item.price); const stock = document.createElement('div'); stock.className = 'availability'; stock.textContent = item.portions > 0 ? `${item.portions} portions` : 'Sold out'; priceGroup.append(price, stock);
    const add = document.createElement('button'); add.className = 'add-button'; add.textContent = '+'; add.title = `Add ${item.name} to your order`; add.disabled = item.portions < 1; add.addEventListener('click', () => addToCart(item)); bottom.append(priceGroup, add);
    card.append(image, topline, title, description);
    if (state.role === 'admin') {
      const controls = document.createElement('div'); controls.className = 'admin-item-controls';
      const edit = document.createElement('button'); edit.className = 'text-button'; edit.textContent = 'Edit'; edit.addEventListener('click', () => editMenuItem(item));
      const disable = document.createElement('button'); disable.className = 'text-button'; disable.textContent = 'Disable'; disable.addEventListener('click', () => disableMenuItem(item));
      controls.append(edit, disable); card.append(controls);
    }
    card.append(bottom); grid.append(card);
  });
}

async function editMenuItem(item) {
  const name = prompt('Dish name', item.name); if (name === null) return;
  const category = prompt('Category', item.category); if (category === null) return;
  const price = prompt('Price in INR', item.price); if (price === null) return;
  const portions = prompt('Available portions', item.portions); if (portions === null) return;
  const description = prompt('Description', item.description); if (description === null) return;
  const is_vegetarian = confirm('Is this dish vegetarian?');
  try { await api(`/api/menu_items/${item.id}`, { method: 'PUT', body: JSON.stringify({ name, category, price: Number(price), portions: Number(portions), description, is_vegetarian }) }); await loadMenu(); }
  catch (error) { alert(error.message); }
}
async function disableMenuItem(item) { if (!confirm(`Disable ${item.name} from the menu?`)) return; try { await api(`/api/menu_items/${item.id}`, { method: 'DELETE' }); await loadMenu(); } catch (error) { alert(error.message); } }

function addToCart(item, change = 1) {
  const current = state.cart.get(item.id)?.quantity || 0, quantity = current + change;
  if (quantity < 1) state.cart.delete(item.id); else if (quantity <= Math.min(10, item.portions)) state.cart.set(item.id, { item, quantity });
  renderCart();
}
function renderCart() {
  const container = $('#cart-lines'); container.replaceChildren(); let count = 0, total = 0;
  if (!state.cart.size) { const empty = document.createElement('p'); empty.className = 'empty-cart'; empty.textContent = 'Your next favorite goes here.'; container.append(empty); }
  state.cart.forEach(({ item, quantity }) => {
    count += quantity; total += Number(item.price) * quantity;
    const row = document.createElement('div'); row.className = 'cart-line'; const name = document.createElement('span'); name.textContent = item.name; const amount = document.createElement('strong'); amount.textContent = money(Number(item.price) * quantity);
    const actions = document.createElement('div'); actions.className = 'cart-actions'; const less = document.createElement('button'); less.textContent = '−'; less.setAttribute('aria-label', `Remove one ${item.name}`); less.addEventListener('click', () => addToCart(item, -1)); const qty = document.createElement('span'); qty.textContent = quantity; const more = document.createElement('button'); more.textContent = '+'; more.setAttribute('aria-label', `Add one ${item.name}`); more.disabled = quantity >= Math.min(10, item.portions); more.addEventListener('click', () => addToCart(item)); actions.append(less, qty, more); row.append(name, amount, actions); container.append(row);
  });
  $('#cart-count').textContent = count; $('#cart-total').textContent = money(total); $('#checkout').disabled = count === 0 || !state.username;
  $('#checkout').title = state.username ? '' : 'Sign in to place an order';
}
$('#veg-only').addEventListener('change', loadMenu); $('#max-price').addEventListener('input', debounce(loadMenu, 250)); $('#search').addEventListener('input', debounce(loadMenu, 250));
$('#checkout').addEventListener('click', async () => {
  if (state.checkoutInProgress || !state.cart.size) return;
  const fingerprint = JSON.stringify([...state.cart.values()].map(({ item, quantity }) => [item.id, quantity]));
  if (state.checkoutFingerprint !== fingerprint) { state.checkoutFingerprint = fingerprint; state.checkoutKey = crypto.randomUUID(); }
  state.checkoutInProgress = true;
  const button = $('#checkout'); button.disabled = true;
  try { const order = await api('/api/orders', { method: 'POST', headers: { 'Idempotency-Key': state.checkoutKey }, body: JSON.stringify({ lines: [...state.cart.values()].map(({ item, quantity }) => ({ item_id: item.id, quantity })) }) }); state.cart.clear(); state.checkoutKey = state.checkoutFingerprint = null; $('#order-status').textContent = `Order #${order.id} confirmed. Total ${money(order.total)}.`; renderCart(); await Promise.all([loadMenu(), loadOrders()]); }
  catch (error) { $('#order-status').textContent = error.message; }
  finally { state.checkoutInProgress = false; button.disabled = false; renderCart(); }
});

async function loadOrders() { if (!state.username) return; try { renderOrders(await api('/api/orders')); } catch (error) { $('#orders-list').textContent = error.message; } }
function renderOrders(orders) {
  const list = $('#orders-list'); list.replaceChildren();
  if (!orders.length) { const empty = document.createElement('p'); empty.className = 'quiet-empty'; empty.textContent = state.username ? 'No orders yet. Your first good meal is waiting.' : 'Sign in to see your order history.'; list.append(empty); return; }
  orders.forEach((order) => { const card = document.createElement('article'); card.className = 'order-card'; const info = document.createElement('div'); const title = document.createElement('h3'); title.textContent = `Order #${order.id} · ${money(order.total)}`; const details = document.createElement('p'); details.className = 'order-meta'; details.textContent = `${order.lines.map((line) => `${line.quantity} × ${line.item_name}`).join(', ')}\n${new Date(order.created_at).toLocaleString()}`; info.append(title, details); if (order.status === 'CONFIRMED') { const cancel = document.createElement('button'); cancel.className = 'order-cancel'; cancel.textContent = 'Cancel order'; cancel.addEventListener('click', async () => { try { await api(`/api/orders/${order.id}/cancel`, { method: 'POST' }); await Promise.all([loadOrders(), loadMenu()]); } catch (error) { alert(error.message); } }); info.append(cancel); } const status = document.createElement('span'); status.className = 'order-status'; status.textContent = order.status; card.append(info, status); list.append(card); });
}
$('#refresh-orders').addEventListener('click', loadOrders);
$('#menu-form').addEventListener('submit', async (event) => { event.preventDefault(); const data = new FormData(event.currentTarget); const payload = Object.fromEntries(data.entries()); payload.price = Number(payload.price); payload.portions = Number(payload.portions); payload.is_vegetarian = data.has('is_vegetarian'); try { await api('/api/menu_items', { method: 'POST', body: JSON.stringify(payload) }); event.currentTarget.reset(); state.categories = []; await loadMenu(); } catch (error) { alert(error.message); } });
$('#document-form').addEventListener('submit', async (event) => { event.preventDefault(); const file = $('#knowledge-file').files[0]; if (!file) return; const body = new FormData(); body.append('file', file); $('#document-status').textContent = 'Uploading…'; try { const result = await api('/api/documents', { method: 'POST', body }); $('#document-status').textContent = `${result.filename}: ${result.chunks} chunks${result.vector_indexed ? ' indexed' : ' saved for local retrieval'}`; event.currentTarget.reset(); } catch (error) { $('#document-status').textContent = error.message; } });

function openChat() { if (!state.username) { openLogin(); $('#login-error').textContent = 'Sign in to use persistent chat.'; return; } $('#chat-drawer').classList.add('open'); $('#chat-drawer').setAttribute('aria-hidden', 'false'); $('#drawer-backdrop').classList.add('visible'); loadSessions(); }
function closeChat() { $('#chat-drawer').classList.remove('open'); $('#chat-drawer').setAttribute('aria-hidden', 'true'); $('#drawer-backdrop').classList.remove('visible'); }
$('#open-chat').addEventListener('click', openChat); $('#close-chat').addEventListener('click', closeChat); $('#drawer-backdrop').addEventListener('click', closeChat);
async function loadSessions() { if (!state.username) return; try { state.sessions = await api('/api/chat/sessions'); const select = $('#session-select'); select.replaceChildren(); const fresh = document.createElement('option'); fresh.value = ''; fresh.textContent = 'Choose a conversation'; select.append(fresh); state.sessions.forEach((session) => { const option = document.createElement('option'); option.value = session.id; option.textContent = session.title; select.append(option); }); if (state.sessionId) select.value = String(state.sessionId); } catch { /* Chat remains available for a new session. */ } }
async function chooseSession(id) { state.sessionId = id ? Number(id) : null; $('#chat-log').replaceChildren(); $('#pending-action').hidden = true; if (!state.sessionId) return; try { const history = await api(`/api/chat/sessions/${state.sessionId}/messages`); history.messages.forEach(renderMessage); if (history.pending_action) renderPending(history.pending_action); } catch (error) { $('#chat-status').textContent = error.message; } }
$('#session-select').addEventListener('change', (event) => chooseSession(event.target.value));
$('#new-session').addEventListener('click', async () => { try { const session = await api('/api/chat/sessions', { method: 'POST', body: JSON.stringify({ title: 'New conversation' }) }); state.sessionId = session.id; await loadSessions(); $('#session-select').value = String(session.id); $('#chat-log').replaceChildren(); $('#pending-action').hidden = true; } catch (error) { $('#chat-status').textContent = error.message; } });
function renderMessage(message) { const bubble = document.createElement('div'); bubble.className = message.role === 'user' ? 'user-message' : 'assistant-message'; bubble.textContent = message.content; $('#chat-log').append(bubble); const sources = message.metadata_json?.citations || []; if (sources.length) { const chips = document.createElement('div'); chips.className = 'source-list'; sources.forEach((source) => { const chip = document.createElement('span'); chip.className = 'source-chip'; chip.textContent = `${source.filename}${source.reference ? ` · ${source.reference}` : ''}`; chips.append(chip); }); $('#chat-log').append(chips); } $('#chat-log').scrollTop = $('#chat-log').scrollHeight; }
$('#chat-form').addEventListener('submit', async (event) => { event.preventDefault(); const content = $('#chat-input').value.trim(); if (!content) return; if (!state.sessionId) { try { const session = await api('/api/chat/sessions', { method: 'POST', body: JSON.stringify({ title: content.slice(0, 60) }) }); state.sessionId = session.id; await loadSessions(); $('#session-select').value = String(session.id); } catch (error) { $('#chat-status').textContent = error.message; return; } } renderMessage({ role: 'user', content }); $('#chat-input').value = ''; $('#chat-status').textContent = 'Thinking…'; try { const result = await api(`/api/chat/sessions/${state.sessionId}/messages`, { method: 'POST', body: JSON.stringify({ content }) }); renderMessage(result); $('#chat-status').textContent = ''; if (result.pending_action) renderPending(result.pending_action); } catch (error) { $('#chat-status').textContent = error.message; } });
function renderPending(action) { const container = $('#pending-action'); container.replaceChildren(); const text = document.createElement('p'); text.textContent = action.summary; const yes = document.createElement('button'); yes.className = 'confirm-action'; yes.textContent = 'Confirm'; const no = document.createElement('button'); no.className = 'reject-action'; no.textContent = 'Reject'; for (const [button, confirm] of [[yes, true], [no, false]]) button.addEventListener('click', async () => { button.disabled = true; try { const result = await api(`/api/chat/actions/${action.id}/confirm`, { method: 'POST', body: JSON.stringify({ confirm }) }); renderMessage(result); container.hidden = true; await Promise.all([loadOrders(), loadMenu()]); } catch (error) { $('#chat-status').textContent = error.message; button.disabled = false; } }); container.append(text, yes, no); container.hidden = false; }
function debounce(callback, delay) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => callback(...args), delay); }; }

renderCart(); loadMenu();
