# Design QA

- Scope: issue detail central content panels only.
- Prototype: `http://localhost:3002/issues/issue_discovery_오세훈-gtx-삼성역-논란-정치공세-발언`
- Reference summary panel: `/Users/joungminsung/.codex/generated_images/019eaf15-a77e-7372-9540-46020cd332f8/ig_0dcdd6f47699f7ef016a28f47324608191b4e9a664c84a5e2b.png`
- Reference debate map: `/Users/joungminsung/.codex/generated_images/019eaf15-a77e-7372-9540-46020cd332f8/ig_0dcdd6f47699f7ef016a28f50febfc8191a8051c8e2481b89d.png`
- Reference participation panel: `/Users/joungminsung/.codex/generated_images/019eaf15-a77e-7372-9540-46020cd332f8/ig_0dcdd6f47699f7ef016a28f7ec17588191a5af762a83c5a317.png`

## Checks

- The existing header, issue title block, left section selector, and right rail are preserved.
- The summary section now uses four document-style panels with thin borders, table heads, cell dividers, reliability dots, and a blue/red debate comparison block.
- The debate map now uses a wide matrix table with legend dots, claim A/B columns, conflict, confirmed fact, and supplemental rows.
- Other detail sections share the same document-frame treatment: bordered evidence tables, filter tabs, structured detail rows, and compact section headers.
- The participation section now follows the reference structure with a tab-like top divider, two form columns, and a bottom guidance row.
- At a 1536px desktop viewport, the summary panel has no clipped table content, the right rail remains visible, and page-level horizontal overflow is absent.
- At a 375px mobile viewport, page-level horizontal overflow is absent; wide matrix tables scroll only inside their own content frame.

## Verification

- `npm run lint`
- `npm run build`
- `FACTTRACER_AUDIT_BASE_URL=http://localhost:3002 npm run acceptance:audit`
- Browser checks: summary, debate map, participation, mobile summary, and mobile debate map.

Final result: passed.
