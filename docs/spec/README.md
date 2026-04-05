# Founder / architecture spec (Markdown mirrors)

원본 Word 문서는 로컬 `~/Downloads/tech500_*.docx` 에 두고, 아래처럼 재생성할 수 있습니다.

```bash
python3 scripts/docx_to_spec_md.py \
  --downloads ~/Downloads \
  --out docs/spec
```

포함 파일(자동 추출본, 표·레이아웃은 단순화됨):

- `tech500_factor_ai_architecture_blueprint_ko_v2.md`
- `tech500_cursor_agent_protocol_ko.md`
- `tech500_plan_mode_roadmap_ko.md`
- `tech500_phase0_cursor_workorder_ko.md`

법적·제품 SSOT는 여전히 원본 `.docx`를 기준으로 두고, 레포 MD는 Cursor/에이전트가 읽기 쉬운 복사본입니다.
