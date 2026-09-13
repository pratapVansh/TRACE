# Retrieval — chunk512

Same pipeline on a separate Qdrant collection chunked at 512/64 (reranker timeout 60 s)  
Run 2026-09-13T11:34:27+00:00 · git e647562 (dirty) · collection `eval_chunks_512` · reranker True · graph True

| Slice | n | Doc recall@5 | Doc hit@5 | Passage recall@5 | Evidence in context | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 89.0% | 82.9% | 77.1% | 86.2% | 0.853 |
| single_hop | 20 | 90.0% | 90.0% | 77.5% | 82.5% | 0.808 |
| multi_hop | 10 | 81.7% | 60.0% | 65.0% | 86.7% | 0.870 |
| follow_up | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 1.000 |
| tag: compound | 12 | 88.9% | 83.3% | 76.4% | 79.2% | 0.833 |
| tag: distractor_doc | 3 | 100.0% | 100.0% | 100.0% | 100.0% | 0.833 |
| tag: entity_resolution | 4 | 87.5% | 75.0% | 83.3% | 100.0% | 1.000 |
| tag: long_doc | 9 | 100.0% | 100.0% | 77.8% | 77.8% | 1.000 |
| tag: no_lexical_overlap | 4 | 50.0% | 50.0% | 50.0% | 75.0% | 0.417 |
| tag: ocr_source | 3 | 83.3% | 66.7% | 50.0% | 72.2% | 0.733 |
| tag: table_row | 7 | 92.9% | 85.7% | 69.0% | 78.6% | 0.929 |

- Follow-up resolution: 100.0%
- Top score, negatives: mean 0.7208, max 1.0000; answerable mean 0.6709
- Retrieval latency: p50 7542 ms, p95 9443 ms

## Per item

| Id | Type | Doc R@5 | Passage R@5 | In context | MRR | Top docs |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| S01 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | MAN-003, SOP-003, INS-003, Equipment, INS-004 |
| S02 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-002, Equipment, INC-002, INS-002, MAN-003 |
| S03 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | SOP-001, MNT-003, SOP-003, MAN-001, LOG-001 |
| S04 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SOP-002, MAN-003, Equipment, SOP-001, INC-001 |
| S05 | single_hop | 0.0% | 0.0% | 0.0% | 0.00 | PPT-001, Equipment, SCN-002, MAN-002, SCN-001 |
| S06 | single_hop | 0.0% | 0.0% | 100.0% | 0.17 | LOG-002, INS-004, LOG-001, SOP-001, INC-001 |
| S07 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | INC-002, LOG-002, LOG-001, Maintenance, Equipment |
| S08 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-001, LOG-001, LOG-002, Equipment, PPT-002 |
| S09 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-002, LOG-002, LOG-001, PPT-001, SCN-002 |
| S10 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, MAN-001, Equipment, LOG-002, SOP-001 |
| S11 | single_hop | 100.0% | 50.0% | 50.0% | 1.00 | MAN-003, MAN-001, MNT-002, INC-001, SOP-001 |
| S12 | single_hop | 100.0% | 0.0% | 0.0% | 1.00 | INS-004, LOG-002, LOG-001, SCN-002, Spare |
| S13 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-001, Equipment, SCN-002, PPT-001, MAN-003 |
| S14 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-002, MAN-002, MAN-003, LOG-002, LOG-001 |
| S15 | single_hop | 100.0% | 0.0% | 0.0% | 1.00 | SCN-002, SOP-001, Equipment, SOP-002, INC-001 |
| S16 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SCN-003, LOG-001, Equipment, PPT-002, LOG-002 |
| S17 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | MNT-002, Spare, MAN-001, LOG-001, Maintenance |
| S18 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SOP-001, MAN-003, SCN-002, INC-001, MAN-001 |
| S19 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-004, LOG-002, LOG-001, Equipment, SCN-002 |
| S20 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, Equipment, LOG-001, MAN-001, MNT-002 |
| M01 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-001, PPT-001, MAN-003, MNT-002, Equipment |
| M02 | multi_hop | 50.0% | 50.0% | 100.0% | 1.00 | INC-002, LOG-002, LOG-001, PPT-001, Equipment |
| M03 | multi_hop | 50.0% | 33.3% | 100.0% | 1.00 | Equipment, MAN-003, SCN-002, SOP-001, INC-001 |
| M04 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | Spare, MNT-003, MAN-001, LOG-001, Maintenance |
| M05 | multi_hop | 100.0% | 50.0% | 50.0% | 1.00 | PPT-001, SCN-003, Maintenance, LOG-002, SOP-001 |
| M06 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-003, Maintenance, LOG-002, INS-004, SOP-003 |
| M07 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, Equipment, SOP-003, INS-003, LOG-001 |
| M08 | multi_hop | 66.7% | 66.7% | 100.0% | 0.50 | INC-001, MNT-002, SOP-001, MAN-001, Maintenance |
| M09 | multi_hop | 100.0% | 50.0% | 50.0% | 1.00 | INS-004, Maintenance, LOG-002, Spare, LOG-001 |
| M10 | multi_hop | 50.0% | 0.0% | 66.7% | 0.20 | PPT-001, Equipment, SCN-002, INC-001, SCN-001 |
| F01 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | INC-002, LOG-002, PPT-001, Spare, LOG-001 |
| F02 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, MAN-001, LOG-001, LOG-002, Maintenance |
| F03 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | INS-004, Spare, Maintenance, LOG-002, LOG-001 |
| F04 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | MNT-002, INC-001, MAN-001, Maintenance, SOP-001 |
| F05 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | MAN-002, INS-002, Maintenance, LOG-001, LOG-002 |
| N01 | negative | — | — | — | — | INC-002, Spare, MNT-003, MAN-003, PPT-001 |
| N02 | negative | — | — | — | — | MAN-003, Equipment, INC-001, LOG-001, MAN-001 |
| N03 | negative | — | — | — | — | INS-004, Spare, LOG-002, Maintenance, LOG-001 |
| N04 | negative | — | — | — | — | INS-003, SOP-003, MAN-003, LOG-002, INS-004 |
| N05 | negative | — | — | — | — | INS-004, SCN-002, Spare, Equipment, MAN-002 |
