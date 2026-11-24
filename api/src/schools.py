"""컴공레이더가 공지를 모으는 학교. Item의 subtype(category가 univ일 때)과 같은 이름입니다.

크롤러(crawler/src/common/item.py의 SCHOOLS)와 웹(web/js/data.js의 SUBTYPES.univ)에도 같은 목록이 있어
학교를 추가하면 함께 고쳐야 하며, 어긋나면 crawler/tests/test_constants.py가 실패합니다.
"""
SCHOOLS = ["전북대", "충북대", "경북대", "부산대"]
OTHER = "other"  # "목록에 없어요"를 고른 사용자
