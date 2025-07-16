import json
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 환경변수 불러오기
load_dotenv()
SERVICE_KEY = os.getenv('SERVICE_KEY')

# 기준 배치 시각 설정 (9,12,15,18시)
BATCH_TIMES = [9, 12, 15, 18]

# 배치 시간대 설정 함수
def get_batch_time_ranges(now):
    # 현재 시각보다 같거나 이전인 배치 시각 필터링
    valid_times = [h for h in BATCH_TIMES if h <= now.hour]
    # case 1: 현재 시각이 가장 이른 배치 이전일 경우 (ex. 08:30 등)
    if not valid_times:
        first_batch_hour = BATCH_TIMES[0]
        last_batch_hour = BATCH_TIMES[-1]

        prev_day = now - timedelta(days=1)
        # 전날 마지막 배치 시각부터 오늘 첫 배치 시각까지
        bgn = prev_day.replace(hour=last_batch_hour, minute=0, second=0, microsecond=0)
        end = now.replace(hour=first_batch_hour, minute=0, second=0, microsecond=0)
        return bgn.strftime("%Y%m%d%H%M"), end.strftime("%Y%m%d%H%M")

    # case 2: 현재 시각이 배치 시간 이후일 경우 → 가장 가까운 이전 배치 구간 반환
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

# 발송 이력 파일 경로
SENT_FILE = "sent_notifications.json"

# 발송 이력 로딩
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, 'r', encoding="utf-8") as f:
        sent_data = json.load(f)
else:
    sent_data = {}

# 사용자 JSON 파일 읽기
with open("users.json", "r", encoding="utf-8") as f:
    users = json.load(f)

# 배치 시간 구간 계산
now = datetime.now()
#now = datetime.now().replace(hour=8, minute=59, second=0, microsecond=0)
print("now: ", now)
inqryBgnDt, inqryEndDt = get_batch_time_ranges(now)
print(f"[배치 요청 시간 범위] {inqryBgnDt} ~ {inqryEndDt}")

# 사용자별 키워드 기반 API 요청
for user in users:
    name = user['name']
    phone = user['phone']
    keywords = user['keywords']

    # 해당 사용자의 발송 이력 리스트
    user_sent = sent_data.get(phone, [])

    for keyword in keywords:
        # 요청 파라미터 구성
        params = {
            "ServiceKey": SERVICE_KEY,
            "pageNo": 1,
            "numOfRows": 10,
            "inqryDiv": 1,
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "bidNtceNm": keyword,
            "type": "json"
        }

        url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

        # API 요청
        response = requests.get(url, params=params)

        # 요청 URL 출력
        print(f"요청 URL: {response.request.url}")

        # 결과 출력
        # print(response.status_code)
        # print(response.text)
        if response.status_code == 200:
            data = response.json()
            items = data.get("response", {}).get("body", {}).get("items", [])

            print(f"[{name}] 키워드 '{keyword}' 결과:")
            if not items:
                print("조회된 데이터가 없습니다.")
            else:
                new_notices = 0
                for i, item in enumerate(items, start=1):
                    bid_no = item.get("bidNtceNo")
                    if bid_no in user_sent:
                        continue # 중복 알림 방지

                    # 새 알림 출력
                    print(f"{i}. 공고명: {item.get('bidNtceNm')}")
                    print(f"   공고번호: {item.get('bidNtceNo')}")
                    print(f"   공고일시: {item.get('bidNtceDt')}")
                    print(f"   상세URL: {item.get('bidNtceDtlUrl')}")
                    user_sent.append(bid_no)
                    new_notices += 1

                if new_notices == 0:
                    print("모든 결과는 이미 알림 발송됨.")
            print("-"*40)
        else:
            print(f"오류 발생: {response.status_code}")
            print(response.text)

    # 갱신된 이력 저장
    sent_data[phone] = user_sent

# 전체 발송 이력 저장
with open(SENT_FILE, 'w', encoding="utf-8") as f:
    json.dump(sent_data, f, indent=2, ensure_ascii=False)