from datetime import datetime
from solapi import SolapiMessageService
from common import *

API_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusServcPPSSrch"

def format_award_message(item):
    """낙찰공고 메시지 포맷"""
    return (
        f"[입찰 결과 알림]\n"
        f"■ 공고명: {item.get('bidNtceNm')}\n"
        f"■ 공고번호: {item.get('bidNtceNo')}\n"
        f"■ 최종낙찰업체: {item.get('bidwinnrNm')}\n"
        f"■ 낙찰일자: {item.get('fnlSucsfDate')}\n"
    )

def format_award_log(item):
    """낙찰공고 로그 포맷"""
    return (
        f"낙찰 공고 | "
        f"공고명='{item.get('bidNtceNm')}', "
        f"공고번호={item.get('bidNtceNo')}, "
        f"최종낙찰업체='{item.get('bidwinnrNm')}', "
        f"낙찰일자={item.get('fnlSucsfDate')}"
    )

def main():
    """낙찰공고 알림 서비스 실행"""

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

        award_conditions = [c for c in search_conditions if c.get('type') == 'award']

        if not award_conditions:
            print(f"[{name}] 낙찰공고 검색 조건이 없습니다.")
            continue

        if name not in sent_data:
            sent_data[name] = {"bid_notices": [], "pre_notices": [], "award_notices": []}

        user_sent = sent_data[name].get('award_notices', [])

        # 각 조건에 대해 API 요청 실행
        for condition in award_conditions:
            keyword = condition.get('keyword')
            number = condition.get('notice_number')

            if not (keyword or number):
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

            # 검색 조건 파라미터 추가
            if keyword:
                params["bidNtceNm"] = keyword
            if number:
                params["bidNtceNo"] = number

            # 검색 조건 설명 생성
            search_desc = build_search_description(keyword, number)

            # API 요청 및 응답 처리
            items = make_api_request(API_URL, params, name, search_desc)

            if items is None or not items:
                print("-" * 40)
                continue

            # 결과가 5개 초과인 경우 제한 메시지 전송
            if check_result_limit_and_notify(items, message_service, env_vars['coolsms_sender'], phone, search_desc):
                print("-" * 40)
                continue

            # 알림 처리
            new_notices = 0
            for i, item in enumerate(items, start=1):
                bid_no = item.get("bidNtceNo")

                # 중복 알림 방지
                if bid_no in user_sent:
                    continue

                # 메시지 내용 구성 및 발송
                msg_text = format_award_message(item)
                print(format_award_log(item))

                if send_message(message_service, env_vars['coolsms_sender'], phone, msg_text):
                    user_sent.append(bid_no)
                    new_notices += 1

            # 결과 출력
            if new_notices == 0:
                print("모든 결과는 이미 알림 발송됨.")

            total_notifications += new_notices
            print("-" * 40)

        # 사용자별 발송 이력 업데이트
        sent_data[name]['award_notices'] = user_sent

    # 전체 발송 이력 저장
    save_sent_data(sent_data)
    print(f"* 총 {total_notifications} 건의 새로운 낙찰공고 알림 발송\n")

if __name__ == "__main__":
    main()