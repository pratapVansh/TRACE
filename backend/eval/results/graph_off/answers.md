# Answers — graph_off

Run 2026-09-13T14:34:45+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 23, calls 0

**PARTIAL (cache-only): 17 items skipped, never answered:** M04, M05, M06, M07, M08, M09, M10, F01, F02, F03, F04, F05, N01, N02, N03, N04, N05

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 23 | 68.8% | 60.9% | 13.0% | 88.1% | 89.1% | 58.1% |
| single_hop | 20 | 64.2% | 55.0% | 15.0% | 88.0% | 90.0% | 55.0% |
| multi_hop | 3 | 100.0% | 100.0% | 0.0% | 88.9% | 83.3% | 79.0% |
| follow_up | 0 | — | — | — | — | — | — |

- Correct refusal on negatives: —
- Grounding sentences: 97 grounded, 4 hedged, 62 unsupported
- LLM latency (uncached calls): p50 — ms, p95 — ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 50.0% | answered | SOP-003 | 28.6% |
| S02 | single_hop | 50.0% | answered | MAN-002 | 57.1% |
| S03 | single_hop | 0.0% | answered | MAN-003, MNT-003 | 42.9% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 75.0% |
| S05 | single_hop | 0.0% | false_refusal | — | 60.0% |
| S06 | single_hop | 100.0% | answered | MNT-001 | 71.4% |
| S07 | single_hop | 100.0% | answered | LOG-002 | 75.0% |
| S08 | single_hop | 100.0% | answered | INS-001 | 33.3% |
| S09 | single_hop | 100.0% | answered | — | 33.3% |
| S10 | single_hop | 33.3% | answered | MAN-003 | 33.3% |
| S11 | single_hop | 50.0% | answered | MAN-003 | 66.7% |
| S12 | single_hop | 0.0% | answered | INS-004 | 66.7% |
| S13 | single_hop | 100.0% | answered | INC-001, PPT-001 | 100.0% |
| S14 | single_hop | 0.0% | false_refusal | INS-002 | 50.0% |
| S15 | single_hop | 0.0% | false_refusal | Equipment, SCN-002 | 50.0% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 60.0% |
| S17 | single_hop | 100.0% | answered | Spare | 33.3% |
| S18 | single_hop | 100.0% | answered | LOG-001, MAN-001, SOP-001 | 50.0% |
| S19 | single_hop | 100.0% | answered | INS-004 | 62.5% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 50.0% |
| M01 | multi_hop | 100.0% | answered | INC-001, MNT-002, PPT-001 | 80.0% |
| M02 | multi_hop | 100.0% | answered | INC-002, Maintenance | 71.4% |
| M03 | multi_hop | 100.0% | answered | MAN-001 | 85.7% |
