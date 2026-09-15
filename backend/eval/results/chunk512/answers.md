# Answers — chunk512

Run 2026-09-15T17:58:55+00:00 · model `openai/gpt-oss-120b` · LLM cache hits 39, calls 0

**PARTIAL (cache-only): 1 items skipped, never answered:** N05

| Slice | n | Fact coverage | Fully correct | False refusal | Citation P | Citation R | Grounded share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 79.3% | 74.3% | 8.6% | 89.8% | 87.1% | 60.6% |
| single_hop | 20 | 80.0% | 75.0% | 15.0% | 90.0% | 95.0% | 59.9% |
| multi_hop | 10 | 77.5% | 70.0% | 0.0% | 100.0% | 65.0% | 71.5% |
| follow_up | 5 | 80.0% | 80.0% | 0.0% | 75.0% | 100.0% | 46.0% |

- Correct refusal on negatives: 75.0%
- Grounding sentences: 146 grounded, 9 hedged, 94 unsupported
- LLM latency (uncached calls): p50 — ms, p95 — ms

## Per item

| Id | Type | Facts | Refusal | Cited | Grounded |
| --- | --- | ---: | --- | --- | ---: |
| S01 | single_hop | 100.0% | answered | SOP-003 | 66.7% |
| S02 | single_hop | 100.0% | answered | MAN-002 | 62.5% |
| S03 | single_hop | 100.0% | answered | MNT-003 | 60.0% |
| S04 | single_hop | 100.0% | answered | SOP-002 | 85.7% |
| S05 | single_hop | 0.0% | false_refusal | Equipment, PPT-001, SCN-002 | 30.0% |
| S06 | single_hop | 100.0% | answered | MNT-001 | 33.3% |
| S07 | single_hop | 100.0% | answered | LOG-002 | 60.0% |
| S08 | single_hop | 100.0% | answered | INS-001 | 60.0% |
| S09 | single_hop | 100.0% | answered | INC-002, LOG-002 | 80.0% |
| S10 | single_hop | 100.0% | answered | MAN-003 | 66.7% |
| S11 | single_hop | 50.0% | answered | MAN-003 | 77.8% |
| S12 | single_hop | 0.0% | false_refusal | INS-004 | 40.0% |
| S13 | single_hop | 100.0% | answered | INC-001, PPT-001 | 57.1% |
| S14 | single_hop | 100.0% | answered | INS-002 | 66.7% |
| S15 | single_hop | 0.0% | false_refusal | SCN-002 | 66.7% |
| S16 | single_hop | 100.0% | answered | SCN-003 | 60.0% |
| S17 | single_hop | 50.0% | answered | Spare | 20.0% |
| S18 | single_hop | 100.0% | answered | SOP-001 | 87.5% |
| S19 | single_hop | 100.0% | answered | INS-004 | 66.7% |
| S20 | single_hop | 100.0% | answered | MAN-003 | 50.0% |
| M01 | multi_hop | 100.0% | answered | INC-001, MNT-002 | 33.3% |
| M02 | multi_hop | 100.0% | answered | INC-002, Maintenance | 62.5% |
| M03 | multi_hop | 100.0% | answered | Equipment, MAN-001 | 33.3% |
| M04 | multi_hop | 100.0% | answered | Spare | 100.0% |
| M05 | multi_hop | 0.0% | answered | — | — |
| M06 | multi_hop | 100.0% | answered | INS-003, Maintenance | 88.9% |
| M07 | multi_hop | 100.0% | answered | Equipment, MAN-003 | 66.7% |
| M08 | multi_hop | 100.0% | answered | — | 100.0% |
| M09 | multi_hop | 75.0% | answered | INS-004, Maintenance | 87.5% |
| M10 | multi_hop | 0.0% | answered | — | — |
| F01 | follow_up | 100.0% | answered | INC-002, LOG-002, Maintenance, Spare | 25.0% |
| F02 | follow_up | 100.0% | answered | MAN-003 | 50.0% |
| F03 | follow_up | 100.0% | answered | INS-004 | 50.0% |
| F04 | follow_up | 100.0% | answered | MNT-002 | 71.4% |
| F05 | follow_up | 0.0% | answered | MAN-002, Maintenance | 33.3% |
| N01 | negative | — | correct_refusal | — | 20.0% |
| N02 | negative | — | correct_refusal | — | 40.0% |
| N03 | negative | — | correct_refusal | INS-004, LOG-002, Spare | 0.0% |
| N04 | negative | — | missed_refusal | INS-003 | 85.7% |
