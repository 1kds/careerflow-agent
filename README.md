# CareerFlow

채용공고와 이력서를 비교하고 지원 준비 계획을 관리하는 툴콜링 기반 취업 준비 에이전트 MVP입니다.

## 역할 분담

- 모델: 사용자 의도 파악, 공고 역량 추출, 이력서 근거 비교, 준비 계획 제안
- 툴: 공고·이력서·분석 결과·할 일의 조회 및 저장, 날짜와 원문 근거 검증
- 사용자: 실제 할 일 등록 전 계획 승인

## 실행

Python 3.11 이상과 사용할 공급자의 API 키가 필요합니다.

```bash
git clone https://github.com/1kds/careerflow-agent.git
cd careerflow-agent
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

OpenAI로 실행:

```bash
export OPENAI_API_KEY="your-api-key"
careerflow --provider openai --trace
```

Gemini API로 실행:

```bash
export GEMINI_API_KEY="your-api-key"
careerflow --provider gemini --trace
```

공급자별 기본 모델은 OpenAI `gpt-5.6-terra`, Gemini `gemini-3.7-flash`입니다. 공급자는 `CAREERFLOW_PROVIDER`, 모델은 `OPENAI_MODEL`·`GEMINI_MODEL` 또는 공통 `--model` 옵션으로 변경할 수 있습니다.

CareerFlow는 Gemini Interactions API 호출에 `store=False`를 사용하고 대화 단계를 실행 중인 프로세스 메모리에서 관리합니다. 단, 입력 내용은 모델 처리를 위해 API 공급자에게 전송됩니다. Gemini 무료 티어에는 실제 이력서나 개인정보를 입력하지 말고 합성·비식별 데이터만 사용하세요. 실제 개인정보를 처리하려면 적법한 동의와 최소 수집 원칙을 적용하고, 유료 티어 약관 및 프로젝트의 데이터 설정을 먼저 검토해야 합니다.

## 데모 순서

1. `홍길동의 이력서를 등록해줘: ...`
2. `ABC AI Engineer 공고를 저장하고 역량을 분석해줘: ...`
3. `공고 1번과 이력서 1번을 비교해줘.`
4. `지원 마감일까지 할 일 계획을 보여줘.`
5. 계획을 확인한 뒤 `좋아, 등록해줘.`

`--trace`를 사용하면 모델이 선택한 툴과 실행 결과가 출력되어 발표 시 전체 흐름을 보여줄 수 있습니다. 이름, 이력서 원문, 이력서 근거, 채용공고 원문은 자동으로 마스킹되지만 자유 서술 필드에 개인정보가 포함될 수 있으므로 합성 데이터 데모에서만 사용하세요.

## 테스트

API 키 없이 저장·검증 툴을 테스트할 수 있습니다.

```bash
python -m unittest discover -v
```

## 핵심 안전장치

- 추출된 역량의 `evidence`가 공고 원문에 없으면 저장하지 않습니다.
- `not_found`는 역량 부재가 아니라 이력서에서 근거를 찾지 못했다는 의미입니다.
- 지원 마감일 이후의 작업은 등록하지 않습니다.
- 시스템 프롬프트에서 사용자 승인 전 할 일 등록을 금지합니다.
