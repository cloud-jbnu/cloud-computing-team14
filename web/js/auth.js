// 로그인 (Cognito). 두 가지 방법이 있습니다.
//
// 1. 디스코드: "디스코드로 로그인"을 누르면 Cognito를 거쳐 디스코드 로그인 화면으로 갔다가, 코드(code)를 들고
//    이 페이지로 돌아옵니다. 그 코드를 토큰으로 바꿉니다. 비밀 값 없이 브라우저만으로 하려고 PKCE 방식을 씁니다.
// 2. 이메일: 화면 안의 로그인 창에서 Cognito API(SignUp, ConfirmSignUp, InitiateAuth 등)를 직접 부릅니다.
//    가입 → 메일로 온 인증 코드 입력 → 로그인. 사용자 이름은 이메일 주소(소문자)입니다.
//
// 어느 쪽이든 받은 토큰을 브라우저에 저장하고, API를 부를 때 Authorization 헤더에 넣습니다.
// 주소 설정(AUTH_BASE, AUTH_CLIENT_ID)은 api.js 맨 위에 있습니다.

(function () {
  const KEY = 'csradar.auth';       // 토큰 (localStorage)
  const PKCE_KEY = 'csradar.pkce';  // 디스코드 로그인 도중에만 쓰는 값 (sessionStorage)
  const REDIRECT_URI = `${location.origin}/`; // infra/template.yaml의 WebOrigin + "/" 와 같아야 함
  // AUTH_BASE(https://<도메인>.auth.<리전>.amazoncognito.com)에서 리전을 꺼내 Cognito API 주소를 만듭니다.
  const REGION = (String(AUTH_BASE).match(/\.auth\.([a-z0-9-]+)\.amazoncognito\.com/) || [])[1];
  const IDP_URL = REGION ? `https://cognito-idp.${REGION}.amazonaws.com/` : '';

  const b64url = (bytes) => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const random = (n) => b64url(crypto.getRandomValues(new Uint8Array(n)));
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } };
  const write = (s) => {
    try { s ? localStorage.setItem(KEY, JSON.stringify(s)) : localStorage.removeItem(KEY); } catch { /* 저장 불가 환경 */ }
  };
  const normEmail = (email) => String(email || '').trim().toLowerCase();

  let session = read();

  function setSession(method, t) {
    session = {
      method,                                  // 'discord' | 'email'
      accessToken: t.accessToken,
      idToken: t.idToken,
      refreshToken: t.refreshToken || (session && session.refreshToken),
      expiresAt: Date.now() + t.expiresIn * 1000,
    };
    write(session);
  }

  // ── 디스코드 (OAuth2 토큰 엔드포인트)
  async function requestToken(params) {
    const res = await fetch(`${AUTH_BASE}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ client_id: AUTH_CLIENT_ID, ...params }),
    });
    if (!res.ok) throw new Error('로그인에 실패했어요. 다시 시도해 주세요.');
    const t = await res.json();
    setSession('discord', { accessToken: t.access_token, idToken: t.id_token, refreshToken: t.refresh_token, expiresIn: t.expires_in });
  }

  // ── 이메일 (Cognito User Pool API)
  const ERRORS = {
    UsernameExistsException: '이미 가입된 이메일이에요. 로그인해 주세요.',
    InvalidPasswordException: '비밀번호는 8자 이상이고 숫자가 하나 이상 들어가야 해요.',
    InvalidParameterException: '입력한 값을 다시 확인해 주세요.',
    CodeMismatchException: '인증 코드가 맞지 않아요.',
    ExpiredCodeException: '인증 코드가 만료됐어요. 코드를 다시 받아 주세요.',
    NotAuthorizedException: '이메일 또는 비밀번호가 맞지 않아요.',
    UserNotFoundException: '이메일 또는 비밀번호가 맞지 않아요.',
    UserNotConfirmedException: '이메일 인증이 아직 끝나지 않았어요.',
    CodeDeliveryFailureException: '인증 메일을 보내지 못했어요. 잠시 후 다시 시도해 주세요.',
    LimitExceededException: '시도가 너무 많아요. 잠시 후 다시 해 주세요.',
    TooManyRequestsException: '시도가 너무 많아요. 잠시 후 다시 해 주세요.',
    TooManyFailedAttemptsException: '시도가 너무 많아요. 잠시 후 다시 해 주세요.',
  };

  class AuthError extends Error {
    constructor(code, message) { super(message); this.code = code; }
  }

  async function idp(action, body) {
    if (!IDP_URL) throw new AuthError('NotConfigured', '로그인이 아직 연결되지 않았어요.');
    let res;
    try {
      res = await fetch(IDP_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': `AWSCognitoIdentityProviderService.${action}`,
        },
        body: JSON.stringify({ ClientId: AUTH_CLIENT_ID, ...body }),
      });
    } catch {
      throw new AuthError('Network', '서버에 연결하지 못했어요. 인터넷 연결을 확인해 주세요.');
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = String(data.__type || '').split('#').pop();
      throw new AuthError(code, ERRORS[code] || '요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.');
    }
    return data;
  }

  function fromAuthResult(data) {
    const r = data.AuthenticationResult;
    if (!r) throw new AuthError('Challenge', '이 계정은 웹에서 바로 로그인할 수 없어요. 관리자에게 문의해 주세요.');
    return { accessToken: r.AccessToken, idToken: r.IdToken, refreshToken: r.RefreshToken, expiresIn: r.ExpiresIn };
  }

  function claims(token) {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(part), (c) => c.charCodeAt(0))));
  }

  window.Auth = {
    configured: Boolean(AUTH_BASE && AUTH_CLIENT_ID && API_BASE),

    // 로그인한 사용자 { name, method } 또는 null. method는 'discord' | 'email'.
    user() {
      if (!session || !session.idToken) return null;
      try {
        const c = claims(session.idToken);
        const method = session.method || 'discord'; // method가 없으면 이메일 로그인이 생기기 전에 저장된 디스코드 세션
        const name = method === 'email'
          ? c.email || c['cognito:username'] || '이메일 사용자'
          : c.preferred_username || c.name || c.nickname || '디스코드 사용자';
        return { name, method };
      } catch { return null; }
    },

    // ── 디스코드 로그인
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

    // 디스코드 로그인하고 돌아온 직후(?code=...)라면 토큰으로 바꿉니다. 페이지를 열 때 한 번 부릅니다.
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

    // ── 이메일 회원가입 · 로그인. 실패하면 화면에 보여 줄 문구와 code를 가진 오류를 던집니다.
    // 가입하면 Cognito가 인증 코드를 메일로 보냅니다. 돌려주는 값: 코드를 보낸 주소(가려진 형태일 수 있음)
    async signUp(email, password) {
      const username = normEmail(email);
      const data = await idp('SignUp', {
        Username: username,
        Password: password,
        UserAttributes: [{ Name: 'email', Value: username }],
      });
      return (data.CodeDeliveryDetails && data.CodeDeliveryDetails.Destination) || username;
    },

    async confirmSignUp(email, code) {
      await idp('ConfirmSignUp', { Username: normEmail(email), ConfirmationCode: String(code).trim() });
    },

    async resendCode(email) {
      await idp('ResendConfirmationCode', { Username: normEmail(email) });
    },

    async loginWithEmail(email, password) {
      const data = await idp('InitiateAuth', {
        AuthFlow: 'USER_PASSWORD_AUTH',
        AuthParameters: { USERNAME: normEmail(email), PASSWORD: password },
      });
      setSession('email', fromAuthResult(data));
    },

    async forgotPassword(email) {
      await idp('ForgotPassword', { Username: normEmail(email) });
    },

    async resetPassword(email, code, password) {
      await idp('ConfirmForgotPassword', { Username: normEmail(email), ConfirmationCode: String(code).trim(), Password: password });
    },

    // API에 보낼 액세스 토큰. 만료가 가까우면 새로 받고, 못 받으면 로그아웃 상태로 돌립니다.
    async token() {
      if (!session) return null;
      if (Date.now() > session.expiresAt - 60000) {
        try {
          if (!session.refreshToken) throw new Error('만료');
          if (session.method === 'email') {
            const data = await idp('InitiateAuth', {
              AuthFlow: 'REFRESH_TOKEN_AUTH',
              AuthParameters: { REFRESH_TOKEN: session.refreshToken },
            });
            setSession('email', fromAuthResult(data)); // 새 리프레시 토큰은 안 오므로 기존 것을 유지
          } else {
            await requestToken({ grant_type: 'refresh_token', refresh_token: session.refreshToken });
          }
        } catch { this.clear(); return null; }
      }
      return session.accessToken;
    },

    clear() { session = null; write(null); },

    // 디스코드 로그인은 Cognito 로그아웃 주소로 이동합니다. 이메일 로그인은 이 자리에서 끝나므로 false를 돌려줍니다.
    logout() {
      const s = session;
      this.clear();
      if (s && s.method === 'email') {
        if (s.refreshToken) idp('RevokeToken', { Token: s.refreshToken }).catch(() => { /* 이미 지운 토큰이라 무시 */ });
        return false;
      }
      location.assign(`${AUTH_BASE}/logout?` + new URLSearchParams({ client_id: AUTH_CLIENT_ID, logout_uri: REDIRECT_URI }));
      return true;
    },
  };
})();
