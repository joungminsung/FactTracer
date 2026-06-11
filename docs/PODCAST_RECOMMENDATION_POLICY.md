# 팟캐스트 추천 정책

기준일: 2026-06-10

## 목적

팟캐스트 추천은 음악 서비스처럼 사용자의 관심을 반영하되, FactTracer의 목적은 `국민의 알 권리`다. 그래서 단순 소비 선호보다 사회적 영향도, 검증 필요도, 출처 신뢰도를 우선한다.

## 로그인 사용자 점수

로그인 사용자의 개인화 피드는 기존 이슈 랭킹 점수와 팟캐스트 소비 로그를 함께 사용한다.

기본 점수:

```text
personalizedScore =
  impactScore * 0.25
  + controversyScore * 0.20
  + freshnessScore * 0.20
  + momentumScore * 0.15
  + personalPreferenceScore
```

개인 선호는 `UserInterestProfile`에 누적한다.

- `podcast_home_impression`: 약한 관심 신호
- `podcast_play_start`: 명시적 관심 신호
- `podcast_progress`: 중간 관심 신호
- `podcast_complete`: 강한 관심 신호
- `podcast_source_click`: 출처 확인 관심 신호
- `podcast_skip`: 약한 감점 신호

반영 대상:

- 카테고리: `topic_weights_json`
- 포맷: `event_group_weights_json["podcast_format:{format}"]`

## 비로그인 사용자 기본 추천

비로그인 사용자는 개인 히스토리를 쓰지 않는다.

우선순위:

1. 사회적 영향도가 높은 이슈
2. 검증 필요도와 논란도가 높은 이슈
3. 최신 업데이트가 있는 이슈
4. 출처가 충분하고 품질 게이트를 통과한 회차
5. 카테고리 다양성

비로그인 홈 노출 순서:

1. 오늘의 추천 팟캐스트
2. 데일리 팟캐스트
3. 긴급 확인
4. 특집 팟캐스트
5. 최신 회차
6. 많이 확인하는 이슈
7. 카테고리별 회차

## 공개 제외

아래 회차는 추천 피드에 공개하지 않는다.

- 출처 수가 운영 기준보다 부족한 회차
- 민감 주제에서 공식 출처가 필요하지만 충족하지 못한 회차
- 스크립트가 비어 있는 회차
- 품질 점수가 70점 미만인 회차
- 상태가 `draft` 또는 `archived`인 회차

## 포맷 다양성

동일 이슈는 필요에 따라 다른 길이와 형식으로 생성할 수 있다.

- 짧은 버전: `solo`
- 표준 버전: 이슈 신호에 따라 `solo`, `panel_2`, `panel_3`
- 심층 버전: `panel_3`

이 방식으로 같은 이슈의 짧은 버전과 긴 버전을 동시에 운영할 수 있다.
