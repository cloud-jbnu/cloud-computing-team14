// 로그인 (Cognito + 디스코드).
// "로그인"을 누르면 Cognito를 거쳐 디스코드 로그인 화면으로 갔다가, 코드(code)를 들고 이 페이지로 돌아옵니다.
// 그 코드를 토큰으로 바꿔 브라우저에 저장하고, API를 부를 때 Authorization 헤더에 넣습니다.
// 비밀 값 없이 브라우저만으로 안전하게 하려고 PKCE 방식을 씁니다.
// 주소 설정(AUTH_BASE, AUTH_CLIENT_ID)은 api.js 맨 위에 있습니다.

(function () {
  const KEY = 'csradar.auth';       // 토큰 (localStorage)
  const PKCE_KEY = 'csradar.pkce';  // 로그인 도중에만 쓰는 값 (sessionStorage)
  const REDIRECT_URI = `${location.origin}/`; // infra/template.yaml의 WebOrigin + "/" 와 같아야 함

  const b64url = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const random = (n) => b64url(crypto.getRandomValues(new Uint8Array(n)));
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } };
  const write = (s) => {
    try { s ? localStorage.setItem(KEY, JSON.stringify(s)) : localStorage.removeItem(KEY); } catch { /* 저장 불가 환경 */ }
  };

  let session = read();

  async function requestToken(params) {
    const res = await fetch(`${AUTH_BASE}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ client_id: AUTH_CLIENT_ID, ...params }),
    });
    if (!res.ok) throw new Error('로그인에 실패했어요. 다시 시도해 주세요.');
    const t = await res.json();
    session = {
      accessToken: t.access_token,
      idToken: t.id_token,
      refreshToken: t.refresh_token || (session && session.refreshToken),
      expiresAt: Date.now() + t.expires_in * 1000,
    };
    write(session);
  }

  window.Auth = {
    configured: Boolean(AUTH_BASE && AUTH_CLIENT_ID && API_BASE),

    // 로그인한 사용자 { name } 또는 null. ID 토큰에 들어 있는 이름을 꺼냅니다.
    user() {
      if (!session || !session.idToken) return null;
      try {
        const part = session.idToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        const claims = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(part), (c) => c.charCodeAt(0))));
        return { name: claims.preferred_username || claims.name || claims.nickname || '디스코드 사용자' };
      } catch { return null; }
    },

    async login() {
      const verifier = random(48);
      const state = random(16);
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
      sessionStorage.setItem(PKCE_KEY, JSON.stringify({ verifier, state }));
      location.assign(`${AUTH_BASE}/oauth2/authorize?` + new URLSearchParams({
        response_type: 'code',
        client_id: AUTH_CLIENT_ID,
        redirect_uri: REDIRECT_URI,
        scope: 'openid profile',
        identity_provider: 'Discord', // Cognito 로그인 화면을 건너뛰고 바로 디스코드로
        state,
        code_challenge: b64url(new Uint8Array(digest)),
        code_challenge_method: 'S256',
      }));
    },

    // 로그인하고 돌아온 직후(?code=...)라면 토큰으로 바꿉니다. 페이지를 열 때 한 번 부릅니다.
    async handleRedirect() {
      const params = new URLSearchParams(location.search);
      if (!params.has('code') && !params.has('error')) return;
      let pkce = null;
      try { pkce = JSON.parse(sessionStorage.getItem(PKCE_KEY)); } catch { /* 아래에서 처리 */ }
      sessionStorage.removeItem(PKCE_KEY);
      history.replaceState(null, '', location.pathname + location.hash); // 주소창에서 code 지우기
      if (params.has('error')) throw new Error('로그인이 취소됐어요.');
      if (!pkce || pkce.state !== params.get('state')) throw new Error('로그인 요청이 맞지 않아요. 다시 시도해 주세요.');
      await requestToken({
        grant_type: 'authorization_code',
        code: params.get('code'),
        redirect_uri: REDIRECT_URI,
        code_verifier: pkce.verifier,
      });
    },

    // API에 보낼 액세스 토큰. 만료가 가까우면 새로 받고, 못 받으면 로그아웃 상태로 돌립니다.
    async token() {
      if (!session) return null;
      if (Date.now() > session.expiresAt - 60000) {
        try {
          if (!session.refreshToken) throw new Error('만료');
          await requestToken({ grant_type: 'refresh_token', refresh_token: session.refreshToken });
        } catch { this.clear(); return null; }
      }
      return session.accessToken;
    },

    clear() { session = null; write(null); },

    logout() {
      this.clear();
      location.assign(`${AUTH_BASE}/logout?` + new URLSearchParams({ client_id: AUTH_CLIENT_ID, logout_uri: REDIRECT_URI }));
    },
  };
})();
