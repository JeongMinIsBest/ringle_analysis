# 블로그 리뷰 및 구글 플레이 리뷰 크롤링/분석 🔠
화상 영어 서비스 '링글(Ringle)'에 대한 사용자들의 피드백과 여론을 수집하고 분석했습니다. Google Play 스토어의 앱 리뷰와 네이버 블로그 포스트를 주요 데이터 소스로 활용하며, 데이터 수집(Crawling/Scraping), 전처리, 키워드 추출, 토픽 분류 및 감성 분석 과정을 정리했습니다.
<br/>

## 🗂️ 프로젝트 구조
```
ringle_analysis/
├── googleplay_review/           # Google Play 스토어 리뷰 분석
│   ├── google_play_review.ipynb  # 리뷰 수집, 필터링 및 카테고리 분류 노트북
│   ├── ringle_googleplay_reviews.csv  # 수집된 원본 리뷰 데이터
│   ├── ringle_reviews_filtered.csv    # 특정 키워드로 필터링된 리뷰
│   └── ringle_reviews_classified.csv  # 카테고리별로 분류된 리뷰 데이터
├── naver_blog_review/           # 네이버 블로그 포스트 분석
│   ├── riingle_naver_blog_crawler.py # 네이버 Search API 기반 블로그 크롤러
│   ├── ringle_blog_analysis.ipynb     # 블로그 본문 전처리, TF-IDF 키워드 추출 및 감성 분석 노트북
│   └── naver_blog_ringle.csv          # 크롤링된 블로그 포스트 데이터
└── .venv/                       # Python 가상 환경
```
<br/>

## 🚀 주요 기능 및 워크플로우

### 1. Google Play 스토어 리뷰 분석 (`googleplay_review/`)
*   **리뷰 수집** : `google-play-scraper` 라이브러리를 사용하여 링글 앱의 최신 리뷰를 수집합니다.
*   **키워드 필터링** : '오류', '버그', '끊김', '로그인' 등 사용자가 겪는 기술적 불편함과 관련된 키워드를 포함하는 리뷰를 별도로 추출합니다.
*   **카테고리 분류** : 리뷰 내용을 바탕으로 다음과 같은 5가지 카테고리로 자동 분류합니다.
    *   인식_분석_문제
    *   UX_조작성_문제
    *   안정성_문제
    *   반복_복습_문제
    *   접근_로그인_문제
  
### 2. 네이버 블로그 분석 (`naver_blog_review/`)
*   **데이터 크롤링** : `ringle_naver_blog_crawler.py`를 통해 네이버 검색 API로 블로그 링크를 확보한 후, 각 블로그의 본문 내용을 크롤링합니다. 광고성 게시글을 필터링하는 로직이 포함되어 있습니다.
*   **텍스트 전처리** : 불용어(Stopwords) 제거, 정규화 등을 통해 분석에 적합한 형태로 데이터를 가공합니다.
*   **키워드 분석** : TF-IDF(Term Frequency-Inverse Document Frequency) 알고리즘을 사용하여 블로그 포스트에서 가장 중요하게 다뤄지는 키워드 Top 15를 추출하고 시각화합니다.
*   **토픽 및 감성 분석** :
    *   문장 단위로 쪼개어 '가격/가성비', '피드백/교정', '스피킹/학습' 등의 토픽으로 분류합니다.
    *   자체 정의된 감성 사전을 바탕으로 각 토픽별 긍정/부정 점수를 산출하여 사용자들의 체감 만족도를 분석합니다.
<br/>

## 💻 설치 및 실행 방법
1.  Python 환경 준비 (Python 3.10 권장)
2.  필수 라이브러리 설치
    ```
    pip install pandas matplotlib scikit-learn wordcloud google-play-scraper requests beautifulsoup4 tqdm lxml
    ```
3.  네이버 블로그 크롤러 실행 시, `ringle_naver_blog_crawler.py` 상단의 `NAVER_CLIENT_ID`와 `NAVER_CLIENT_SECRET`에 본인의 네이버 API ID/Secret을 입력해야 합니다.
4.  각 폴더의 `.ipynb` 파일을 주피터 노트북 환경에서 순차적으로 실행합니다.
<br/>
