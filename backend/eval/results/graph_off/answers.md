# Answers — graph_off

Run 2026-09-14T10:51:11+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 23, calls 17

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 73.6% | 62.9% | 11.4% | 84.3% | 91.9% | 60.8% |
| single_hop | 20 | 64.2% | 55.0% | 15.0% | 88.0% | 90.0% | 55.0% |
| multi_hop | 10 | 89.2% | 70.0% | 0.0% | 90.0% | 91.7% | 66.1% |
| follow_up | 5 | 80.0% | 80.0% | 20.0% | 60.0% | 100.0% | 73.4% |

- Correct refusal on negatives: 100.0%
- Grounding sentences: 173 grounded, 6 hedged, 116 unsupported
- LLM latency (uncached calls): p50 2596 ms, p95 5300 ms

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
| M04 | multi_hop | 100.0% | answered | MNT-003, Spare | 71.4% |
| M05 | multi_hop | 100.0% | answered | PPT-001, SCN-003 | 50.0% |
| M06 | multi_hop | 66.7% | answered | INS-003, LOG-002, Maintenance | 70.0% |
| M07 | multi_hop | 100.0% | answered | Equipment, MAN-003 | 57.1% |
| M08 | multi_hop | 50.0% | answered | INS-002, LOG-001, MNT-002 | 41.7% |
| M09 | multi_hop | 75.0% | answered | INS-004, Maintenance | 57.1% |
| M10 | multi_hop | 100.0% | answered | MNT-001, SCN-001 | 76.9% |
| F01 | follow_up | 100.0% | answered | INC-002, LOG-002, Spare | 57.1% |
| F02 | follow_up | 0.0% | false_refusal | LOG-001, LOG-002, MAN-003 | 50.0% |
| F03 | follow_up | 100.0% | answered | INS-004 | 88.9% |
| F04 | follow_up | 100.0% | answered | MNT-002 | 83.3% |
| F05 | follow_up | 100.0% | answered | MAN-002, Maintenance, Spare | 87.5% |
| N01 | negative | — | correct_refusal | — | 0.0% |
| N02 | negative | — | correct_refusal | Equipment, MAN-003 | 40.0% |
| N03 | negative | — | correct_refusal | — | 0.0% |
| N04 | negative | — | correct_refusal | INS-003 | 83.3% |
| N05 | negative | — | correct_refusal | INS-004 | 0.0% |
