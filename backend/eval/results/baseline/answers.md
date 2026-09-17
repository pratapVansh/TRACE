# Answers — baseline

Run 2026-09-16T18:31:12+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 40, calls 1

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 74.0% | 60.0% | 11.4% | 78.4% | 84.8% | 49.0% |
| single_hop | 20 | 65.0% | 50.0% | 15.0% | 75.4% | 90.0% | 49.3% |
| multi_hop | 10 | 89.2% | 70.0% | 0.0% | 95.0% | 76.7% | 53.8% |
| follow_up | 5 | 80.0% | 80.0% | 20.0% | 56.7% | 80.0% | 38.1% |

- Correct refusal on negatives: 100.0%
- Empty answers (model produced no text; scored 0.0 coverage): none
- Grounding sentences: 140 grounded, 8 hedged, 132 unsupported
- LLM latency (uncached calls): p50 2331 ms, p95 2331 ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 50.0% | answered | MAN-003, SOP-003 | 50.0% |
| S02 | single_hop | 50.0% | answered | MAN-002 | 12.5% |
| S03 | single_hop | 0.0% | answered | MAN-003 | 16.7% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 85.7% |
| S05 | single_hop | 0.0% | false_refusal | — | 20.0% |
| S06 | single_hop | 100.0% | answered | LOG-002, MNT-001 | 66.7% |
| S07 | single_hop | 100.0% | answered | Equipment, INC-002, LOG-002 | 28.6% |
| S08 | single_hop | 100.0% | answered | INS-001 | 60.0% |
| S09 | single_hop | 100.0% | answered | INC-002, PPT-001 | 71.4% |
| S10 | single_hop | 33.3% | answered | MAN-003 | 50.0% |
| S11 | single_hop | 50.0% | answered | MAN-003 | 87.5% |
| S12 | single_hop | 0.0% | false_refusal | INS-004, Maintenance | 33.3% |
| S13 | single_hop | 100.0% | answered | INC-001, PPT-001 | 100.0% |
| S14 | single_hop | 50.0% | answered | INS-002 | 57.1% |
| S15 | single_hop | 0.0% | false_refusal | SCN-002 | 33.3% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 33.3% |
| S17 | single_hop | 100.0% | answered | Spare | 33.3% |
| S18 | single_hop | 66.7% | answered | MAN-001, SOP-001 | 57.1% |
| S19 | single_hop | 100.0% | answered | INS-004 | 50.0% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 40.0% |
| M01 | multi_hop | 100.0% | answered | MNT-002, PPT-001 | 77.8% |
| M02 | multi_hop | 100.0% | answered | INC-002, Maintenance | 42.9% |
| M03 | multi_hop | 100.0% | answered | Equipment, MAN-001 | 33.3% |
| M04 | multi_hop | 100.0% | answered | Spare | 33.3% |
| M05 | multi_hop | 100.0% | answered | PPT-001, SCN-003 | 54.5% |
| M06 | multi_hop | 66.7% | answered | INS-003, Maintenance | 90.0% |
| M07 | multi_hop | 100.0% | answered | Equipment, MAN-003 | 77.8% |
| M08 | multi_hop | 50.0% | answered | LOG-001, MNT-002 | 33.3% |
| M09 | multi_hop | 75.0% | answered | Maintenance | 28.6% |
| M10 | multi_hop | 100.0% | answered | MNT-001 | 66.7% |
| F01 | follow_up | 100.0% | answered | INC-002, LOG-002, Spare | 0.0% |
| F02 | follow_up | 0.0% | false_refusal | MAN-003 | 57.1% |
| F03 | follow_up | 100.0% | answered | INS-004 | 77.8% |
| F04 | follow_up | 100.0% | answered | MNT-002, SOP-001 | 55.6% |
| F05 | follow_up | 100.0% | answered | Maintenance, Spare | 0.0% |
| N01 | negative | — | correct_refusal | — | 20.0% |
| N02 | negative | — | correct_refusal | Equipment, LOG-001, MAN-003 | 0.0% |
| N03 | negative | — | correct_refusal | INS-004, Maintenance, Spare | 50.0% |
| N04 | negative | — | correct_refusal | INS-003 | 57.1% |
| N05 | negative | — | correct_refusal | INS-004 | 60.0% |
