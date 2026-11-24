"""JWT Authorizer가 넘겨 준 Cognito 토큰 클레임에서 사용자 정보를 꺼냅니다."""
import re


def claims_of(event):
    try:
        return event["requestContext"]["authorizer"]["jwt"]["claims"] or {}
    except (KeyError, TypeError):
        return {}


def user_sub(event):
    """Cognito 사용자의 고유 ID(sub). 로그인 방법과 상관없이 있습니다."""
    sub = claims_of(event).get("sub")
    return str(sub) if sub else None


def discord_id(event):
    """디스코드로 로그인한 사용자의 디스코드 ID. 이메일 가입자 등 그 밖의 사용자는 None.

    Cognito는 디스코드 사용자 이름을 "Discord_<디스코드 ID>"로 만들고, 그 사용자를
    "<User Pool ID>_Discord" 그룹에 자동으로 넣습니다. 이메일 가입자가 사용자 이름을
    "discord_123..."처럼 지어 남의 구독을 건드리지 못하도록 그룹까지 확인합니다.
    (HTTP API는 배열 클레임을 "[a b]" 같은 문자열로 넘겨 줍니다.)
    """
    claims = claims_of(event)
    username = claims.get("username")
    if not username:
        return None
    groups = re.findall(r"[\w-]+", str(claims.get("cognito:groups", "")))
    if not any(g.endswith("_Discord") for g in groups):
        return None
    provider, _, user_id = str(username).partition("_")
    return user_id if provider.lower() == "discord" and user_id.isdigit() else None
