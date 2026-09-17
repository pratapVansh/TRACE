# Answers — rerank_off

Run 2026-09-15T17:24:11+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 37, calls 3

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 63.8% | 48.6% | 14.3% | 75.0% | 81.4% | 45.8% |
| single_hop | 20 | 62.5% | 50.0% | 15.0% | 75.9% | 85.0% | 47.5% |
| multi_hop | 10 | 78.2% | 50.0% | 0.0% | 83.3% | 75.0% | 55.6% |
| follow_up | 5 | 40.0% | 40.0% | 40.0% | 56.7% | 80.0% | 19.7% |

- Correct refusal on negatives: 80.0%
- Empty answers (model produced no text; scored 0.0 coverage): none
- Grounding sentences: 127 grounded, 9 hedged, 138 unsupported
- LLM latency (uncached calls): p50 2076 ms, p95 5391 ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 50.0% | answered | MAN-003, SOP-003 | 66.7% |
| S02 | single_hop | 50.0% | answered | MAN-002 | 50.0% |
| S03 | single_hop | 0.0% | false_refusal | — | 20.0% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 57.1% |
| S05 | single_hop | 0.0% | false_refusal | — | 20.0% |
| S06 | single_hop | 100.0% | answered | MNT-001 | 33.3% |
| S07 | single_hop | 100.0% | answered | Equipment, INC-002, LOG-002 | 42.9% |
| S08 | single_hop | 100.0% | answered | INS-001 | 66.7% |
| S09 | single_hop | 100.0% | answered | INC-002, LOG-002 | 42.9% |
| S10 | single_hop | 33.3% | answered | MAN-003 | 85.7% |
| S11 | single_hop | 0.0% | answered | MNT-002 | 85.7% |
| S12 | single_hop | 0.0% | answered | INS-004 | 37.5% |
| S13 | single_hop | 100.0% | answered | INC-001, PPT-001 | 66.7% |
| S14 | single_hop | 50.0% | answered | INS-002, LOG-001, MAN-002 | 50.0% |
| S15 | single_hop | 0.0% | false_refusal | SCN-002 | 28.6% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 60.0% |
| S17 | single_hop | 100.0% | answered | Spare | 20.0% |
| S18 | single_hop | 66.7% | answered | MAN-001, SOP-001 | 42.9% |
| S19 | single_hop | 100.0% | answered | INS-004 | 33.3% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 40.0% |
| M01 | multi_hop | 50.0% | answered | INC-001, PPT-001 | 85.7% |
| M02 | multi_hop | 100.0% | answered | INC-002, LOG-002 | 62.5% |
| M03 | multi_hop | 100.0% | answered | MAN-001, SOP-001 | 60.0% |
| M04 | multi_hop | 100.0% | answered | MNT-003, Spare | 66.7% |
| M05 | multi_hop | 40.0% | answered | PPT-001, SCN-003 | 37.5% |
| M06 | multi_hop | 66.7% | answered | INS-003, Maintenance | 57.1% |
| M07 | multi_hop | 100.0% | answered | Equipment, MAN-003 | 62.5% |
| M08 | multi_hop | 50.0% | answered | — | 50.0% |
| M09 | multi_hop | 75.0% | answered | INS-004, Maintenance | 14.3% |
| M10 | multi_hop | 100.0% | answered | MNT-001, SCN-001 | 60.0% |
| F01 | follow_up | 100.0% | answered | INC-002, LOG-002, Spare | 0.0% |
| F02 | follow_up | 0.0% | false_refusal | MAN-003 | 25.0% |
| F03 | follow_up | 0.0% | false_refusal | INS-004 | 0.0% |
| F04 | follow_up | 100.0% | answered | MNT-002, Spare | 33.3% |
| F05 | follow_up | 0.0% | answered | Maintenance | 40.0% |
| N01 | negative | — | correct_refusal | — | 40.0% |
| N02 | negative | — | correct_refusal | — | 0.0% |
| N03 | negative | — | correct_refusal | INS-004, LOG-002, Spare | 40.0% |
| N04 | negative | — | missed_refusal | INS-003 | 50.0% |
| N05 | negative | — | correct_refusal | INS-004 | 40.0% |
