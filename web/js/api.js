// 데이터 접근 계층.
// API_BASE가 비어 있으면 data.js의 예시 데이터를 쓰고,
// 주소를 넣으면 그 서버(예: API Gateway → Lambda)에서 받아옵니다.
//
// 기대하는 응답 형식  GET {API_BASE}/items  →  { "items": [ Item, ... ] }
// Item = { id, category, subtype, source, title, fields: [], date, deadline?, url, repo? }

const API_BASE = ''; // 예: 'https://xxxx.execute-api.ap-northeast-2.amazonaws.com/prod'

window.Api = {
  usingSample: !API_BASE,

  async listItems() {
    if (!API_BASE) return structuredClone(window.SAMPLE_ITEMS);
    const res = await fetch(`${API_BASE}/items`);
    if (!res.ok) throw new Error(`목록을 불러오지 못했어요 (HTTP ${res.status})`);
    const body = await res.json();
    return body.items || [];
  },
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
