import json
import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from solapi.model import RequestMessage

# 상수 정의
BATCH_TIMES = [9, 12, 15, 18]
SENT_FILE = "sent_notifications.json"
USERS_FILE = "users.json"

def load_environment():
    """환경변수 로딩"""
    load_dotenv()
    return {
        'service_key': os.getenv('SERVICE_KEY'),
        'coolsms_api_key': os.getenv('COOLSMS_API_KEY'),
        'coolsms_api_secret': os.getenv('COOLSMS_API_SECRET'),
        'coolsms_sender': os.getenv('COOLSMS_SENDER')
    }

def get_batch_time_ranges(now):
    """배치 시간대 설정 함수"""
    valid_times = [h for h in BATCH_TIMES if h <= now.hour]

    # case 1: 현재 시각이 가장 이른 배치 이전일 경우
    if not valid_times:
        prev_day = now - timedelta(days=1)
        # 전날 마지막 배치 시각부터 오늘 첫 배치 시각까지
        bgn = prev_day.replace(hour=BATCH_TIMES[-1], minute=0, second=0, microsecond=0)
        end = now.replace(hour=BATCH_TIMES[0], minute=0, second=0, microsecond=0)
        return bgn.strftime("%Y%m%d%H%M"), end.strftime("%Y%m%d%H%M")

    # case 2: 현재 시각이 배치 시간 이후일 경우
    # 가장 가까운 이전 배치 구간 반환
    prev_batch_hour = max(valid_times)
    idx = BATCH_TIMES.index(prev_batch_hour)

    if idx == 0:
        # 첫 번째 배치인 경우: 전날 마지막 배치 시각부터 오늘 첫 배치 시각까지
        bgn = now.replace(hour=BATCH_TIMES[-1], minute=0, second=0, microsecond=0) - timedelta(days=1)
    else:
        # 일반 배치 구간 (이전 배치 시각 → 현재 배치 시각)
        bgn = now.replace(hour=BATCH_TIMES[idx-1], minute=0, second=0, microsecond=0)

    end = now.replace(hour=prev_batch_hour, minute=0, second=0, microsecond=0)
    return bgn.strftime("%Y%m%d%H%M"), end.strftime("%Y%m%d%H%M")

def make_sms_text_compact(prefix, content_name):
    """간결한 SMS 메시지 내용 생성"""
    max_length = 30
    if len(content_name) > max_length:
        content_name = content_name[:max_length - 3] + "..."
    return prefix + content_name

def send_message(message_service, sender_phone, recipient_phone, message_text):
    """단일 메시지 전송 함수"""
    try:
        message = RequestMessage(
            from_=sender_phone,
            to=recipient_phone,
            text=message_text,
        )
        res = message_service.send(message)
        print(f"문자 발송 완료 (Group ID: {res.group_info.group_id})")
        return True
    except Exception as e:
        print(f"문자 발송 실패: {str(e)}")
        return False

def load_sent_data():
    """발송 이력 로딩"""
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_sent_data(sent_data):
    """발송 이력 저장"""
    with open(SENT_FILE, 'w', encoding="utf-8") as f:
        json.dump(sent_data, f, indent=2, ensure_ascii=False)

def load_users():
    """사용자 정보 로딩"""
    with open(USERS_FILE, 'r', encoding="utf-8") as f:
        return json.load(f)

def build_search_description(keyword=None, notice_org=None, demand_org=None, number=None):
    """검색 조건 설명 생성"""
    search_parts = []
    if keyword:
        search_parts.append(f"키워드='{keyword}'")
    if notice_org:
        search_parts.append(f"공고기관='{notice_org}'")
    if demand_org:
        search_parts.append(f"수요기관='{demand_org}'")
    if number:
        search_parts.append(f"공고번호='{number}'")
    return " + ".join(search_parts)

def make_api_request(api_url, params, name, search_desc):
    """API 요청 및 응답 처리"""
    response = requests.get(api_url, params=params)
    print(f"요청 URL: {response.request.url}")

    if response.status_code != 200:
        print(f"API 오류 발생: {response.status_code}")
        print(response.text)
        return None

    try:
        data = response.json()

        # API 에러 응답 체크
        if "nkoneps.com.response.ResponseError" in data:
            error_info = data["nkoneps.com.response.ResponseError"]["header"]
            error_code = error_info.get("resultCode")
            error_msg = error_info.get("resultMsg")
            print(f"[{name}] API 오류 발생 - 코드: {error_code}, 메시지: {error_msg}")
            return None

        # 정상 응답 처리
        items = data.get("response", {}).get("body", {}).get("items", [])
        print(f"[{name}] 조회 {search_desc} 결과:")

        if not items:
            print("조회된 데이터가 없습니다.")
            return []

        return items

    except (ValueError, KeyError) as e:
        print(f"[{name}] JSON 파싱 오류")
        return None

def check_result_limit_and_notify(items, message_service, sender_phone, recipient_phone, search_desc, limit=5):
    """결과 개수 제한 체크 및 제한 메시지 발송"""
    if len(items) > limit:
        limit_msg = (
            f"[공고 알림]\n"
            f"{search_desc} 새 공고 {len(items)}건 조회\n"
            f"결과가 많아 발송 제한됩니다.\n"
            f"조회조건을 더 구체적으로 설정해주세요.\n"
        )

        if send_message(message_service, sender_phone, recipient_phone, limit_msg):
            print(f"제한 메시지 전송 완료: {len(items)}개 결과")
        return True
    return False
