// 데이터 접근 계층.
// API_BASE가 비어 있으면 data.js의 예시 데이터를 쓰고,
// 주소를 넣으면 그 서버(예: API Gateway → Lambda)에서 받아옵니다.
//
// 기대하는 응답 형식  GET {API_BASE}/items  →  { "items": [ Item, ... ] }
// Item = { id, category, subtype, source, title, fields: [], date, deadline?, url, repo? }

const API_BASE = ''; // 예: 'https://xxxx.execute-api.us-east-1.amazonaws.com'

// 로그인 설정 (sam deploy가 끝나면 Outputs에 나오는 값). 비어 있으면 로그인 기능이 꺼집니다.
const AUTH_BASE = '';      // Outputs의 AuthUrl. 예: 'https://csradar-123456789012.auth.us-east-1.amazoncognito.com'
const AUTH_CLIENT_ID = ''; // Outputs의 AuthClientId

// 로그인이 필요한 API 호출: 토큰을 Authorization 헤더에 넣어 보냅니다.
async function authedFetch(path, options = {}) {
  const token = await Auth.token();
  if (!token) throw new Error('로그인이 필요해요.');
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  });
  const body = await res.json().catch(() => ({}));
  if (res.status === 401) { Auth.clear(); throw new Error('로그인이 만료됐어요. 다시 로그인해 주세요.'); }
  if (!res.ok) throw new Error(body.message || `요청에 실패했어요 (HTTP ${res.status})`);
  return body;
}

window.Api = {
  usingSample: !API_BASE,

  // 키워드 구독 (로그인 필요). 셋 다 { userId, keywords: [...] }를 돌려줍니다.
  listSubscriptions() { return authedFetch('/me/subscriptions'); },
  addSubscription(keyword) {
    return authedFetch('/me/subscriptions', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword }),
    });
  },
  removeSubscription(keyword) {
    return authedFetch(`/me/subscriptions?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE' });
  },

  // 챗봇 (로그인 필요). history = [{ role: 'user' | 'model', text }], school = 내 학교(없으면 null)
  // → { answer, items: [Item, ...], web, notice, remaining: 오늘 남은 질문 수 }
  chat(message, history, school) {
    return authedFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, school: school || null }),
    });
  },

  // 내 학교 설정 (로그인 필요). 둘 다 { school: '전북대' | 'other' | null, requestedSchool }
  getProfile() { return authedFetch('/me/profile'); },
  saveProfile(profile) {
    return authedFetch('/me/profile', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
  },

  async listItems() {
    if (!API_BASE) return structuredClone(window.SAMPLE_ITEMS);
    const res = await fetch(`${API_BASE}/items`);
    if (!res.ok) throw new Error(`목록을 불러오지 못했어요 (HTTP ${res.status})`);
    const body = await res.json();
    return body.items || [];
  },
};

// 내 학교: 로그인 없이도 쓰도록 브라우저에 저장하고, 로그인하면 서버(/me/profile)와 맞춥니다 (app.js).
// 값: SUBTYPES.univ의 학교 이름 | 'other'(목록에 없는 학교) | ''(정하지 않음)
window.MySchool = {
  KEY: 'csradar.school',
  get() {
    try {
      const s = JSON.parse(localStorage.getItem(this.KEY) || '{}');
      const ok = s.school === 'other' || SUBTYPES.univ.includes(s.school);
      return { school: ok ? s.school : '', requestedSchool: ok && s.school === 'other' ? s.requestedSchool || '' : '', asked: Boolean(s.asked) };
    } catch { return { school: '', requestedSchool: '', asked: false }; }
  },
  set(school, requestedSchool = '') {
    try { localStorage.setItem(this.KEY, JSON.stringify({ school, requestedSchool: school === 'other' ? requestedSchool : '', asked: true })); }
    catch { /* 저장 불가 환경 */ }
  },
  // 고르지 않고 "나중에"를 눌렀을 때: 다시 묻지 않도록 표시만
  skip() { const s = this.get(); this.set(s.school, s.requestedSchool); },
  // 챗봇에 보낼 학교: 목록에 있는 학교일 때만
  forChat() { const s = this.get().school; return SUBTYPES.univ.includes(s) ? s : null; },
};

// 북마크는 로그인 없이 쓰도록 브라우저에만 저장합니다.
window.Bookmarks = {
  KEY: 'csradar.bookmarks',
  all() {
    try { return new Set(JSON.parse(localStorage.getItem(this.KEY) || '[]')); }
    catch { return new Set(); }
  },
  toggle(id) {
    const set = this.all();
    set.has(id) ? set.delete(id) : set.add(id);
    try { localStorage.setItem(this.KEY, JSON.stringify([...set])); } catch { /* 저장 불가 환경 */ }
    return set;
  },
};
