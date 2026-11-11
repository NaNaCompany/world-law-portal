# Japanese190 structured-text tools

고정된 일본190개 공식JSON의 원본SHA와 기존 공개HTML의 텍스트SHA를 대조하고, 새 텍스트 본문과 별도 후보의 구조·속성·제외 위치·출처 보존 검사를 완료했습니다. 엄격HTML 검사와 HTML5/lxml 독립 검사, 목록·링크·광고/추적태그 정적 검사도 통과했습니다. 이 코드 보존은 실제 사이트 게시를 뜻하지 않습니다. 브라우저 시각 검사는 별도입니다.

실제 Table, ArithFormula, Fig 하위 트리만 위치별 안내와 공식 원문 링크를 남기고 제외합니다. 표 밖 제목·관련조문·Remarks와 일반 법문·부칙 속성·OldNum·Ruby는 보존합니다. 원문 자체의 발췌 제한은 유지하며, 완전본문·현행성·국가별 전체 수집을 보증하지 않습니다.

일부 도구는 저장된 checkpoint에서 회수하고 migration·감사생성 도구는 재구성했습니다. 소실된 과거 전체 코드와 바이트 동일하다는 보증은 하지 않습니다. 원본 법령JSON·아카이브·감사보고서는 이 코드 묶음에 포함하지 않습니다.

## CLI

- `python tests/verify_renderer.py --selftest`: 합성 안전성 검사.
- `python scripts/build_fresh_jp_audit.py --help`: 기준 checkout과 공식 원본 입력의 새 감사 생성.
- `python tests/verify_renderer.py --help`: 명시한 감사/제외맵을 사용한 본문 생성·검증.
- `python scripts/migrate_jp_text_structure.py --help`: 별도 후보에 대한 dry-run, 검증 후 `--apply`. 원본 checkout은 변경하지 않습니다.
- `python scripts/freeze_jp_candidate_manifest.py --help`: 검사된 후보의 파일해시와 전송크기 manifest 생성. commit·외부 게시는 수행하지 않습니다.

모든 경로는 호출자가 CLI로 지정합니다. 독립 후보 검토가 통과하기 전에는 release 준비상태를 승인하지 않으며, 검토된 로컬 commit을 별도로 동결해야 합니다.
