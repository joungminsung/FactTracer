# 팟캐스트 로컬 운영 검증 증거

검증일: 2026-06-11  
대상: 로컬 Docker API `http://127.0.0.1:8000`, 로컬 Docker Web `http://127.0.0.1:3000`

## 요약

로컬 Docker 환경에서 유효한 `OPENAI_API_KEY`를 주입한 뒤 팟캐스트 실제 TTS 생성, 공개 오디오 전달, 이벤트/개인화 누적, 관리자 실패 작업 표시를 검증했다.

최종 audit:

```json
{
  "status": "passed",
  "passed": true,
  "summary": {
    "failed": 0,
    "passed": 18,
    "total": 18,
    "warnings": 0
  },
  "failedChecks": [],
  "warningChecks": []
}
```

남은 항목 래퍼 검증:

```json
{
  "passed": true,
  "summary": {
    "failed": 0,
    "passed": 5,
    "total": 5
  },
  "items": {
    "live_tts_audio": true,
    "staging_smoke_and_audit": true,
    "live_tts_delivery": true,
    "recommendation_events_profile": true,
    "admin_failed_job_display_data": true
  }
}
```

## 생성된 OpenAI TTS 회차

```json
{
  "episodeId": "podcast_c5b5a3d4f0cb",
  "title": "긴급 팟캐스트: 레디코리아 훈련: 열차 탈선 및 항공유 폭발 대비 실제 같은 재난 대응 훈련 · 짧은 브리핑",
  "ttsProvider": "openai",
  "ttsStatus": "completed",
  "publicAudioUrl": "/v1/podcasts/podcast_c5b5a3d4f0cb/audio",
  "audioStream": {
    "bytesRead": 256000,
    "contentType": "audio/wav",
    "status": 200
  }
}
```

로컬 복사 파일:

```text
qa/podcast-audio/podcast_c5b5a3d4f0cb.wav
```

## 관리자 화면 표시 검증

로그인 쿠키를 포함해 `http://127.0.0.1:3000/admin/podcasts` 서버 렌더링 HTML을 확인했다.

검증 결과:

```json
{
  "hasFailedSection": true,
  "hasRenderJob": true,
  "hasKoreanUserMessage": true,
  "hasRawNotFound": false
}
```

표시된 운영자 메시지:

```text
팟캐스트 음성 렌더링 작업이 실패했습니다. TTS 설정과 회차 대본을 확인해 주세요.
```

## 재현 명령

```bash
cd facttracer-backend
python scripts/verify_podcast_remaining_work.py \
  --api-base-url http://127.0.0.1:8000 \
  --admin-email podcast-admin-smoke@example.com \
  --admin-password password123 \
  --feed latest \
  --force
```

비용 없이 최종 상태만 재확인:

```bash
cd facttracer-backend
python scripts/audit_podcast_operations.py \
  --api-base-url http://127.0.0.1:8000 \
  --require-env-vars \
  --require-live-tts \
  --require-audio-stream \
  --require-events \
  --require-failed-job \
  --require-seed-script \
  --require-tts-retry-evidence \
  --json
```

## 범위

이 문서는 로컬 Docker 운영 검증 증거다. 별도 스테이징/배포 URL이 존재하면 같은 명령을 해당 `--api-base-url`로 다시 실행해야 한다.
