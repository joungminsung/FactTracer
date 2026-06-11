# FactTracer

## Docker로 실행

Docker Desktop을 켠 뒤 루트 폴더에서 실행합니다.

```bash
docker compose up --build
```

브라우저 주소:

- 웹: http://localhost:3000
- API: http://localhost:8000

macOS에서는 `start-facttracer.command` 파일을 더블클릭하면 컨테이너를 백그라운드로 띄우고 웹 화면을 엽니다.

## 환경 변수

AI 분석을 쓰려면 `facttracer-backend/.env`에 API 키를 넣습니다. 루트 Docker Compose는 이 파일을 컨테이너 환경 변수로 전달합니다.

기본 Docker 구성은 별도 Postgres/Redis 없이 SQLite 볼륨과 내장 스케줄러/워커로 동작합니다. 운영형 Postgres/RQ 구성은 `facttracer-backend/docker-compose.yml`을 사용합니다.
