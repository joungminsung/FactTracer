const baseUrl = process.env.FACTTRACER_AUDIT_BASE_URL ?? "http://localhost:3002";

const routes = [
  {
    path: "/",
    required: ["이슈 모니터", "기사 링크", "감지된 사건"],
  },
  {
    path: "/saved",
    required: ["저장 이슈"],
  },
  {
    path: "/verify",
    required: ["기사, 문서, 텍스트를 보도 분석에 보냅니다", "직접 검증 입력"],
  },
  {
    path: "/notifications",
    required: ["알림"],
  },
  {
    path: "/account",
    required: ["내 계정"],
  },
  {
    path: "/issues/MISSING-001",
    required: ["이슈를 찾을 수 없습니다", "이슈 모니터 보기"],
  },
  {
    path: "/reports/MISSING-001",
    required: ["리포트로 만들 이슈를 찾을 수 없습니다"],
  },
  {
    path: "/admin",
    required: ["운영 콘솔", "검토 목록"],
  },
  {
    path: "/admin/issues/ISS-260608-001",
    required: ["검토 대상을 찾을 수 없습니다", "운영 메뉴"],
  },
  {
    path: "/admin/reports",
    required: ["신고 표현 처리"],
  },
  {
    path: "/admin/sources",
    required: ["출처 관리"],
  },
  {
    path: "/admin/agents",
    required: ["자동 처리 기록"],
  },
  {
    path: "/login",
    required: ["로그인"],
  },
  {
    path: "/signup",
    required: ["회원가입"],
  },
  {
    path: "/missing-route",
    required: ["페이지를 찾을 수 없습니다"],
  },
];

const forbiddenVisibleTerms = [
  "API",
  "서버",
  "환경변수",
  "토큰",
  "Bearer",
  "응답",
  "데이터",
  "endpoint",
  "URL",
  "PRD",
  "Issue",
  "Queue",
  "Agent",
  "에이전트",
  "검토 큐",
  "도메인",
  "더미",
  "dummy",
  "mock",
  "개발",
];

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchRoute(path) {
  const response = await fetch(new URL(path, baseUrl), {
    headers: { accept: "text/html" },
  });
  const html = await response.text();
  return { html, path, status: response.status, text: stripHtml(html) };
}

const failures = [];

try {
  const health = await fetch(new URL("/", baseUrl), {
    headers: { accept: "text/html" },
  });
  if (!health.ok) {
    failures.push(`${baseUrl} is reachable but returned ${health.status} for /`);
  }
} catch {
  console.error(
    `Acceptance audit needs a running app. Start it first, for example: npm run start -- --port 3002`,
  );
  process.exit(1);
}

for (const route of routes) {
  const result = await fetchRoute(route.path);
  const allowedStatuses = route.path === "/missing-route" ? [404] : [200];

  if (!allowedStatuses.includes(result.status)) {
    failures.push(`${route.path} returned ${result.status}`);
  }

  for (const required of route.required) {
    if (!result.text.includes(required)) {
      failures.push(`${route.path} is missing required text: ${required}`);
    }
  }

  for (const term of forbiddenVisibleTerms) {
    if (result.text.includes(term)) {
      failures.push(`${route.path} exposes forbidden UI term: ${term}`);
    }
  }

  const hashTargets = new Set(
    Array.from(result.html.matchAll(/href="#([^"]+)"/g), (match) => match[1]),
  );
  for (const target of hashTargets) {
    if (
      !result.html.includes(`id="${target}"`) &&
      !result.html.includes(`id='${target}'`)
    ) {
      failures.push(`${route.path} has an in-page link without target: #${target}`);
    }
  }
}

if (failures.length > 0) {
  console.error("Acceptance audit failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log(`Acceptance audit passed for ${routes.length} routes at ${baseUrl}`);
