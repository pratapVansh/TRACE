# Answers — passage2

Run 2026-09-17T18:24:46+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 0, calls 40

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 87.6% | 80.0% | 8.6% | 85.5% | 85.7% | 57.2% |
| single_hop | 20 | 87.5% | 85.0% | 10.0% | 85.2% | 90.0% | 61.9% |
| multi_hop | 10 | 91.7% | 70.0% | 0.0% | 95.8% | 70.0% | 51.7% |
| follow_up | 5 | 80.0% | 80.0% | 20.0% | 70.0% | 100.0% | 49.5% |

- Correct refusal on negatives: 100.0%
- Empty answers (model produced no text; scored 0.0 coverage): none
- Grounding sentences: 159 grounded, 7 hedged, 120 unsupported
- LLM latency (uncached calls): p50 2686 ms, p95 4227 ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 100.0% | answered | MAN-003, SOP-003 | 40.0% |
| S02 | single_hop | 100.0% | answered | MAN-002 | 57.1% |
| S03 | single_hop | 100.0% | answered | MNT-003 | 71.4% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 66.7% |
| S05 | single_hop | 0.0% | false_refusal | — | 40.0% |
| S06 | single_hop | 100.0% | answered | LOG-001, LOG-002, MNT-001 | 77.8% |
| S07 | single_hop | 100.0% | answered | LOG-002, Maintenance | 66.7% |
| S08 | single_hop | 100.0% | answered | INS-001 | 71.4% |
| S09 | single_hop | 100.0% | answered | INC-002 | 70.0% |
| S10 | single_hop | 100.0% | answered | MAN-001, MAN-003 | 80.0% |
| S11 | single_hop | 50.0% | answered | MAN-003 | 80.0% |
| S12 | single_hop | 0.0% | false_refusal | INS-004 | 50.0% |
| S13 | single_hop | 100.0% | answered | INC-001 | 66.7% |
| S14 | single_hop | 100.0% | answered | INS-002 | 87.5% |
| S15 | single_hop | 100.0% | answered | Maintenance, SCN-002 | 25.0% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 50.0% |
| S17 | single_hop | 100.0% | answered | Spare | 40.0% |
| S18 | single_hop | 100.0% | answered | — | 75.0% |
| S19 | single_hop | 100.0% | answered | INS-004 | 42.9% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 80.0% |
| M01 | multi_hop | 100.0% | answered | INC-001, MNT-002 | 57.1% |
| M02 | multi_hop | 100.0% | answered | INC-002, Maintenance | 57.1% |
| M03 | multi_hop | 100.0% | answered | MAN-001 | 60.0% |
| M04 | multi_hop | 100.0% | answered | Spare | 40.0% |
| M05 | multi_hop | 100.0% | answered | — | 33.3% |
| M06 | multi_hop | 66.7% | answered | INS-003, Maintenance | 55.6% |
| M07 | multi_hop | 100.0% | answered | Equipment, MAN-003, SOP-003 | 42.9% |
| M08 | multi_hop | 75.0% | answered | — | 42.9% |
| M09 | multi_hop | 75.0% | answered | INS-004, Maintenance | 50.0% |
| M10 | multi_hop | 100.0% | answered | MNT-001, SCN-001 | 77.8% |
| F01 | follow_up | 100.0% | answered | INC-002, Spare | 33.3% |
| F02 | follow_up | 0.0% | false_refusal | MAN-003 | 40.0% |
| F03 | follow_up | 100.0% | answered | INS-004 | 85.7% |
| F04 | follow_up | 100.0% | answered | MNT-002, Spare | 28.6% |
| F05 | follow_up | 100.0% | answered | MAN-002, Maintenance | 60.0% |
| N01 | negative | — | correct_refusal | — | 0.0% |
| N02 | negative | — | correct_refusal | — | 0.0% |
| N03 | negative | — | correct_refusal | INS-004, LOG-002, Spare | 14.3% |
| N04 | negative | — | correct_refusal | INS-003, LOG-001 | 66.7% |
| N05 | negative | — | correct_refusal | INS-004, SCN-002, Spare | 42.9% |
