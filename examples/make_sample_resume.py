"""Generate a fully fictional resume for local CareerFlow testing."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

DEST = Path(__file__).resolve().parent / '가상지원자_AI엔지니어_이력서.pdf'
pdfmetrics.registerFont(TTFont('Korean', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
body = ParagraphStyle('body', fontName='Korean', fontSize=10, leading=16, textColor=colors.HexColor('#253248'), wordWrap='CJK', spaceAfter=7)
heading = ParagraphStyle('heading', parent=body, fontSize=13, leading=19, textColor=colors.HexColor('#176B70'), spaceBefore=10)
title = ParagraphStyle('title', parent=body, fontSize=24, leading=32)
story = []
def add(text, style=body):
    story.append(Paragraph(text, style))

add('이서준 | 신입 AI 엔지니어', title)
add('CareerFlow 테스트용 가상 이력서 · 실제 지원용 아님', heading)
add('이름, 학습 이력, 프로젝트와 수치는 모두 가상입니다. 실제 개인의 개인정보는 포함하지 않습니다.')
add('소개', heading)
add('Python 기반 서비스 개발과 문서 검색에 관심이 있는 AI 엔지니어 지망생입니다. 작은 기능부터 구현하고 질문별 검색 결과와 응답 근거를 확인하며 개선하는 과정을 좋아합니다.')
add('기술 및 학습', heading)
add('Python, SQL, FastAPI, Git, LangChain, FAISS, pandas, scikit-learn<br/>컴퓨터공학 기초 독학 1년: 자료구조, 데이터베이스, 기계학습 학습.<br/>영어 공식 문서의 예제를 실행하며 API 사용법을 익혔습니다. 정규 개발 경력은 없습니다.')
add('프로젝트 1 | 공개 매뉴얼 검색 챗봇 · 개인 · 3개월', heading)
add('공개된 제품 매뉴얼 20개를 텍스트로 변환하고 문단 단위로 분할했습니다. LangChain과 FAISS로 벡터 검색을 구성하고 LLM 답변에 검색 문서 이름을 함께 표시했습니다. FastAPI로 질문·답변 API를 구현했습니다.')
add('직접 만든 질문 30개로 검색 결과를 확인했습니다. 문서 분할 크기를 조정한 뒤 상위 3개 검색 결과에 정답 근거가 포함된 질문이 18개에서 23개로 늘었습니다. 소규모 자체 평가이며 일반적인 성능을 보장하지 않습니다. 인덱스를 파일로 저장해 실행할 때마다 임베딩을 다시 만들지 않도록 했습니다.')
add('프로젝트 2 | 고객 문의 분류 실험 · 개인 · 1개월', heading)
add('공개 예제 문의 데이터의 중복과 빈 값을 정리하고, TF-IDF와 로지스틱 회귀로 문의 유형을 분류했습니다. 학습·평가 데이터를 분리하고 혼동행렬에서 자주 혼동되는 유형을 확인했습니다. 실행 방법과 실험 설정을 Git 저장소의 README에 정리했습니다.')
add('현재 보완 중인 부분', heading)
add('Dense 벡터 검색은 구현했지만 Sparse·Hybrid 검색 비교와 Reranker 적용 경험은 없습니다. Docker는 학습 중이며 고객사 온프레미스 구축, 운영 배포, 대규모 트래픽 대응 경험은 없습니다. 다음 실험으로 BM25와 벡터 검색 결과를 비교할 계획입니다.')

SimpleDocTemplate(str(DEST), rightMargin=44, leftMargin=44, topMargin=34, bottomMargin=34, title='가상 지원자 AI 엔지니어 이력서', author='CareerFlow sample').build(story)
print(DEST)
