// 예시 데이터 — 백엔드(크롤러 + API)가 붙기 전까지 화면 확인용으로만 씁니다.
// 실제 서비스에서는 api.js가 API_BASE에서 같은 모양의 데이터를 받아옵니다.

window.CATEGORIES = [
  { id: 'univ',    label: '대학 소식' },
  { id: 'contest', label: '공모전·대회' },
  { id: 'jobs',    label: '취업·인턴' },
  { id: 'tech',    label: '테크 트렌드' },
];

window.FIELDS = [
  { id: 'backend',  label: '백엔드' },
  { id: 'frontend', label: '프론트엔드' },
  { id: 'ai',       label: 'AI' },
  { id: 'data',     label: '데이터' },
  { id: 'cloud',    label: '클라우드' },
  { id: 'network',  label: '네트워크' },
  { id: 'security', label: '보안' },
  { id: 'mobile',   label: '모바일' },
];

// 카테고리별 세부 구분
window.SUBTYPES = {
  univ:    ['전북대', '충북대', '경북대', '부산대'],
  contest: ['해커톤', '공모전', '경진대회', 'CTF'],
  jobs:    ['인턴', '신입', '채용연계'],
  tech:    ['GitHub', '최신기술', '이슈'],
};

// 근무지·행사 장소(시·도)와 대회 진행 방식. crawler/src/common/item.py의 REGIONS·VENUES와 같은 값
window.REGIONS = ['서울', '경기', '인천', '강원', '대전', '세종', '충북', '충남', '광주', '전북', '전남', '대구', '경북', '부산', '울산', '경남', '제주'];
window.VENUES = [
  { id: 'online', label: '온라인' },
  { id: 'offline', label: '오프라인' },
];
// 내 학교가 있는 시·도 (취업·인턴 지역 칩에서 맨 앞에 보여 줌)
window.SCHOOL_REGION = { 전북대: '전북', 충북대: '충북', 경북대: '대구', 부산대: '부산' };

