# Retrieval — rerank_off

Reranker disabled (RRF order)  
Run 2026-09-13T10:44:30+00:00 · git e647562 (dirty) · collection `document_chunks` · reranker False · graph True

| Slice | n | Doc recall@5 | Doc hit@5 | Passage recall@5 | Evidence in context | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 88.6% | 82.9% | 50.0% | 54.3% | 0.783 |
| single_hop | 20 | 90.0% | 90.0% | 52.5% | 57.5% | 0.704 |
| multi_hop | 10 | 80.0% | 60.0% | 60.0% | 65.0% | 0.833 |
| follow_up | 5 | 100.0% | 100.0% | 20.0% | 20.0% | 1.000 |
| tag: compound | 12 | 87.5% | 83.3% | 44.4% | 48.6% | 0.777 |
| tag: distractor_doc | 3 | 100.0% | 100.0% | 66.7% | 66.7% | 0.583 |
| tag: entity_resolution | 4 | 100.0% | 100.0% | 75.0% | 75.0% | 0.750 |
| tag: long_doc | 9 | 100.0% | 100.0% | 38.9% | 38.9% | 0.870 |
| tag: no_lexical_overlap | 4 | 50.0% | 50.0% | 0.0% | 25.0% | 0.281 |
| tag: ocr_source | 3 | 83.3% | 66.7% | 72.2% | 72.2% | 0.778 |
| tag: table_row | 7 | 100.0% | 100.0% | 71.4% | 71.4% | 0.786 |

- Follow-up resolution: 100.0%
- Top score, negatives: mean 0.1075, max 0.1328; answerable mean 0.1159
- Retrieval latency: p50 132 ms, p95 170 ms

## Per item

| Id | Type | Doc R@5 | Passage R@5 | In context | MRR | Top docs |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| S01 | single_hop | 100.0% | 50.0% | 50.0% | 0.20 | MAN-003, INS-003, Spare, Equipment, SOP-003 |
| S02 | single_hop | 100.0% | 50.0% | 50.0% | 1.00 | MAN-002, LOG-001, LOG-002, INS-002, INC-002 |
| S03 | single_hop | 100.0% | 0.0% | 0.0% | 0.50 | SOP-001, MNT-003, LOG-001, SOP-002, MAN-003 |
| S04 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | INC-001, SOP-002, SCN-002, LOG-002, MAN-003 |
| S05 | single_hop | 0.0% | 0.0% | 0.0% | 0.12 | Equipment, SCN-002, SCN-001, MAN-002, LOG-002 |
| S06 | single_hop | 0.0% | 0.0% | 100.0% | 0.17 | SCN-002, INS-004, Maintenance, INC-001, SOP-001 |
| S07 | single_hop | 100.0% | 100.0% | 100.0% | 0.25 | INC-002, Equipment, Spare, LOG-002, LOG-001 |
| S08 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-001, LOG-001, LOG-002, PPT-002, Maintenance |
| S09 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-002, LOG-002, Equipment, LOG-001, SCN-002 |
| S10 | single_hop | 100.0% | 0.0% | 0.0% | 0.33 | LOG-001, LOG-002, MAN-003, MNT-002, INS-002 |
| S11 | single_hop | 100.0% | 0.0% | 0.0% | 0.50 | MNT-002, MAN-003, PPT-001, INC-001, MAN-001 |
| S12 | single_hop | 100.0% | 0.0% | 0.0% | 1.00 | INS-004, SCN-002, Spare, Maintenance, INS-002 |
| S13 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-001, SCN-002, MAN-003, SOP-001, PPT-001 |
| S14 | single_hop | 100.0% | 0.0% | 0.0% | 1.00 | INS-002, MAN-002, MAN-003, LOG-001, Equipment |
| S15 | single_hop | 100.0% | 0.0% | 0.0% | 1.00 | SCN-002, Equipment, SOP-001, MAN-001, SOP-002 |
| S16 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SCN-003, Equipment, PPT-002, LOG-001, MAN-003 |
| S17 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | MNT-002, Spare, SOP-001, MAN-001, MAN-002 |
| S18 | single_hop | 100.0% | 50.0% | 50.0% | 1.00 | SOP-001, MAN-001, LOG-001, LOG-002, MAN-003 |
| S19 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-004, SCN-002, LOG-002, LOG-001, Spare |
| S20 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, LOG-001, INS-003, SOP-003, LOG-002 |
| M01 | multi_hop | 50.0% | 0.0% | 0.0% | 1.00 | INC-001, MAN-003, Equipment, PPT-001, SOP-001 |
| M02 | multi_hop | 50.0% | 50.0% | 50.0% | 1.00 | INC-002, PPT-001, Equipment, LOG-001, LOG-002 |
| M03 | multi_hop | 100.0% | 100.0% | 100.0% | 0.50 | SCN-002, Equipment, SOP-001, MAN-001, INC-001 |
| M04 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | Spare, MNT-003, Maintenance, LOG-001, Equipment |
| M05 | multi_hop | 100.0% | 50.0% | 50.0% | 1.00 | SCN-003, Maintenance, PPT-001, LOG-002, SOP-001 |
| M06 | multi_hop | 50.0% | 50.0% | 100.0% | 0.50 | LOG-001, Maintenance, INS-004, Equipment, LOG-002 |
| M07 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, SOP-003, Equipment, INS-003, LOG-001 |
| M08 | multi_hop | 100.0% | 33.3% | 33.3% | 1.00 | MNT-002, INC-001, LOG-002, LOG-001, SOP-001 |
| M09 | multi_hop | 100.0% | 50.0% | 50.0% | 1.00 | INS-004, Maintenance, LOG-002, Spare, LOG-001 |
| M10 | multi_hop | 50.0% | 66.7% | 66.7% | 0.33 | Equipment, SCN-002, MNT-001, LOG-002, LOG-001 |
| F01 | follow_up | 100.0% | 0.0% | 0.0% | 1.00 | INC-002, PPT-001, Spare, LOG-002, LOG-001 |
| F02 | follow_up | 100.0% | 0.0% | 0.0% | 1.00 | MAN-003, MAN-001, SOP-002, SOP-003, LOG-002 |
| F03 | follow_up | 100.0% | 0.0% | 0.0% | 1.00 | INS-004, Spare, Maintenance, Equipment, SCN-002 |
| F04 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | MNT-002, Spare, SOP-001, MAN-001, PPT-001 |
| F05 | follow_up | 100.0% | 0.0% | 0.0% | 1.00 | MAN-002, Maintenance, Equipment, LOG-001, PPT-002 |
| N01 | negative | — | — | — | — | INC-002, LOG-001, MNT-003, Spare, SCN-003 |
| N02 | negative | — | — | — | — | MAN-003, INC-001, PPT-001, INS-003, SCN-002 |
| N03 | negative | — | — | — | — | INS-004, LOG-002, Spare, Maintenance, SCN-002 |
| N04 | negative | — | — | — | — | INS-004, MAN-003, LOG-001, Equipment, INS-003 |
| N05 | negative | — | — | — | — | INS-004, Spare, Equipment, MAN-002, INS-003 |
