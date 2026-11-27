(function () {
  const $ = (id) => document.getElementById(id);
  const CAT = Object.fromEntries(CATEGORIES.map((c) => [c.id, c]));
  const FIELD = Object.fromEntries(FIELDS.map((f) => [f.id, f]));
  const CAT_DESC = {
    all: '대학 소식, 공모전, 채용, 테크 트렌드를 한곳에서 봐요.',
    univ: `${SUBTYPES.univ.join('·')} 학교 공지`,
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
    region: null,         // 취업·인턴 탭의 지역 칩 (시·도)
    venue: null,          // 공모전·대회 탭의 진행 방식 칩 (online | offline)
    fields: new Set(),
    q: '',
    sort: 'latest',
    bookmarks: Bookmarks.all(),
    user: null,           // 로그인한 사용자 { name, method: 'discord' | 'email' }
    subs: null,           // 구독 키워드 목록 (불러오기 전에는 null)
    authMsg: '',          // 로그인·구독 관련 안내/오류 문구
    mySchool: MySchool.get().school, // 내 학교: 학교 이름 | 'other' | ''
    schoolMsg: '',        // 내 학교 저장 관련 안내
  };
  const isSchool = (s) => SUBTYPES.univ.includes(s);
  const hasRegion = (it) => Array.isArray(it.regions) && it.regions.length > 0;
  const VENUE_LABEL = { online: '온라인', offline: '오프라인', hybrid: '온·오프라인' };
  // 글 아래에 보여 줄 장소: "오프라인 · 서울", "서울·경기"
  const placeText = (it) => [VENUE_LABEL[it.venue], hasRegion(it) ? it.regions.join('·') : ''].filter(Boolean).join(' · ');

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
  const monthDay = (s) => { const d = toDate(s); return `${d.getMonth() + 1}.${d.getDate()}`; };
  const todayText = `${today.getMonth() + 1}월 ${today.getDate()}일 ${'일월화수목금토'[today.getDay()]}요일`;
  // 마감이 안 지난 글을 마감 가까운 순으로
  const upcoming = (list) => list.filter((it) => it.deadline && daysLeft(it.deadline) >= 0)
    .sort((a, b) => daysLeft(a.deadline) - daysLeft(b.deadline));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const linkAttrs = (url) => (url && url !== '#' ? `href="${esc(url)}" target="_blank" rel="noopener"` : 'href="#" data-nolink');

  // ── 라우팅 (#all, #univ, #contest, #jobs, #tech, #saved)
  function readHash() {
    const h = location.hash.slice(1);
    const valid = ['all', 'saved', ...CATEGORIES.map((c) => c.id)];
    const next = valid.includes(h) ? h : 'all';
    // 대학 소식 탭에 들어오면 내 학교 칩이 골라진 상태로 시작 (전체 칩을 누르면 모든 학교)
    if (next !== state.view) {
      state.subtype = next === 'univ' && isSchool(state.mySchool) ? state.mySchool : null;
      state.region = null; state.venue = null;
    }
    state.view = next;
  }

  // ── 필터링
  // 내 학교를 정했으면 "전체" 탭·마감 임박·탭 숫자에서 다른 학교 공지를 뺍니다.
  // ('other' = 목록에 없는 학교: 학교 공지를 모두 뺌. 대학 소식 탭과 북마크에서는 그대로 보임)
  const otherSchool = (it) => it.category === 'univ' && Boolean(state.mySchool) && it.subtype !== state.mySchool;

  function filtered() {
    const q = state.q.trim().toLowerCase();
    let list = state.items.filter((it) => {
      if (state.view === 'saved') { if (!state.bookmarks.has(it.id)) return false; }
      // 전체 탭: GitHub 저장소는 오른쪽 "오늘의 GitHub"에 있으니 목록에서는 뺌 (검색하면 나옴)
      else if (state.view === 'all') { if (otherSchool(it) || (it.repo && !q)) return false; }
      else if (it.category !== state.view) return false;
      if (state.subtype && it.subtype !== state.subtype) return false;
      // 지역·방식 정보가 없는 글은 걸러 내지 않음 (예전에 모은 글, 근무지를 안 적은 공고)
      if (state.region && hasRegion(it) && !it.regions.includes(state.region)) return false;
      if (state.venue && it.venue && it.venue !== 'hybrid' && it.venue !== state.venue) return false;
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
    const mine = state.items.filter((it) => !otherSchool(it)); // 내 학교를 정했으면 다른 학교 공지는 세지 않음
    const counts = mine.reduce((m, it) => ((m[it.category] = (m[it.category] || 0) + 1), m), {});
    const tabs = [{ id: 'all', label: '전체', n: mine.length }, ...CATEGORIES.map((c) => ({ ...c, n: counts[c.id] || 0 }))];
    const caret = '<svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    $('tabs').innerHTML = tabs.map((t) => {
      const hasMenu = Boolean(SUBTYPES[t.id]);
      const menuAttrs = hasMenu ? `data-cat="${t.id}" aria-controls="megaMenu" aria-expanded="${menu.open === t.id}"` : '';
      return `<a class="tab" href="#${t.id}" ${menuAttrs} ${state.view === t.id ? 'aria-current="page"' : ''}>${t.label}<span class="n">${t.n}</span>${hasMenu ? caret : ''}</a>`;
    }).join('');
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
    // 취업·인턴: 지역 칩 (내 학교 지역 먼저, 그다음 글이 있는 시·도) / 공모전·대회: 온라인·오프라인 칩
    const place = state.view === 'jobs' || state.view === 'contest';
    $('placeRow').hidden = !place;
    if (state.view === 'jobs') {
      const mine = SCHOOL_REGION[state.mySchool];
      const present = new Set(state.items.filter((it) => it.category === 'jobs' && hasRegion(it)).flatMap((it) => it.regions));
      const regions = REGIONS.filter((r) => r === mine || present.has(r)).sort((a, b) => (b === mine) - (a === mine));
      $('placeLabel').textContent = '지역';
      $('placeChips').innerHTML = [null, ...regions].map((r) =>
        `<button type="button" class="chip" data-region="${r || ''}" aria-pressed="${state.region === r}">${r ? esc(r) : '전체'}${r && r === mine ? '<span class="chip-note">내 학교</span>' : ''}</button>`
      ).join('');
    } else if (state.view === 'contest') {
      $('placeLabel').textContent = '방식';
      $('placeChips').innerHTML = [{ id: null, label: '전체' }, ...VENUES].map((v) =>
        `<button type="button" class="chip" data-venue="${v.id || ''}" aria-pressed="${state.venue === v.id}">${v.label}</button>`
      ).join('');
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
    const repo = it.repo ? `<span class="repo-meta">${esc(it.repo.lang)} · ★ ${it.repo.starsToday} today</span>` : '';
    const saved = state.bookmarks.has(it.id);
    // AI 요약 (크롤러가 새 글을 저장할 때 붙임). 없는 글은 제목만 보여 줍니다.
    const summary = Array.isArray(it.summary) && it.summary.length
      ? `<ul class="item-summary" aria-label="AI 요약">${it.summary.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>` : '';
    return `<li class="item" style="--cat-color: var(--c-${it.category})">
      <div>
        <div class="item-meta">
          <span class="badge"><span class="sr-only">${cat.label} </span>${esc(it.subtype)}</span>
          <span>${esc(it.source)}</span><span class="sep">·</span>
          <time datetime="${it.date}">${relDate(it.date)}</time>
        </div>
        <a class="item-title ${it.repo ? 'mono' : ''}" ${linkAttrs(it.url)}>${esc(it.title)}</a>
        ${summary}
        <div class="tags">${placeText(it) ? `<span class="place">${esc(placeText(it))}</span>` : ''}${it.fields.map((f) => `<span>#${FIELD[f].label}</span>`).join('')}${repo}</div>
      </div>
      <div class="item-side">
        ${dday || '<span></span>'}
        <button type="button" class="bm" data-bm="${it.id}" aria-pressed="${saved}" aria-label="${saved ? '북마크 해제' : '북마크'}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h12a1 1 0 0 1 1 1V21l-7-4.5L5 21V4.5a1 1 0 0 1 1-1z"/></svg></button>
      </div>
    </li>`;
  }

  function renderList() {
    const list = filtered();
    let title = state.view === 'all' ? '전체' : state.view === 'saved' ? '북마크' : CAT[state.view].label;
    if (state.view === 'all') {
      const mine = state.items.filter((it) => !otherSchool(it));
      const week = upcoming(mine).filter((it) => daysLeft(it.deadline) <= 7).length;
      title = `이번 주 마감 ${week}건, 모아 둔 글 ${mine.length}건`;
    }
    $('feedTitle').textContent = title;
    $('feedDesc').textContent = CAT_DESC[state.view];
    $('listTitle').textContent = state.view === 'all' ? '새 글' : '';
    // 지역·방식을 골랐을 때, 정보가 없어 함께 보이는 글 수를 알려 줌
    const unknown = state.region ? list.filter((it) => !hasRegion(it)).length
      : state.venue ? list.filter((it) => !it.venue).length : 0;
    const what = state.region ? '근무지' : '진행 방식';
    $('resultCount').textContent = `${list.length}건${unknown ? ` (${what} 정보가 없는 ${unknown}건 포함)` : ''}`;
    $('list').innerHTML = list.map(itemHTML).join('');
    $('list').hidden = list.length === 0;
    $('empty').hidden = list.length !== 0;
  }

  function renderRail() {
    const upcoming = state.items
      .filter((it) => it.deadline && daysLeft(it.deadline) >= 0 && !otherSchool(it))
      .sort((a, b) => daysLeft(a.deadline) - daysLeft(b.deadline))
      .slice(0, 6);
    $('deadlineList').innerHTML = upcoming.map((it) => {
      const n = daysLeft(it.deadline);
      return `<li><a ${linkAttrs(it.url)}><span><span class="t">${esc(it.title)}</span><span class="s">${CAT[it.category].label} · ${esc(it.source)}</span></span><span class="r ${n <= 7 ? 'soon' : ''}">${ddayText(n)}</span></a></li>`;
    }).join('');

    const repos = state.items.filter((it) => it.repo).sort((a, b) => b.repo.starsToday - a.repo.starsToday).slice(0, 5);
    $('repoList').innerHTML = repos.map((it, i) =>
      `<li><a ${linkAttrs(it.url)}><span class="rank">${i + 1}</span><span><span class="t">${esc(it.title)}</span><span class="s">${esc(it.repo.lang)}</span></span><span class="r">★ ${it.repo.starsToday}</span></a></li>`
    ).join('');
  }

  // ── 전체 탭 대시보드: 마감 카드 + 내 학교 새 공지
  function dlCardHTML(it) {
    const n = daysLeft(it.deadline);
    return `<a class="dl-card" ${linkAttrs(it.url)} style="--cat-color: var(--c-${it.category})">
      <span class="dl-top"><span class="dl-kind"><span class="sr-only">${CAT[it.category].label} </span>${esc(it.subtype)}</span><span class="dl-dday ${n <= 3 ? 'soon' : ''}">${ddayText(n)}</span></span>
      <span class="dl-title">${esc(it.title)}</span>
      <span class="dl-src">${esc(it.source)} · ${monthDay(it.deadline)} 마감</span>
    </a>`;
  }

  function renderDash() {
    const isAll = state.view === 'all';
    $('dash').hidden = !isAll;
    $('deadlinePanel').hidden = isAll; // 전체 탭에서는 위의 카드가 같은 역할
    $('schoolNews').hidden = true;
    if (!isAll) return;

    const soon = upcoming(state.items.filter((it) => !otherSchool(it))).slice(0, 4);
    $('dashCards').innerHTML = soon.length ? soon.map(dlCardHTML).join('') : '<p class="muted">다가오는 마감이 없어요.</p>';

    const s = state.mySchool;
    if (!isSchool(s)) return;
    const news = state.items.filter((it) => it.category === 'univ' && it.subtype === s)
      .sort((a, b) => b.date.localeCompare(a.date)).slice(0, 3);
    if (!news.length) return;
    $('schoolNews').hidden = false;
    $('schoolNews').innerHTML = `<div class="panel-head"><h2>${esc(s)} 새 공지</h2><a href="#univ">대학 소식 →</a></div>
      <ul class="news-list">${news.map((it) => {
        const first = Array.isArray(it.summary) && it.summary.length ? `<span class="s">${esc(it.summary[0])}</span>` : '';
        return `<li><a ${linkAttrs(it.url)}><span class="news-src">${esc(it.source.replace(s, '').trim() || it.source)}</span>
          <span><span class="t">${esc(it.title)}</span>${first}</span><span class="r">${relDate(it.date)}</span></a></li>`;
      }).join('')}</ul>`;
  }

  // ── 상단 탭 세부 메뉴 (데스크톱: 마우스를 올리면, 키보드: 탭으로 들어가면 열림)
  const menu = { open: null, timer: 0, skipFocus: false };

  function megaHTML(cat) {
    const inCat = state.items.filter((it) => it.category === cat);
    const subs = SUBTYPES[cat].map((s) => {
      const list = inCat.filter((it) => it.subtype === s);
      const next = upcoming(list)[0];
      const latest = list.map((it) => it.date).sort().pop();
      const note = next ? `가장 가까운 마감 ${ddayText(daysLeft(next.deadline))}` : latest ? `최근 글 ${relDate(latest)}` : '아직 글이 없어요';
      const mine = cat === 'univ' && s === state.mySchool ? '<span class="mega-mine">내 학교</span>' : '';
      return `<a class="mega-sub" href="#${cat}" data-go-cat="${cat}" data-go-sub="${esc(s)}">
        <span class="mega-sub-top"><b>${esc(s)}</b>${mine}<span class="n">${list.length}건</span></span>
        <span class="mega-sub-note">${note}</span></a>`;
    }).join('');
    // 오른쪽: 마감 가까운 글 2개 (마감 있는 글이 없으면 최신 글). 대학 소식은 내 학교 공지 먼저.
    const pool = cat === 'univ' && isSchool(state.mySchool) ? inCat.filter((it) => it.subtype === state.mySchool) : inCat;
    const soon = upcoming(pool);
    const picks = (soon.length ? soon : [...pool].sort((a, b) => b.date.localeCompare(a.date))).slice(0, 2);
    const pickTitle = soon.length ? '마감 임박' : '최근 글';
    return `<div class="mega-inner">
      <div class="mega-main">
        <div class="mega-head"><b>${CAT[cat].label}</b><a href="#${cat}" data-go-cat="${cat}" data-go-sub="">전체 ${inCat.length}건 보기 →</a></div>
        <div class="mega-subs">${subs}</div>
      </div>
      <div class="mega-side">
        <span class="mega-side-title">${pickTitle}</span>
        ${picks.map((it) => {
          const tag = it.deadline && daysLeft(it.deadline) >= 0 ? ddayText(daysLeft(it.deadline)) : esc(it.subtype);
          const hot = it.deadline && daysLeft(it.deadline) >= 0 && daysLeft(it.deadline) <= 7;
          return `<a class="mega-pick" ${linkAttrs(it.url)}><span class="mega-tag ${hot ? 'soon' : ''}">${tag}</span><span>${esc(it.title)}</span></a>`;
        }).join('') || '<p class="muted">아직 글이 없어요.</p>'}
      </div>
    </div>`;
  }

  function renderMenu() {
    const el = $('megaMenu');
    el.hidden = !menu.open || !state.items.length;
    el.innerHTML = el.hidden ? '' : megaHTML(menu.open);
    document.querySelectorAll('.tab[data-cat]').forEach((t) => t.setAttribute('aria-expanded', String(t.dataset.cat === menu.open)));
  }
  function openMenu(cat) { clearTimeout(menu.timer); if (menu.open !== cat) { menu.open = cat; renderMenu(); } }
  function closeMenu() { clearTimeout(menu.timer); if (menu.open) { menu.open = null; renderMenu(); } }

  // 피드 제목 위 "내 학교" 한 줄 (전체 탭에서는 오늘 날짜도)
  function renderSchoolLine() {
    const s = state.mySchool;
    const text = isSchool(s) ? `<b>내 학교: ${esc(s)}</b> · 대학 소식은 ${esc(s)} 공지만 보여요`
      : s === 'other' ? '<b>내 학교: 목록에 없음</b> · 전체 탭에서는 학교 공지를 빼고 보여요'
      : '내 학교를 정하면 우리 학교 공지만 모아 볼 수 있어요';
    const msg = state.schoolMsg ? ` <span class="school-msg">${esc(state.schoolMsg)}</span>` : '';
    const date = state.view === 'all' ? `<span class="today">${todayText}</span> · ` : '';
    $('schoolLine').innerHTML = `${date}${text} <button type="button" class="auth-link" data-open-school>${s ? '바꾸기' : '학교 고르기'}</button>${msg}`;
  }

  function render() { renderTabs(); renderFilters(); renderList(); renderDash(); renderRail(); renderSchoolLine(); renderMenu(); }

  // ── 로그인 · 키워드 구독
  const NOT_CONFIGURED = '로그인이 아직 연결되지 않았어요. 배포한 뒤 js/api.js에 API_BASE, AUTH_BASE, AUTH_CLIENT_ID를 넣어 주세요.';

  function renderAuth() {
    const msg = state.authMsg ? `<p class="panel-msg" role="status">${esc(state.authMsg)}</p>` : '';
    if (!state.user) {
      $('authBox').innerHTML = '<button type="button" class="login-btn" data-open-login>로그인</button>';
      $('subsBody').innerHTML = `<p class="panel-text">디스코드로 로그인하면 알림 받을 키워드를 여기서 관리할 수 있어요.</p>
        <button type="button" class="btn-discord" data-login-discord>디스코드로 로그인</button>${msg}`;
      return;
    }
    $('authBox').innerHTML = `<span class="user" title="${esc(state.user.name)}">${esc(state.user.name)}</span>
      <button type="button" class="logout-btn" data-logout>로그아웃</button>`;
    if (state.user.method === 'email') {
      // 키워드 알림은 디스코드 DM으로만 보내므로 이메일 가입자는 안내만 보여 줍니다.
      $('subsBody').innerHTML = `<p class="panel-text">키워드 알림은 디스코드 DM으로 보내요. 알림을 받으려면 디스코드로 로그인해 주세요.</p>
        <button type="button" class="btn-discord" data-login-discord>디스코드로 로그인</button>${msg}`;
      return;
    }
    const chips = state.subs === null ? '<p class="panel-text">불러오는 중…</p>'
      : state.subs.length === 0 ? '<p class="panel-text">아직 구독한 키워드가 없어요.</p>'
      : `<ul class="sub-chips">${state.subs.map((k) =>
          `<li class="sub-chip">${esc(k)}<button type="button" data-unsub="${esc(k)}" aria-label="${esc(k)} 구독 해지">×</button></li>`).join('')}</ul>`;
    $('subsBody').innerHTML = `<form class="subs-form" id="subsForm">
        <label class="sr-only" for="subsInput">구독할 키워드</label>
        <input id="subsInput" type="text" maxlength="30" placeholder="예: 해커톤" autocomplete="off" required>
        <button type="submit">추가</button>
      </form>${chips}${msg}`;
  }

  // 구독 API를 부르고 결과(전체 목록)로 화면을 다시 그립니다.
  function syncSubs(request) {
    state.authMsg = '';
    return request
      .then((res) => { state.subs = res.keywords; })
      .catch((err) => { state.authMsg = err.message; state.user = Auth.user(); if (state.subs === null) state.subs = []; })
      .finally(renderAuth);
  }

  // 로그인이 끝나면: 디스코드 사용자만 구독 목록을 불러옵니다 (이메일 가입자는 키워드 알림을 받을 수 없음).
  function afterLogin() {
    state.authMsg = '';
    state.user = Auth.user();
    state.subs = null;
    renderAuth();
    if (state.user && state.user.method === 'discord') syncSubs(Api.listSubscriptions());
    authChanged();
  }

  // 로그인 상태가 바뀌었음을 다른 화면(챗봇 등)에 알립니다.
  function authChanged() { window.dispatchEvent(new Event('csradar:auth')); syncSchool(); }

  // ── 내 학교
  // 브라우저에 저장하고, 로그인했으면 서버(/me/profile)에도 저장합니다.
  function applySchool(school, requested = '', sync = true) {
    MySchool.set(school, requested);
    state.mySchool = school;
    state.schoolMsg = '';
    if (state.view === 'univ') state.subtype = isSchool(school) ? school : null;
    render();
    if (sync && state.user && Auth.configured) {
      Api.saveProfile({ school: school || null, requestedSchool: requested || null })
        .catch(() => { state.schoolMsg = '서버에 저장하지 못했어요. 이 브라우저에는 저장됐어요.'; renderSchoolLine(); });
    }
  }

  // 로그인하면 서버 설정과 맞춥니다: 서버에 있으면 서버 값을 쓰고, 없으면 이 브라우저 값을 올립니다.
  function syncSchool() {
    if (!state.user || !Auth.configured) return;
    Api.getProfile()
      .then((p) => {
        if (p.school) { applySchool(p.school, p.requestedSchool || '', false); return; }
        const local = MySchool.get();
        if (local.school) Api.saveProfile({ school: local.school, requestedSchool: local.requestedSchool || null }).catch(() => {});
        else if (!local.asked) openSchool();
      })
      .catch(() => { /* 서버에 못 가도 브라우저 설정으로 계속 */ });
  }

  function openSchool() {
    const dialog = $('schoolDialog');
    if (dialog.open || $('authDialog').open) return;
    const cur = MySchool.get();
    dialog.innerHTML = `<div class="auth-head">
        <h2 id="schoolTitle">어느 학교 학생이세요?</h2>
        <button type="button" class="auth-close" data-school-close aria-label="닫기">×</button>
      </div>
      <p class="school-intro">대학 소식에서 우리 학교 공지만 모아 보여 드려요. 공모전·채용·테크 글은 그대로 다 보여요.</p>
      <div class="school-options" role="group" aria-label="학교">${SUBTYPES.univ.map((s) =>
        `<button type="button" class="school-option" data-school="${esc(s)}" aria-pressed="${cur.school === s}">${esc(s)}</button>`).join('')}</div>
      <div class="auth-or"><span>목록에 없나요?</span></div>
      <form class="auth-form" data-school-other>
        <label class="auth-field"><span>다니는 학교 (선택, 추가할 때 참고할게요)</span>
          <input name="requested" type="text" maxlength="30" placeholder="예: 서울대" autocomplete="organization" value="${esc(cur.requestedSchool)}"></label>
        <button type="submit" class="auth-submit secondary" aria-pressed="${cur.school === 'other'}">목록에 없는 학교로 설정</button>
      </form>
      <p class="auth-switch">${cur.school
        ? '<button type="button" class="auth-link" data-school="">학교 설정 지우기</button>'
        : '<button type="button" class="auth-link" data-school-close>나중에 할게요</button>'}</p>`;
    dialog.showModal();
    const picked = dialog.querySelector('[aria-pressed="true"]') || dialog.querySelector('.school-option');
    if (picked) picked.focus();
  }

  // 고르지 않고 닫아도 다시 묻지 않음
  $('schoolDialog').addEventListener('close', () => { if (!MySchool.get().asked) MySchool.skip(); });
  $('schoolDialog').addEventListener('click', (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });

  // ── 로그인 · 회원가입 창 (이메일)
  // 단계: login → (signup → confirm) | (forgot → reset). 비밀번호는 가입 직후 자동 로그인용으로 창이 열려 있는 동안만 기억합니다.
  const authForm = { mode: 'login', email: '', password: '', info: '' };
  let authBusy = false;

  const inputField = (label, attrs) => `<label class="auth-field"><span>${label}</span><input ${attrs}></label>`;
  const emailField = () => inputField('이메일', `name="email" type="email" autocomplete="email" maxlength="128" required value="${esc(authForm.email)}"`);
  const codeField = () => inputField('인증 코드', 'name="code" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" required');
  const pwHint = '<p class="auth-hint">8자 이상, 숫자를 하나 이상 넣어 주세요.</p>';
  const backToLogin = '<p class="auth-switch"><button type="button" class="auth-link" data-auth-mode="login">로그인으로 돌아가기</button></p>';

  const AUTH_VIEWS = {
    login: () => ({
      title: '로그인',
      fields: `${emailField()}${inputField('비밀번호', 'name="password" type="password" autocomplete="current-password" required')}`,
      submit: '로그인',
      after: `<p class="auth-switch"><button type="button" class="auth-link" data-auth-mode="forgot">비밀번호를 잊었어요</button></p>
        <div class="auth-or"><span>또는</span></div>
        <button type="button" class="btn-discord" data-login-discord>디스코드로 로그인</button>
        <p class="auth-switch">계정이 없나요? <button type="button" class="auth-link" data-auth-mode="signup">이메일로 회원가입</button></p>`,
    }),
    signup: () => ({
      title: '회원가입',
      fields: `${emailField()}
        ${inputField('비밀번호', 'name="password" type="password" autocomplete="new-password" minlength="8" required')}
        ${inputField('비밀번호 확인', 'name="password2" type="password" autocomplete="new-password" minlength="8" required')}${pwHint}`,
      submit: '가입하고 인증 코드 받기',
      after: `<p class="auth-note">키워드 알림(디스코드 DM)은 디스코드로 로그인해야 받을 수 있어요. 북마크는 로그인 없이도 쓸 수 있어요.</p>
        <p class="auth-switch">이미 계정이 있나요? <button type="button" class="auth-link" data-auth-mode="login">로그인</button></p>`,
    }),
    confirm: () => ({
      title: '이메일 인증',
      fields: codeField(),
      submit: '인증하고 로그인',
      after: `<p class="auth-switch">메일이 안 왔나요? <button type="button" class="auth-link" data-auth-resend>코드 다시 받기</button></p>${backToLogin}`,
    }),
    forgot: () => ({
      title: '비밀번호 찾기',
      fields: emailField(),
      submit: '인증 코드 받기',
      after: backToLogin,
    }),
    reset: () => ({
      title: '새 비밀번호 설정',
      fields: `${codeField()}${inputField('새 비밀번호', 'name="password" type="password" autocomplete="new-password" minlength="8" required')}${pwHint}`,
      submit: '비밀번호 바꾸고 로그인',
      after: backToLogin,
    }),
  };

  function setAuthMode(mode, info = '') {
    authForm.mode = mode;
    authForm.info = info;
    const v = AUTH_VIEWS[mode]();
    const dialog = $('authDialog');
    dialog.innerHTML = `<div class="auth-head">
        <h2 id="authTitle">${v.title}</h2>
        <button type="button" class="auth-close" data-auth-close aria-label="닫기">×</button>
      </div>
      <form class="auth-form" data-auth-form="${mode}">
        ${info ? `<p class="auth-info" role="status">${esc(info)}</p>` : ''}
        ${v.fields}
        <p class="auth-error" role="alert"></p>
        <button type="submit" class="auth-submit">${v.submit}</button>
      </form>${v.after}`;
    const empty = [...dialog.querySelectorAll('input')].find((i) => !i.value);
    if (empty) empty.focus();
  }

  function openAuth() {
    const dialog = $('authDialog');
    if (!dialog.open) dialog.showModal();
    setAuthMode('login', Auth.configured ? '' : NOT_CONFIGURED); // 창을 연 뒤에 그려야 입력칸에 포커스가 감
  }

  function closeAuth() { $('authDialog').close(); }

  async function submitAuth(form) {
    if (authBusy) return;
    const mode = form.dataset.authForm;
    const data = Object.fromEntries(new FormData(form));
    const btn = form.querySelector('.auth-submit');
    const showError = (m) => { const el = form.querySelector('.auth-error'); if (el) el.textContent = m; };
    if (data.email !== undefined) authForm.email = data.email.trim();
    if (!Auth.configured) { showError(NOT_CONFIGURED); return; }
    if (mode === 'signup' && data.password !== data.password2) { showError('비밀번호 확인이 맞지 않아요.'); return; }

    authBusy = true;
    const label = btn.textContent;
    btn.disabled = true; btn.textContent = '처리 중…'; showError('');
    try {
      if (mode === 'login') {
        authForm.password = data.password;
        try {
          await Auth.loginWithEmail(authForm.email, data.password);
        } catch (err) {
          if (err.code !== 'UserNotConfirmedException') throw err;
          await Auth.resendCode(authForm.email); // 가입만 하고 인증을 안 끝낸 계정: 코드를 새로 보내고 인증 단계로
          setAuthMode('confirm', `이메일 인증이 아직 안 끝났어요. ${authForm.email} 주소로 보낸 6자리 코드를 입력해 주세요.`);
          return;
        }
        closeAuth(); afterLogin();
      } else if (mode === 'signup') {
        authForm.password = data.password;
        const dest = await Auth.signUp(authForm.email, data.password);
        setAuthMode('confirm', `${dest} 주소로 인증 코드를 보냈어요. 메일에 있는 6자리 코드를 입력해 주세요.`);
      } else if (mode === 'confirm') {
        await Auth.confirmSignUp(authForm.email, data.code);
        if (!authForm.password) { setAuthMode('login', '인증이 끝났어요. 로그인해 주세요.'); return; }
        await Auth.loginWithEmail(authForm.email, authForm.password);
        closeAuth(); afterLogin();
      } else if (mode === 'forgot') {
        await Auth.forgotPassword(authForm.email);
        setAuthMode('reset', `${authForm.email} 주소로 보낸 인증 코드와 새 비밀번호를 입력해 주세요.`);
      } else if (mode === 'reset') {
        await Auth.resetPassword(authForm.email, data.code, data.password);
        await Auth.loginWithEmail(authForm.email, data.password);
        closeAuth(); afterLogin();
      }
    } catch (err) {
      showError(err.message);
    } finally {
      authBusy = false;
      if (form.isConnected) { btn.disabled = false; btn.textContent = label; }
    }
  }

  $('authDialog').addEventListener('close', () => { authForm.password = ''; });
  $('authDialog').addEventListener('click', (e) => { if (e.target === e.currentTarget) closeAuth(); }); // 바깥(배경) 클릭

  // ── 이벤트
  document.addEventListener('click', (e) => {
    // 세부 메뉴에서 고르면: 그 카테고리로 가서 구분 칩을 골라 둠 ("전체 N건 보기"는 칩 없이)
    const go = e.target.closest('[data-go-cat]');
    if (go) {
      e.preventDefault();
      const cat = go.dataset.goCat;
      state.view = cat;
      state.subtype = go.dataset.goSub || null;
      closeMenu();
      if (location.hash !== `#${cat}`) location.hash = cat; // hashchange에서 다시 그림 (view가 같아서 칩은 유지)
      else { render(); window.scrollTo(0, 0); }
      return;
    }
    const sub = e.target.closest('[data-subtype]');
    if (sub) { const v = sub.dataset.subtype; state.subtype = v === '전체' ? null : v; renderFilters(); renderList(); return; }
    const region = e.target.closest('[data-region]');
    if (region) { state.region = region.dataset.region || null; renderFilters(); renderList(); return; }
    const venue = e.target.closest('[data-venue]');
    if (venue) { state.venue = venue.dataset.venue || null; renderFilters(); renderList(); return; }
    const field = e.target.closest('[data-field]');
    if (field) { const f = field.dataset.field; state.fields.has(f) ? state.fields.delete(f) : state.fields.add(f); renderFilters(); renderList(); return; }
    const bm = e.target.closest('[data-bm]');
    if (bm) { state.bookmarks = Bookmarks.toggle(bm.dataset.bm); renderTabs(); renderList(); return; }
    if (e.target.closest('[data-open-school]')) { openSchool(); return; }
    const school = e.target.closest('[data-school]');
    if (school) { $('schoolDialog').close(); applySchool(school.dataset.school); return; }
    if (e.target.closest('[data-school-close]')) { $('schoolDialog').close(); return; }
    if (e.target.closest('[data-open-login]')) { openAuth(); return; }
    if (e.target.closest('[data-login-discord]')) {
      if (Auth.configured) { Auth.login(); return; }
      if ($('authDialog').open) { $('authDialog').querySelector('.auth-error').textContent = NOT_CONFIGURED; return; }
      state.authMsg = NOT_CONFIGURED;
      renderAuth(); return;
    }
    const mode = e.target.closest('[data-auth-mode]');
    if (mode) { setAuthMode(mode.dataset.authMode); return; }
    if (e.target.closest('[data-auth-close]')) { closeAuth(); return; }
    const resend = e.target.closest('[data-auth-resend]');
    if (resend) {
      const err = $('authDialog').querySelector('.auth-error');
      resend.disabled = true;
      Auth.resendCode(authForm.email)
        .then(() => { err.textContent = ''; setAuthMode('confirm', `${authForm.email} 주소로 인증 코드를 다시 보냈어요.`); })
        .catch((e2) => { err.textContent = e2.message; resend.disabled = false; });
      return;
    }
    if (e.target.closest('[data-logout]')) {
      if (!Auth.logout()) { state.user = null; state.subs = null; state.authMsg = ''; renderAuth(); authChanged(); } // 이메일 로그인은 이 자리에서 로그아웃
      return;
    }
    const unsub = e.target.closest('[data-unsub]');
    if (unsub) { syncSubs(Api.removeSubscription(unsub.dataset.unsub)); return; }
    if (e.target.closest('[data-nolink]')) e.preventDefault(); // 예시 데이터라 원문 링크가 없음
  });
  document.addEventListener('submit', (e) => {
    if (e.target.dataset.authForm) { e.preventDefault(); submitAuth(e.target); return; }
    if ('schoolOther' in e.target.dataset) {
      e.preventDefault();
      $('schoolDialog').close();
      applySchool('other', e.target.requested.value.trim());
      return;
    }
    if (e.target.id !== 'subsForm') return;
    e.preventDefault();
    const keyword = $('subsInput').value.trim();
    if (keyword) syncSubs(Api.addSubscription(keyword)).then(() => { const input = $('subsInput'); if (input) input.focus(); });
  });
  $('search').addEventListener('input', (e) => { state.q = e.target.value; renderList(); });
  $('sort').addEventListener('change', (e) => { state.sort = e.target.value; renderList(); });
  $('resetBtn').addEventListener('click', () => {
    state.fields.clear(); state.subtype = null; state.region = null; state.venue = null; state.q = ''; $('search').value = ''; renderFilters(); renderList();
  });
  const syncThemeBtn = () => {
    const dark = document.documentElement.dataset.theme === 'dark';
    $('themeBtn').setAttribute('aria-label', dark ? '밝은 화면으로 전환' : '어두운 화면으로 전환');
  };
  $('themeBtn').addEventListener('click', () => {
    const root = document.documentElement;
    const dark = root.dataset.theme !== 'dark';
    if (dark) root.dataset.theme = 'dark'; else delete root.dataset.theme;
    try { localStorage.setItem('csradar.theme', dark ? 'dark' : 'light'); } catch { /* 저장 불가 환경 */ }
    syncThemeBtn();
  });
  syncThemeBtn();
  window.addEventListener('hashchange', () => { menu.open = null; readHash(); render(); window.scrollTo(0, 0); });

  // 세부 메뉴 열고 닫기: 마우스는 잠깐 머물러야 열리고, 탭·메뉴 밖으로 나가면 조금 있다 닫힘
  const navZone = $('navZone');
  navZone.addEventListener('pointerover', (e) => {
    if (e.pointerType !== 'mouse') return; // 터치에서는 탭을 누르면 바로 이동
    const tab = e.target.closest('.tab');
    if (!tab) { if (e.target.closest('#megaMenu')) clearTimeout(menu.timer); return; }
    clearTimeout(menu.timer);
    const cat = tab.dataset.cat || null;
    menu.timer = setTimeout(() => (cat ? openMenu(cat) : closeMenu()), menu.open ? 60 : 150);
  });
  navZone.addEventListener('pointerleave', (e) => {
    if (e.pointerType !== 'mouse') return;
    clearTimeout(menu.timer);
    menu.timer = setTimeout(closeMenu, 200);
  });
  navZone.addEventListener('focusin', (e) => {
    const tab = e.target.closest('.tab');
    if (!tab || menu.skipFocus) { menu.skipFocus = false; return; }
    if (!tab.matches(':focus-visible')) return;
    if (tab.dataset.cat) openMenu(tab.dataset.cat); else closeMenu();
  });
  navZone.addEventListener('focusout', (e) => { if (!navZone.contains(e.relatedTarget)) closeMenu(); });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || !menu.open) return;
    const tab = document.querySelector(`.tab[data-cat="${menu.open}"]`);
    const inside = navZone.contains(document.activeElement);
    closeMenu();
    if (inside && tab && document.activeElement !== tab) { menu.skipFocus = true; tab.focus(); }
  });

  // ── 시작
  readHash();
  state.user = Auth.user();
  renderAuth();
  Auth.handleRedirect()                      // 로그인하고 막 돌아온 경우 토큰으로 교환
    .catch((err) => { state.authMsg = err.message; })
    .then(() => {
      state.user = Auth.user();
      renderAuth();
      if (state.user && state.user.method === 'discord') syncSubs(Api.listSubscriptions());
      authChanged();                         // 로그인했으면 여기서 내 학교도 서버와 맞춤
      // 처음 온 사람(로그인 안 함)에게 한 번만 학교를 물어봄
      if (!state.user && !MySchool.get().asked) openSchool();
    });
  renderSchoolLine();
  Api.listItems()
    .then((items) => { state.items = items; render(); })
    .catch((err) => {
      $('list').hidden = true; $('empty').hidden = false;
      $('empty').innerHTML = `<p><b>${esc(err.message)}</b></p><p class="muted">js/api.js의 API_BASE 주소와 서버 상태를 확인해 주세요.</p>`;
    });
})();
