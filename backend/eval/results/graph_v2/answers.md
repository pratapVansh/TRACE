# Answers — graph_v2

Run 2026-09-16T17:41:12+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 0, calls 40

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 70.7% | 57.1% | 11.4% | 79.8% | 86.7% | 49.1% |
| single_hop | 20 | 62.5% | 50.0% | 15.0% | 84.2% | 90.0% | 50.4% |
| multi_hop | 10 | 82.5% | 60.0% | 0.0% | 85.2% | 83.3% | 50.5% |
| follow_up | 5 | 80.0% | 80.0% | 20.0% | 53.3% | 80.0% | 41.4% |

- Correct refusal on negatives: 100.0%
- Empty answers (model produced no text; scored 0.0 coverage): none
- Grounding sentences: 137 grounded, 8 hedged, 136 unsupported
- LLM latency (uncached calls): p50 2476 ms, p95 4091 ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 50.0% | answered | SOP-003 | 57.1% |
| S02 | single_hop | 50.0% | answered | MAN-002 | 25.0% |
| S03 | single_hop | 0.0% | answered | MAN-003 | 33.3% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 66.7% |
| S05 | single_hop | 0.0% | false_refusal | — | 40.0% |
| S06 | single_hop | 100.0% | answered | MNT-001 | 42.9% |
| S07 | single_hop | 100.0% | answered | LOG-002 | 71.4% |
| S08 | single_hop | 100.0% | answered | INS-001 | 28.6% |
| S09 | single_hop | 100.0% | answered | INC-002 | 50.0% |
| S10 | single_hop | 33.3% | answered | MAN-001, MAN-003 | 85.7% |
| S11 | single_hop | 50.0% | answered | MAN-003, MNT-002 | 70.0% |
| S12 | single_hop | 0.0% | answered | INS-004 | 83.3% |
| S13 | single_hop | 100.0% | answered | INC-001 | 71.4% |
| S14 | single_hop | 0.0% | false_refusal | INS-002 | 20.0% |
| S15 | single_hop | 0.0% | false_refusal | SCN-002 | 75.0% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 16.7% |
| S17 | single_hop | 100.0% | answered | Maintenance, Spare | 20.0% |
| S18 | single_hop | 66.7% | answered | MAN-001, SOP-001 | 28.6% |
| S19 | single_hop | 100.0% | answered | INS-004 | 88.9% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 33.3% |
| M01 | multi_hop | 100.0% | answered | INC-001, MNT-002, PPT-001 | 55.6% |
| M02 | multi_hop | 100.0% | answered | INC-002, Maintenance | 57.1% |
| M03 | multi_hop | 100.0% | answered | Equipment, MAN-001, SOP-001 | 66.7% |
| M04 | multi_hop | 100.0% | answered | MNT-003, Maintenance, Spare | 14.3% |
| M05 | multi_hop | 100.0% | answered | PPT-001, SCN-003 | 16.7% |
| M06 | multi_hop | 66.7% | answered | INS-003, Maintenance | 77.8% |
| M07 | multi_hop | 100.0% | answered | Equipment, INS-003, MAN-003 | 62.5% |
| M08 | multi_hop | 50.0% | answered | LOG-001 | 66.7% |
| M09 | multi_hop | 75.0% | answered | INS-004, Maintenance | 37.5% |
| M10 | multi_hop | 33.3% | answered | — | 50.0% |
| F01 | follow_up | 100.0% | answered | LOG-002, Maintenance, Spare | 0.0% |
| F02 | follow_up | 0.0% | false_refusal | LOG-001, LOG-002, MAN-003 | 25.0% |
| F03 | follow_up | 100.0% | answered | INS-004 | 66.7% |
| F04 | follow_up | 100.0% | answered | MNT-002 | 60.0% |
| F05 | follow_up | 100.0% | answered | MAN-002, Maintenance, Spare | 55.6% |
| N01 | negative | — | correct_refusal | — | 20.0% |
| N02 | negative | — | correct_refusal | — | 0.0% |
| N03 | negative | — | correct_refusal | — | 20.0% |
| N04 | negative | — | correct_refusal | INS-003 | 57.1% |
| N05 | negative | — | correct_refusal | Equipment, INS-004, SCN-002 | 57.1% |
