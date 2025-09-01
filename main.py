from bid_notice import main as bid_main
from pre_notice import main as pre_main
from award_notice import main as award_main

def main():
    """공고 알림 서비스 실행"""
    try:
        # 입찰공고 처리
        bid_main()
        # 사전공고 처리
        pre_main()
        # 낙찰공고 처리
        award_main()

    except Exception as e:
        print(f"서비스 실행 중 오류 발생: {str(e)}")

if __name__ == '__main__':
    main()