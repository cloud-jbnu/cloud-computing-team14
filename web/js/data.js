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
  univ:    ['서울대', 'KAIST', 'POSTECH', '연세대', '고려대', '성균관대', '한양대', '전북대'],
  contest: ['해커톤', '공모전', '경진대회', 'CTF'],
  jobs:    ['인턴', '신입', '채용연계'],
  tech:    ['GitHub', '최신기술', '이슈'],
};

window.SAMPLE_ITEMS = [
  // ── 대학 소식
  { id: 'u1', category: 'univ', subtype: 'KAIST', source: 'KAIST 전산학부', title: '2027학년도 전기 대학원 입학설명회 개최 안내', fields: ['ai', 'data'], date: '2026-11-10', url: 'https://cs.kaist.ac.kr' },
  { id: 'u2', category: 'univ', subtype: '서울대', source: '서울대 컴퓨터공학부', title: '겨울방학 학부생 연구인턴(URP) 모집', fields: ['ai'], date: '2026-11-09', deadline: '2026-11-21', url: 'https://cse.snu.ac.kr' },
  { id: 'u3', category: 'univ', subtype: 'POSTECH', source: 'POSTECH 컴퓨터공학과', title: '동계 시스템 보안 집중 캠프 참가자 모집', fields: ['security', 'network'], date: '2026-11-08', deadline: '2026-11-25', url: 'https://cse.postech.ac.kr' },
  { id: 'u4', category: 'univ', subtype: '연세대', source: '연세대 컴퓨터과학과', title: '초청 특강: 대규모 분산 시스템 설계', fields: ['backend', 'cloud'], date: '2026-11-07', url: 'https://cs.yonsei.ac.kr' },
  { id: 'u5', category: 'univ', subtype: '고려대', source: '고려대 정보보호대학원', title: '해킹 방어 실습 세미나 참가 신청', fields: ['security'], date: '2026-11-06', deadline: '2026-11-19', url: 'https://gsis.korea.ac.kr' },
  { id: 'u6', category: 'univ', subtype: '전북대', source: '전북대 SW중심대학사업단', title: '동계 클라우드 부트캠프 수강생 모집', fields: ['cloud', 'backend'], date: '2026-11-10', deadline: '2026-11-20', url: 'https://www.jbnu.ac.kr' },
  { id: 'u7', category: 'univ', subtype: '성균관대', source: '성균관대 소프트웨어학과', title: '2026 졸업작품 전시회 개최', fields: ['frontend', 'mobile'], date: '2026-11-05', url: 'https://cse.skku.edu' },
  { id: 'u8', category: 'univ', subtype: '한양대', source: '한양대 컴퓨터소프트웨어학부', title: '온디바이스 AI 연구실 학부연구생 모집', fields: ['ai', 'mobile'], date: '2026-11-04', deadline: '2026-11-30', url: 'https://cs.hanyang.ac.kr' },

  // ── 공모전·대회
  { id: 'c1', category: 'contest', subtype: '해커톤', source: '대학생 개발자 연합', title: '제12회 대학생 AI 해커톤 참가팀 모집', fields: ['ai', 'backend'], date: '2026-11-10', deadline: '2026-11-24', url: '#' },
  { id: 'c2', category: 'contest', subtype: 'CTF', source: '정보보호 동아리 연합', title: '화이트햇 CTF 2026 예선 참가 접수', fields: ['security', 'network'], date: '2026-11-09', deadline: '2026-11-18', url: '#' },
  { id: 'c3', category: 'contest', subtype: '공모전', source: '클라우드 산업 협회', title: '클라우드 네이티브 아키텍처 설계 공모전', fields: ['cloud', 'backend'], date: '2026-11-08', deadline: '2026-12-05', url: '#' },
  { id: 'c4', category: 'contest', subtype: '공모전', source: '모바일 서비스 포럼', title: '대학생 모바일 앱 아이디어 공모전', fields: ['mobile', 'frontend'], date: '2026-11-07', deadline: '2026-11-29', url: '#' },
  { id: 'c5', category: 'contest', subtype: '경진대회', source: '공공데이터 활용 센터', title: '공공데이터 분석·시각화 경진대회', fields: ['data', 'ai'], date: '2026-11-06', deadline: '2026-12-12', url: '#' },
  { id: 'c6', category: 'contest', subtype: '경진대회', source: '전국 대학 알고리즘 연합', title: '동계 대학생 알고리즘 대회 (팀전 3인)', fields: ['backend'], date: '2026-11-05', deadline: '2026-11-15', url: '#' },
  { id: 'c7', category: 'contest', subtype: '해커톤', source: '오픈소스 커뮤니티', title: '겨울 오픈소스 컨트리뷰션 해커톤', fields: ['backend', 'frontend'], date: '2026-11-04', deadline: '2026-11-27', url: '#' },
  { id: 'c8', category: 'contest', subtype: '공모전', source: '웹 접근성 연구회', title: '웹 접근성 UI 개선 챌린지', fields: ['frontend'], date: '2026-11-03', deadline: '2026-12-01', url: '#' },

  // ── 취업·인턴
  { id: 'j1', category: 'jobs', subtype: '인턴', source: '루프랩', title: '2027 동계 백엔드 개발 인턴 (8주)', fields: ['backend', 'cloud'], date: '2026-11-10', deadline: '2026-11-23', url: '#' },
  { id: 'j2', category: 'jobs', subtype: '신입', source: '픽셀하우스', title: '프론트엔드 엔지니어 신입 공개채용', fields: ['frontend'], date: '2026-11-09', deadline: '2026-11-30', url: '#' },
  { id: 'j3', category: 'jobs', subtype: '채용연계', source: '시큐어웨이브', title: '보안관제·침해대응 채용연계형 인턴', fields: ['security', 'network'], date: '2026-11-08', deadline: '2026-11-17', url: '#' },
  { id: 'j4', category: 'jobs', subtype: '인턴', source: '데이터포레스트', title: 'ML 엔지니어 체험형 인턴', fields: ['ai', 'data'], date: '2026-11-07', deadline: '2026-11-26', url: '#' },
  { id: 'j5', category: 'jobs', subtype: '신입', source: '클라우드브릿지', title: 'DevOps·SRE 신입 엔지니어', fields: ['cloud', 'network'], date: '2026-11-06', deadline: '2026-12-08', url: '#' },
  { id: 'j6', category: 'jobs', subtype: '인턴', source: '모빌리언', title: 'Android·iOS 앱 개발 인턴', fields: ['mobile'], date: '2026-11-05', deadline: '2026-11-22', url: '#' },
  { id: 'j7', category: 'jobs', subtype: '채용연계', source: '넷코어', title: '네트워크 엔지니어 채용연계형 인턴', fields: ['network'], date: '2026-11-04', deadline: '2026-11-28', url: '#' },
  { id: 'j8', category: 'jobs', subtype: '신입', source: '넥스트스택', title: '풀스택 개발자 (Node.js · React) 신입', fields: ['backend', 'frontend'], date: '2026-11-03', deadline: '2026-12-03', url: '#' },

  // ── 테크 트렌드 (GitHub · 최신기술 · 이슈)
  { id: 't1', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'ollama/ollama', fields: ['ai'], date: '2026-11-11', url: 'https://github.com/ollama/ollama', repo: { lang: 'Go', starsToday: 412 } },
  { id: 't2', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'astral-sh/uv', fields: ['backend'], date: '2026-11-11', url: 'https://github.com/astral-sh/uv', repo: { lang: 'Rust', starsToday: 288 } },
  { id: 't3', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'vercel/next.js', fields: ['frontend'], date: '2026-11-11', url: 'https://github.com/vercel/next.js', repo: { lang: 'TypeScript', starsToday: 197 } },
  { id: 't4', category: 'tech', subtype: 'GitHub', source: 'GitHub Trending', title: 'projectdiscovery/nuclei', fields: ['security'], date: '2026-11-11', url: 'https://github.com/projectdiscovery/nuclei', repo: { lang: 'Go', starsToday: 154 } },
  { id: 't5', category: 'tech', subtype: '최신기술', source: '기술 블로그 모음', title: 'HTTP/3 도입 사례로 보는 백엔드 성능 변화', fields: ['network', 'backend'], date: '2026-11-10', url: '#' },
  { id: 't6', category: 'tech', subtype: '최신기술', source: '기술 블로그 모음', title: '쿠버네티스 신규 버전 주요 변경점 정리', fields: ['cloud'], date: '2026-11-09', url: '#' },
  { id: 't7', category: 'tech', subtype: '이슈', source: '보안 뉴스', title: 'npm 패키지 공급망 공격 주의보', fields: ['security', 'frontend'], date: '2026-11-10', url: '#' },
  { id: 't8', category: 'tech', subtype: '이슈', source: 'AI 뉴스', title: 'LLM 에이전트 프롬프트 인젝션 대응 가이드 공개', fields: ['ai', 'security'], date: '2026-11-08', url: '#' },
];
