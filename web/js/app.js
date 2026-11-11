(function () {
  const $ = (id) => document.getElementById(id);
  const CAT = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));
  const FIELD = Object.fromEntries(FIELDS.map((f) => [f.id, f]));
  const CAT_DESC = {
    all: '대학 소식, 공모전, 채용, 테크 트렌드를 한곳에서 봐요.',
    univ: '주요 대학 컴퓨터 관련 학과·사업단 공지',
    contest: '해커톤, 공모전, 경진대회, CTF',
    jobs: '인턴, 신입 공채, 채용연계형 프로그램',
    tech: 'GitHub 트렌딩, 최신 기술, 개발 이슈',
    saved: '북마크한 글을 모아 봐요. 이 브라우저에만 저장돼요.',
  };
  const SUBTYPE_LABEL = { univ: '학교', contest: '종류', jobs: '형태', tech: '구분' };

  const state = {
    items: [],
    view: 'all',          // all | univ | contest | jobs | tech | saved
    subtype: null,
    fields: new Set(),
    q: '',
    sort: 'latest',
    bookmarks: Bookmarks.all(),
  };

  // ── 날짜 유틸
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const toDate = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const daysLeft = (s) => Math.round((toDate(s) - today) / 86400000);
  const ddayText = (n) => (n < 0 ? '마감' : n === 0 ? 'D-Day' : `D-${n}`);
  const relDate = (s) => {
    const n = -daysLeft(s);
    if (n <= 0) return '오늘';
    if (n === 1) return '어제';
    if (n < 7) return `${n}일 전`;
    const d = toDate(s); return `${d.getMonth() + 1}.${d.getDate()}`;
  };
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const linkAttrs = (url) => (url && url !== '#' ? `href="${esc(url)}" target="_blank" rel="noopener"` : 'href="#" data-nolink');

  // ── 라우팅 (#all, #univ, #contest, #jobs, #tech, #saved)
  function readHash() {
    const h = location.hash.slice(1);
    const valid = ['all', 'saved', ...CATEGORIES.map((c) => c.id)];
    const next = valid.includes(h) ? h : 'all';
    if (next !== state.view) state.subtype = null;
    state.view = next;
  }

  // ── 필터링
  function filtered() {
    const q = state.q.trim().toLowerCase();
    let list = state.items.filter((it) => {
      if (state.view === 'saved') { if (!state.bookmarks.has(it.id)) return false; }
      else if (state.view !== 'all' && it.category !== state.view) return false;
      if (state.subtype && it.subtype !== state.subtype) return false;
      if (state.fields.size && !it.fields.some((f) => state.fields.has(f))) return false;
      if (q && !`${it.title} ${it.source} ${it.subtype}`.toLowerCase().includes(q)) return false;
      return true;
    });
    if (state.sort === 'deadline') {
      const key = (it) => (it.deadline && daysLeft(it.deadline) >= 0 ? daysLeft(it.deadline) : 9999);
      list.sort((a, b) => key(a) - key(b) || b.date.localeCompare(a.date));
    } else {
      list.sort((a, b) => b.date.localeCompare(a.date));
    }
    return list;
  }

  // ── 렌더링
  function renderTabs() {
    const counts = state.items.reduce((m, it) => ((m[it.category] = (m[it.category] || 0) + 1), m), {});
    const tabs = [{ id: 'all', label: '전체', n: state.items.length }, ...CATEGORIES.map((c) => ({ ...c, n: counts[c.id] || 0 }))];
    $('tabs').innerHTML = tabs.map((t) =>
      `<a class="tab" href="#${t.id}" style="--tab-color: var(--c-${t.id === 'all' ? 'univ' : t.id})" ${state.view === t.id ? 'aria-current="page"' : ''}>${t.label}<span class="n">${t.n}</span></a>`
    ).join('');
    $('savedCount').textContent = state.bookmarks.size;
  }

  function renderFilters() {
    const subs = SUBTYPES[state.view];
    $('subtypeRow').hidden = !subs;
    if (subs) {
      $('subtypeLabel').textContent = SUBTYPE_LABEL[state.view];
      $('subtypeChips').innerHTML = ['전체', ...subs].map((s) => {
        const on = s === '전체' ? !state.subtype : state.subtype === s;
        return `<button type="button" class="chip" data-subtype="${esc(s)}" aria-pressed="${on}">${esc(s)}</button>`;
      }).join('');
    }
    $('fieldChips').innerHTML = FIELDS.map((f) =>
      `<button type="button" class="chip" data-field="${f.id}" aria-pressed="${state.fields.has(f.id)}">${f.label}</button>`
    ).join('');
  }

  function itemHTML(it) {
    const cat = CAT[it.category];
    const dl = it.deadline ? daysLeft(it.deadline) : null;
    const dday = dl === null ? '' :
      `<span class="dday ${dl < 0 ? 'closed' : dl <= 7 ? 'soon' : ''}" title="마감 ${esc(it.deadline)}">${ddayText(dl)}</span>`;
    const repo = it.repo ? `<span class="sep">·</span><span class="repo-meta">${esc(it.repo.lang)} · ★ ${it.repo.starsToday} today</span>` : '';
    const saved = state.bookmarks.has(it.id);
    return `<li class="item" style="--cat-color: var(--c-${it.category})">
      <div>
        <div class="item-meta">
          <span class="cat">${cat.label}</span>
          <span>${esc(it.subtype)}</span><span class="sep">·</span>
          <span>${esc(it.source)}</span><span class="sep">·</span>
          <time datetime="${it.date}">${relDate(it.date)}</time>${repo}
        </div>
        <a class="item-title ${it.repo ? 'mono' : ''}" ${linkAttrs(it.url)}>${esc(it.title)}</a>
        <div class="tags">${it.fields.map((f) => `<span class="tag">#${FIELD[f].label}</span>`).join('')}</div>
      </div>
      <div class="item-side">
        ${dday || '<span></span>'}
        <button type="button" class="bm" data-bm="${it.id}" aria-pressed="${saved}" aria-label="${saved ? '북마크 해제' : '북마크'}">${saved ? '★' : '☆'}</button>
      </div>
    </li>`;
  }

  function renderList() {
    const list = filtered();
    const title = state.view === 'all' ? '전체' : state.view === 'saved' ? '북마크' : CAT[state.view].label;
    $('feedTitle').textContent = title;
    $('feedDesc').textContent = CAT_DESC[state.view];
    $('resultCount').textContent = `${list.length}건`;
    $('list').innerHTML = list.map(itemHTML).join('');
    $('list').hidden = list.length === 0;
    $('empty').hidden = list.length !== 0;
  }

  function renderRail() {
    const upcoming = state.items
      .filter((it) => it.deadline && daysLeft(it.deadline) >= 0)
      .sort((a, b) => daysLeft(a.deadline) - daysLeft(b.deadline))
      .slice(0, 6);
    $('deadlineList').innerHTML = upcoming.map((it) => {
      const n = daysLeft(it.deadline);
      return `<li><a ${linkAttrs(it.url)}><span><span class="t">${esc(it.title)}</span><span class="s">${CAT[it.category].label} · ${esc(it.source)}</span></span><span class="r ${n <= 7 ? 'soon' : ''}">${ddayText(n)}</span></a></li>`;
    }).join('');

    const repos = state.items.filter((it) => it.repo).sort((a, b) => b.repo.starsToday - a.repo.starsToday).slice(0, 5);
    $('repoList').innerHTML = repos.map((it) =>
      `<li><a ${linkAttrs(it.url)}><span><span class="t">${esc(it.title)}</span><span class="s">${esc(it.repo.lang)}</span></span><span class="r">★ ${it.repo.starsToday}</span></a></li>`
    ).join('');
  }

  function render() { renderTabs(); renderFilters(); renderList(); renderRail(); }

  // ── 이벤트
  document.addEventListener('click', (e) => {
    const sub = e.target.closest('[data-subtype]');
    if (sub) { const v = sub.dataset.subtype; state.subtype = v === '전체' ? null : v; renderFilters(); renderList(); return; }
    const field = e.target.closest('[data-field]');
    if (field) { const f = field.dataset.field; state.fields.has(f) ? state.fields.delete(f) : state.fields.add(f); renderFilters(); renderList(); return; }
    const bm = e.target.closest('[data-bm]');
    if (bm) { state.bookmarks = Bookmarks.toggle(bm.dataset.bm); renderTabs(); renderList(); return; }
    if (e.target.closest('[data-nolink]')) e.preventDefault(); // 예시 데이터라 원문 링크가 없음
  });
  $('search').addEventListener('input', (e) => { state.q = e.target.value; renderList(); });
  $('sort').addEventListener('change', (e) => { state.sort = e.target.value; renderList(); });
  $('resetBtn').addEventListener('click', () => {
    state.fields.clear(); state.subtype = null; state.q = ''; $('search').value = ''; renderFilters(); renderList();
  });
  window.addEventListener('hashchange', () => { readHash(); render(); window.scrollTo(0, 0); });

  // ── 시작
  readHash();
  Api.listItems()
    .then((items) => { state.items = items; render(); })
    .catch((err) => {
      $('list').hidden = true; $('empty').hidden = false;
      $('empty').innerHTML = `<p><b>${esc(err.message)}</b></p><p class="muted">js/api.js의 API_BASE 주소와 서버 상태를 확인해 주세요.</p>`;
    });
})();
