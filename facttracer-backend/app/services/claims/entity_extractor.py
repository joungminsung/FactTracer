from __future__ import annotations

import re


DATE_PATTERN = re.compile(r"(\d{4}[.-]\d{1,2}[.-]\d{1,2}|\d{1,2}월\s*\d{1,2}일|\d{1,2}:\d{2})")
NUMBER_PATTERN = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?\s*(?:명|곳|건|개|원|억|조|%|퍼센트|시간|분|장)?)")
ORG_PATTERN = re.compile(r"([가-힣A-Za-z0-9]{2,}(?:위원회|부|청|처|원|공사|공단|기관|정부|국회|법원|경찰|소방|시청|도청))")
PLACE_PATTERN = re.compile(r"([가-힣]{2,}(?:시|군|구|동|읍|면|도|광역시|특별시))")


def extract_entities(text: str) -> dict:
    return {
        "dates": sorted(set(DATE_PATTERN.findall(text))),
        "numbers": sorted(set(NUMBER_PATTERN.findall(text))),
        "organizations": sorted(set(ORG_PATTERN.findall(text))),
        "places": sorted(set(PLACE_PATTERN.findall(text))),
    }
