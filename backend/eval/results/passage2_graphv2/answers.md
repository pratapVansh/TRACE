# Answers — passage2_graphv2

Run 2026-09-18T18:01:43+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 8, calls 32

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 87.6% | 80.0% | 5.7% | 85.5% | 93.3% | 59.0% |
| single_hop | 20 | 87.5% | 85.0% | 5.0% | 85.1% | 95.0% | 60.8% |
| multi_hop | 10 | 91.7% | 70.0% | 0.0% | 91.7% | 86.7% | 59.0% |
| follow_up | 5 | 80.0% | 80.0% | 20.0% | 75.0% | 100.0% | 51.7% |

- Correct refusal on negatives: 100.0%
- Empty answers (model produced no text; scored 0.0 coverage): none
- Grounding sentences: 157 grounded, 12 hedged, 106 unsupported
- LLM latency (uncached calls): p50 2457 ms, p95 5406 ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 100.0% | answered | SOP-003 | 75.0% |
| S02 | single_hop | 100.0% | answered | MAN-002 | 50.0% |
| S03 | single_hop | 100.0% | answered | MNT-003 | 50.0% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 57.1% |
| S05 | single_hop | 0.0% | false_refusal | — | 40.0% |
| S06 | single_hop | 100.0% | answered | MNT-001 | 66.7% |
| S07 | single_hop | 100.0% | answered | INC-002, LOG-002, Maintenance | 100.0% |
| S08 | single_hop | 100.0% | answered | INS-001 | 66.7% |
| S09 | single_hop | 100.0% | answered | INC-002, Maintenance | 57.1% |
| S10 | single_hop | 100.0% | answered | MAN-003 | 83.3% |
| S11 | single_hop | 50.0% | answered | MAN-003 | 33.3% |
| S12 | single_hop | 0.0% | answered | INS-004 | 50.0% |
| S13 | single_hop | 100.0% | answered | INC-001, MNT-002, PPT-001 | 87.5% |
| S14 | single_hop | 100.0% | answered | INS-002 | 75.0% |
| S15 | single_hop | 100.0% | answered | SCN-002 | 50.0% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 50.0% |
| S17 | single_hop | 100.0% | answered | Maintenance, Spare | 16.7% |
| S18 | single_hop | 100.0% | answered | SOP-001 | 62.5% |
| S19 | single_hop | 100.0% | answered | INS-004, Maintenance | 62.5% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 83.3% |
| M01 | multi_hop | 100.0% | answered | INC-001, MNT-002 | 57.1% |
| M02 | multi_hop | 100.0% | answered | INC-002, Maintenance | 42.9% |
| M03 | multi_hop | 100.0% | answered | Equipment, MAN-001, Maintenance, SOP-001 | 100.0% |
| M04 | multi_hop | 100.0% | answered | Spare | 33.3% |
| M05 | multi_hop | 100.0% | answered | SCN-003 | 14.3% |
| M06 | multi_hop | 66.7% | answered | INS-003, Maintenance | 100.0% |
| M07 | multi_hop | 100.0% | answered | Equipment, INS-003, MAN-003 | 66.7% |
| M08 | multi_hop | 75.0% | answered | LOG-001, MNT-002 | 66.7% |
| M09 | multi_hop | 75.0% | answered | INS-004, Maintenance | 28.6% |
| M10 | multi_hop | 100.0% | answered | MNT-001, SCN-001 | 80.0% |
| F01 | follow_up | 100.0% | answered | INC-002, LOG-002, Maintenance, Spare | 75.0% |
| F02 | follow_up | 0.0% | false_refusal | MAN-003 | 42.9% |
| F03 | follow_up | 100.0% | answered | INS-004 | 57.1% |
| F04 | follow_up | 100.0% | answered | MNT-002 | 83.3% |
| F05 | follow_up | 100.0% | answered | MAN-002, Maintenance | 0.0% |
| N01 | negative | — | correct_refusal | — | 0.0% |
| N02 | negative | — | correct_refusal | — | 0.0% |
| N03 | negative | — | correct_refusal | INS-004, Maintenance, Spare | 0.0% |
| N04 | negative | — | correct_refusal | INS-003, Maintenance | 83.3% |
| N05 | negative | — | correct_refusal | Equipment, INS-004, SCN-002 | 50.0% |
