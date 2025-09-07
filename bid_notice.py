import requests
from datetime import datetime
from solapi import SolapiMessageService
from common import *

API_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

def main():
    """입찰공고 알림 서비스 실행"""

    # 환경변수 로딩
    env_vars = load_environment()

    # CoolSMS API 설정
    message_service = SolapiMessageService(
        api_key=env_vars['coolsms_api_key'],
        api_secret=env_vars['coolsms_api_secret']
    )

    # 데이터 로딩
    sent_data = load_sent_data()
    users = load_users()

    # 배치 시간 구간 계산
    now = datetime.now()
    # now = datetime.strptime("202508111900", "%Y%m%d%H%M") # 테스트용 시간 지정
    print(f"현재 시각: {now}")
    inqry_bgn_dt, inqry_end_dt = get_batch_time_ranges(now)
    print(f"[배치 요청 시간 범위] {inqry_bgn_dt} ~ {inqry_end_dt}")

    total_notifications = 0

    # 사용자별 키워드 기반 API 요청
    for user in users:
        name = user['name']
        phone = user['phone']
        search_conditions = user.get('search_conditions', [])

        bid_conditions = [c for c in search_conditions if c.get('type') == 'bid']

        if not bid_conditions:
            print(f"[{name}] 입찰공고 검색 조건이 없습니다.")
            continue

        if name not in sent_data:
            sent_data[name] = {"bid_notices": [], "pre_notices": [], "award_notices": []}

        user_sent = sent_data[name].get('bid_notices', [])

        # 각 조건에 대해 API 요청 실행
        for condition in bid_conditions:
            keyword = condition.get('keyword')
            notice_org = condition.get('notice_org')
            demand_org = condition.get('demand_org')

            if not (keyword or notice_org or demand_org):
                print(f"[{name}] 검색 조건이 없어 건너뜀")
                continue

            # API 요청 파라미터 구성
            params = {
                "ServiceKey": env_vars['service_key'],
                "pageNo": 1,
                "numOfRows": 100,
                "inqryDiv": 1,
                "inqryBgnDt": inqry_bgn_dt,
                "inqryEndDt": inqry_end_dt,
                "indstrytyCd": "1468",
                "type": "json"
            }

            # 검색 조건 설명 생성
            search_parts = []

            # 검색 조건이 있으면 파라미터에 추가
            if keyword:
                params["bidNtceNm"] = keyword
                search_parts.append(f"키워드='{keyword}'")
            if notice_org:
                params["ntceInsttNm"] = notice_org
                search_parts.append(f"공고기관='{notice_org}'")
            if demand_org:
                params["dminsttNm"] = demand_org
                search_parts.append(f"수요기관='{demand_org}'")

            search_desc = " + ".join(search_parts)

            # API 요청
            response = requests.get(API_URL, params=params)
            print(f"요청 URL: {response.request.url}")

            if response.status_code == 200:
                try:
                    data = response.json()

                    # API 에러 응답 체크
                    if "nkoneps.com.response.ResponseError" in data:
                        error_info = data["nkoneps.com.response.ResponseError"]["header"]
                        error_code = error_info.get("resultCode")
                        error_msg = error_info.get("resultMsg")
                        print(f"[{name}] API 오류 발생 - 코드: {error_code}, 메시지: {error_msg}")
                        print("-" * 40)
                        continue

                    # 정상 응답 처리
                    items = data.get("response", {}).get("body", {}).get("items", [])

                    print(f"[{name}] 입찰공고 조회 {search_desc} 결과:")
                    if not items:
                        print("조회된 데이터가 없습니다.")
                        print("-" * 40)
                    else:
                        # 결과가 5개 초과인 경우 제한 메시지 전송
                        if len(items) > 5:
                            limit_msg = (
                                f"[입찰 공고 알림]\n"
                                f"{search_desc} 공고 {len(items)}개 조회\n"
                                f"결과가 많아 발송 제한됩니다.\n"
                                f"조회조건을 구체적으로 정의해주세요.\n"
                            )

                            # 제한 메시지 전송
                            if send_message(message_service, env_vars['coolsms_sender'], phone, limit_msg):
                                print(f"제한 메시지 전송 완료: {len(items)}개 결과")

                            print("-" * 40)
                            continue # 다음 검색 조건으로 넘어감

                        new_notices = 0
                        for i, item in enumerate(items, start=1):
                            bid_no = item.get("bidNtceNo")
                            if bid_no in user_sent:
                                continue  # 중복 알림 방지

                            # 문자 메시지 내용 구성
                            msg_text = (
                                f"[입찰 공고 알림]\n"
                                f"■ 공고명: {item.get('bidNtceNm')}\n"
                                f"■ 공고번호: {item.get('bidNtceNo')}\n"
                                f"■ 수요기관: {item.get('dminsttNm')}\n"
                                f"■ 공고일시: {item.get('bidNtceDt')}\n"
                                f"■ 입찰마감일시: {item.get('bidClseDt')}\n"
                                f"■ 추정가격: {int(item.get('presmptPrce', 0)):,}원\n"
                                f"■ 상세URL: {item.get('bidNtceDtlUrl')}"
                            )

                            # 공고 정보 출력
                            print(
                                f"입찰 공고 | "
                                f"공고명='{item.get('bidNtceNm')}', "
                                f"공고번호={item.get('bidNtceNo')}, "
                                f"수요기관='{item.get('dminsttNm')}', "
                                f"공고일시={item.get('bidNtceDt')}, "
                                f"입찰마감일시={item.get('bidClseDt')}, "
                                f"추정가격={item.get('presmptPrce')}, "
                                f"상세URL={item.get('bidNtceDtlUrl')}"
                            )

                            # 단일 메시지 생성 및 발송
                            if send_message(message_service, env_vars['coolsms_sender'], phone, msg_text):
                                user_sent.append(bid_no)
                                new_notices += 1

                        if new_notices == 0:
                            print("모든 결과는 이미 알림 발송됨.")

                        total_notifications += new_notices
                        print("-" * 40)

                except (ValueError, KeyError) as e:
                    print(f"[{name}] JSON 파싱 오류")
                    print("-" * 40)
                    continue
            else:
                print(f"API 오류 발생: {response.status_code}")
                print(response.text)

        # 사용자별 발송 이력 업데이트
        sent_data[name]['bid_notices'] = user_sent

    # 전체 발송 이력 저장
    save_sent_data(sent_data)
    print(f"* 총 {total_notifications} 건의 새로운 입찰공고 알림 발송\n")

if __name__ == "__main__":
    main()