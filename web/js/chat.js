// 챗봇: 오른쪽 아래 "AI에게 물어보기" 버튼으로 여는 대화 창.
// 질문을 POST /chat으로 보내면 서버(api/src/chat.py)가 모아 둔 글 중에서 골라 Gemini로 답합니다.
// 로그인한 사용자만 쓸 수 있고, 대화는 이 페이지를 열어 둔 동안만 기억합니다 (새로고침하면 사라짐).
// 로그인 상태가 바뀌면 app.js가 'csradar:auth' 이벤트를 보내 이 창도 다시 그립니다.

(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const CAT = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));
  const HISTORY = 6; // 서버에 같이 보낼 앞선 대화 수 (api/src/chat.py의 MAX_HISTORY와 같게)
  const SUGGESTIONS = ['이번 주에 마감하는 대회 알려줘', 'AI 분야 신입 채용 있어?', '장학금 관련 학교 공지 찾아줘'];

  const messages = []; // { role: 'user' | 'model', text, items?, error? }
  let busy = false;
  let remaining = null;

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const daysLeft = (s) => { const [y, m, d] = String(s).split('-').map(Number); return Math.round((new Date(y, m - 1, d) - today) / 86400000); };

  function itemCard(it) {
    const safe = /^https?:\/\//i.test(it.url || '');
    const cat = CAT[it.category] ? CAT[it.category].label : '';
    let due = '';
    if (it.deadline) {
      const n = daysLeft(it.deadline);
      due = `<span class="chat-item-due ${n <= 7 ? 'soon' : ''}">${n < 0 ? '마감' : n === 0 ? 'D-Day' : `D-${n}`}</span>`;
    }
    return `<a class="chat-item" ${safe ? `href="${esc(it.url)}" target="_blank" rel="noopener noreferrer"` : ''}>
      <span class="chat-item-meta">${esc(cat)} · ${esc(it.source || '')}${due}</span>
      <span class="chat-item-title">${esc(it.title || '')}</span></a>`;
  }

  function bubble(m) {
    const text = esc(m.text).replace(/\n/g, '<br>');
    if (m.role === 'user') return `<div class="chat-msg user"><p>${text}</p></div>`;
    const items = m.items && m.items.length ? `<div class="chat-items">${m.items.map(itemCard).join('')}</div>` : '';
    return `<div class="chat-msg bot ${m.error ? 'error' : ''}"><p>${text}</p>${items}</div>`;
  }

  function renderLog() {
    const user = Auth.user();
    let html = `<div class="chat-msg bot"><p>안녕하세요! 찾고 싶은 공지, 대회, 채용 글을 편하게 물어보세요.</p></div>`;
    if (!messages.length && user) {
      html += `<div class="chat-suggest">${SUGGESTIONS.map((s) => `<button type="button" data-chat-suggest="${esc(s)}">${esc(s)}</button>`).join('')}</div>`;
    }
    html += messages.map(bubble).join('');
    if (busy) html += '<div class="chat-msg bot typing" aria-label="답을 만드는 중"><span></span><span></span><span></span></div>';
    $('chatLog').innerHTML = html;
    $('chatLog').scrollTop = $('chatLog').scrollHeight;
  }

  function renderFoot() {
    if (!Auth.configured) {
      $('chatFoot').innerHTML = '<p class="chat-note">챗봇은 배포한 뒤 js/api.js에 API_BASE, AUTH_BASE, AUTH_CLIENT_ID를 넣으면 쓸 수 있어요.</p>';
      return;
    }
    if (!Auth.user()) {
      $('chatFoot').innerHTML = `<p class="chat-note">로그인하면 AI에게 물어볼 수 있어요.</p>
        <button type="button" class="chat-login" data-open-login>로그인</button>`;
      return;
    }
    const left = remaining === null ? '' : `<span class="chat-left">오늘 ${remaining}번 더 물어볼 수 있어요</span>`;
    $('chatFoot').innerHTML = `<form class="chat-form" id="chatForm">
        <label class="sr-only" for="chatInput">질문</label>
        <textarea id="chatInput" rows="1" maxlength="500" placeholder="예: 다음 주까지 신청하는 해커톤" ${busy ? 'disabled' : ''}></textarea>
        <button type="submit" aria-label="보내기" ${busy ? 'disabled' : ''}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>
        </button>
      </form>${left}`;
  }

  function render() { renderLog(); renderFoot(); }

  function focusInput() { const input = $('chatInput'); if (input) input.focus(); }

  function send(text) {
    text = text.trim();
    if (!text || busy) return;
    // 앞선 대화: 오류 응답은 빼고 최근 HISTORY개
    const history = messages.filter((m) => !m.error).slice(-HISTORY).map((m) => ({ role: m.role, text: m.text }));
    messages.push({ role: 'user', text });
    busy = true;
    render();
    Api.chat(text, history)
      .then((res) => {
        messages.push({ role: 'model', text: res.answer, items: res.items || [] });
        if (typeof res.remaining === 'number') remaining = res.remaining;
      })
      .catch((err) => { messages.push({ role: 'model', text: err.message, error: true }); })
      .finally(() => { busy = false; render(); focusInput(); });
  }

  function setOpen(open) {
    $('chatPanel').hidden = !open;
    $('chatFab').setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('chat-open', open);
    if (open) { render(); focusInput(); } else { $('chatFab').focus(); }
  }

  $('chatFab').addEventListener('click', () => setOpen($('chatPanel').hidden));
  $('chatClose').addEventListener('click', () => setOpen(false));
  $('chatPanel').addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
  $('chatPanel').addEventListener('click', (e) => {
    const s = e.target.closest('[data-chat-suggest]');
    if (s) send(s.dataset.chatSuggest);
  });
  $('chatPanel').addEventListener('submit', (e) => {
    if (e.target.id !== 'chatForm') return;
    e.preventDefault();
    send($('chatInput').value);
  });
  $('chatPanel').addEventListener('keydown', (e) => {
    // Enter로 보내기, Shift+Enter는 줄바꿈 (한글 조합 중 Enter는 무시)
    if (e.target.id === 'chatInput' && e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send(e.target.value);
    }
  });
  $('chatPanel').addEventListener('input', (e) => {
    if (e.target.id !== 'chatInput') return;
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
  });
  window.addEventListener('csradar:auth', () => {
    if (!Auth.user()) { messages.length = 0; remaining = null; } // 로그아웃하면 대화도 지움
    if (!$('chatPanel').hidden) render();
  });
})();