window.SAMPLE_ITEMS = [
  // ── 대학 소식 (학교 전체 공지)
  { id: 'u1', category: 'univ', subtype: '전북대', source: '전북대 SW중심대학사업단', title: '동계 클라우드 부트캠프 수강생 모집', fields: ['cloud', 'backend'], date: '2026-11-10', deadline: '2026-11-20', url: 'https://www.jbnu.ac.kr', summary: ['재학생 대상 4주 과정으로 AWS 기초부터 배포까지 실습함', '11월 20일까지 온라인으로 신청하며 수료 시 비교과 포인트를 줌'] },
  { id: 'u2', category: 'univ', subtype: '전북대', source: '전북대 학사관리과', title: '2026학년도 동계 계절수업 수강신청 안내', fields: [], date: '2026-11-09', deadline: '2026-11-21', url: 'https://www.jbnu.ac.kr', summary: ['수강신청은 11월 18일부터 21일까지이며 최대 6학점까지 가능함', '등록금을 기간 안에 내지 않으면 신청이 취소됨'] },
  { id: 'u3', category: 'univ', subtype: '충북대', source: '충북대 창업지원단', title: '동계 시스템 보안 집중 캠프 참가자 모집', fields: ['security', 'network'], date: '2026-11-08', deadline: '2026-11-25', url: 'https://www.chungbuk.ac.kr', summary: ['전공 무관 재학생 30명을 선발해 5일간 실습 위주로 진행함', '11월 25일까지 신청서를 내야 함'] },
  { id: 'u4', category: 'univ', subtype: '충북대', source: '충북대 학사지원과', title: '초청 특강: 대규모 분산 시스템 설계', fields: ['backend', 'cloud'], date: '2026-11-07', url: 'https://www.chungbuk.ac.kr' },
  { id: 'u5', category: 'univ', subtype: '경북대', source: '경북대 정보화본부', title: '해킹 방어 실습 세미나 참가 신청', fields: ['security'], date: '2026-11-06', deadline: '2026-11-19', url: 'https://www.knu.ac.kr', summary: ['웹 취약점 분석과 대응을 실습하는 하루 과정임', '선착순 40명이며 11월 19일에 접수를 마감함'] },
  { id: 'u6', category: 'univ', subtype: '경북대', source: '경북대 교무과', title: '2026학년도 제4회 융합전공 설명회 개최 안내', fields: [], date: '2026-11-10', url: 'https://www.knu.ac.kr' },
  { id: 'u7', category: 'univ', subtype: '부산대', source: '부산대 대학일자리플러스센터', title: '2026 졸업작품 전시회 개최', fields: ['frontend', 'mobile'], date: '2026-11-05', url: 'https://www.pusan.ac.kr' },
  { id: 'u8', category: 'univ', subtype: '부산대', source: '부산대 학생과', title: '온디바이스 AI 연구실 학부연구생 모집', fields: ['ai', 'mobile'], date: '2026-11-04', deadline: '2026-11-30', url: 'https://www.pusan.ac.kr', summary: ['3학년 이상 재학생을 대상으로 겨울방학 동안 연구에 참여함', '11월 30일까지 지원서와 성적증명서를 내야 함'] },

  // ── 공모전·대회
  { id: 'c1', category: 'contest', subtype: '해커톤', source: '대학생 개발자 연합', title: '제12회 대학생 AI 해커톤 참가팀 모집', fields: ['ai', 'backend'], date: '2026-11-10', deadline: '2026-11-24', url: '#', venue: 'offline', regions: ['서울'], summary: ['3~4인 팀으로 참가하며 AI를 활용한 서비스를 48시간 동안 만듦', '11월 24일까지 참가 신청을 받음'] },
  { id: 'c2', category: 'contest', subtype: 'CTF', source: '정보보호 동아리 연합', title: '화이트햇 CTF 2026 예선 참가 접수', fields: ['security', 'network'], date: '2026-11-09', deadline: '2026-11-18', url: '#', venue: 'online' },
  { id: 'c3', category: 'contest', subtype: '공모전', source: '클라우드 산업 협회', title: '클라우드 네이티브 아키텍처 설계 공모전', fields: ['cloud', 'backend'], date: '2026-11-08', deadline: '2026-12-05', url: '#', venue: 'online' },
  { id: 'c4', category: 'contest', subtype: '공모전', source: '모바일 서비스 포럼', title: '대학생 모바일 앱 아이디어 공모전', fields: ['mobile', 'frontend'], date: '2026-11-07', deadline: '2026-11-29', url: '#', venue: 'hybrid' },
  { id: 'c5', category: 'contest', subtype: '경진대회', source: '공공데이터 활용 센터', title: '공공데이터 분석·시각화 경진대회', fields: ['data', 'ai'], date: '2026-11-06', deadline: '2026-12-12', url: '#', venue: 'online' },
  { id: 'c6', category: 'contest', subtype: '경진대회', source: '전국 대학 알고리즘 연합', title: '동계 대학생 알고리즘 대회 (팀전 3인)', fields: ['backend'], date: '2026-11-05', deadline: '2026-11-15', url: '#', venue: 'offline', regions: ['대전'] },
  { id: 'c7', category: 'contest', subtype: '해커톤', source: '오픈소스 커뮤니티', title: '겨울 오픈소스 컨트리뷰션 해커톤', fields: ['backend', 'frontend'], date: '2026-11-04', deadline: '2026-11-27', url: '#', venue: 'online' },
  { id: 'c8', category: 'contest', subtype: '공모전', source: '웹 접근성 연구회', title: '웹 접근성 UI 개선 챌린지', fields: ['frontend'], date: '2026-11-03', deadline: '2026-12-01', url: '#' },

  // ── 취업·인턴
  { id: 'j1', category: 'jobs', subtype: '인턴', source: '루프랩', title: '2027 동계 백엔드 개발 인턴 (8주)', fields: ['backend', 'cloud'], date: '2026-11-10', deadline: '2026-11-23', url: '#', regions: ['서울'], summary: ['8주 동안 백엔드 팀에서 실제 서비스 개발에 참여함', '졸업 예정자와 휴학생도 지원할 수 있으며 11월 23일에 마감함'] },
  { id: 'j2', category: 'jobs', subtype: '신입', source: '픽셀하우스', title: '프론트엔드 엔지니어 신입 공개채용', fields: ['frontend'], date: '2026-11-09', deadline: '2026-11-30', url: '#', regions: ['경기'] },
  { id: 'j3', category: 'jobs', subtype: '채용연계', source: '시큐어웨이브', title: '보안관제·침해대응 채용연계형 인턴', fields: ['security', 'network'], date: '2026-11-08', deadline: '2026-11-17', url: '#', regions: ['서울'] },
  { id: 'j4', category: 'jobs', subtype: '인턴', source: '데이터포레스트', title: 'ML 엔지니어 체험형 인턴', fields: ['ai', 'data'], date: '2026-11-07', deadline: '2026-11-26', url: '#', regions: ['부산'] },
  { id: 'j5', category: 'jobs', subtype: '신입', source: '클라우드브릿지', title: 'DevOps·SRE 신입 엔지니어', fields: ['cloud', 'network'], date: '2026-11-06', deadline: '2026-12-08', url: '#', regions: ['대전'] },
  { id: 'j6', category: 'jobs', subtype: '인턴', source: '모빌리언', title: 'Android·iOS 앱 개발 인턴', fields: ['mobile'], date: '2026-11-05', deadline: '2026-11-22', url: '#', regions: ['전북'] },
  { id: 'j7', category: 'jobs', subtype: '채용연계', source: '넷코어', title: '네트워크 엔지니어 채용연계형 인턴', fields: ['network'], date: '2026-11-04', deadline: '2026-11-28', url: '#', regions: ['대구', '경북'] },
  { id: 'j8', category: 'jobs', subtype: '신입', source: '넥스트스택', title: '풀스택 개발자 (Node.js · React) 신입', fields: ['backend', 'frontend'], date: '2026-11-03', deadline: '2026-12-03', url: '#' },

  // ── 테크 트렌드 (GitHub · 최신기술 · 이슈)
  { id: 't1', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'ollama/ollama', fields: ['ai'], date: '2026-11-11', url: 'https://github.com/ollama/ollama', repo: { lang: 'Go', starsToday: 412 } },
  { id: 't2', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'astral-sh/uv', fields: ['backend'], date: '2026-11-11', url: 'https://github.com/astral-sh/uv', repo: { lang: 'Rust', starsToday: 288 } },
  { id: 't3', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'vercel/next.js', fields: ['frontend'], date: '2026-11-11', url: 'https://github.com/vercel/next.js', repo: { lang: 'TypeScript', starsToday: 197 } },
  { id: 't4', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'projectdiscovery/nuclei', fields: ['security'], date: '2026-11-11', url: 'https://github.com/projectdiscovery/nuclei', repo: { lang: 'Go', starsToday: 154 } },
  { id: 't5', category: 'tech', subtype: '최신기술', source: '기술 블로그 모음', title: 'HTTP/3 도입 사례로 보는 백엔드 성능 변화', fields: ['network', 'backend'], date: '2026-11-10', url: '#', summary: ['HTTP/3로 바꾼 뒤 지연 시간이 줄어든 사례를 수치와 함께 소개함', '도입할 때 겪은 로드밸런서 설정 문제와 해결 방법을 다룸'] },
  { id: 't6', category: 'tech', subtype: '최신기술', source: '기술 블로그 모음', title: '쿠버네티스 신규 버전 주요 변경점 정리', fields: ['cloud'], date: '2026-11-09', url: '#' },
  { id: 't7', category: 'tech', subtype: '이슈', source: '보안 뉴스', title: 'npm 패키지 공급망 공격 주의보', fields: ['security', 'frontend'], date: '2026-11-10', url: '#' },
  { id: 't8', category: 'tech', subtype: '이슈', source: 'AI 뉴스', title: 'LLM 에이전트 프롬프트 인젝션 대응 가이드 공개', fields: ['ai', 'security'], date: '2026-11-08', url: '#' },
];
