import requests
import os
from dotenv import load_dotenv

# 환경변수 불러오기
load_dotenv()
SERVICE_KEY = os.getenv('SERVICE_KEY')

# API 파라미터 설정
params = {
    "ServiceKey": SERVICE_KEY,
    "pageNo": 1,
    "numOfRows": 10,
    "inqryDiv": 1,
    "type": "json"
}

url = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

# API 요청
response = requests.get(url, params=params)

# 결과 출력
# print(response.status_code)
# print(response.text)
if response.status_code == 200:
    data = response.json()
    items = data.get("response", {}).get("body", {}).get("items", [])

    if not items:
        print("조회된 데이터가 없습니다.")
    else:
        print(f"총 {len(items)}건이 조회되었습니다.\n")
        for i, item in enumerate(items, start=1):
            print(f"{i}. 공고명: {item.get('bidNtceNm')}")
            print(f"   공고번호: {item.get('bidNtceNo')}")
            print(f"   공고기관: {item.get('ntceInsttNm')}")
            print("---")
else:
    print(f"오류 발생: {response.status_code}")
    print(response.text)