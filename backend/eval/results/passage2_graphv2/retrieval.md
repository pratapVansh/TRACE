# Retrieval — passage2_graphv2

Diagnostic: two passages per document with the reworked graph arm  
Run 2026-09-16T18:57:23+00:00 · git fbf3439 (dirty) · collection `document_chunks` · reranker True · graph True

| Slice | n | Doc recall@5 | Doc hit@5 | Passage recall@5 | Evidence in context | MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All answerable | 35 | 98.6% | 97.1% | 75.2% | 85.2% | 0.920 |
| single_hop | 20 | 100.0% | 100.0% | 77.5% | 87.5% | 0.910 |
| multi_hop | 10 | 95.0% | 90.0% | 68.3% | 83.3% | 0.950 |
| follow_up | 5 | 100.0% | 100.0% | 80.0% | 80.0% | 0.900 |
| tag: compound | 12 | 100.0% | 100.0% | 65.3% | 76.4% | 0.933 |
| tag: distractor_doc | 3 | 100.0% | 100.0% | 100.0% | 100.0% | 0.833 |
| tag: entity_resolution | 4 | 87.5% | 75.0% | 83.3% | 100.0% | 1.000 |
| tag: long_doc | 9 | 100.0% | 100.0% | 66.7% | 66.7% | 0.944 |
| tag: no_lexical_overlap | 4 | 100.0% | 100.0% | 75.0% | 75.0% | 0.800 |
| tag: ocr_source | 3 | 100.0% | 100.0% | 72.2% | 72.2% | 1.000 |
| tag: table_row | 7 | 92.9% | 85.7% | 69.0% | 78.6% | 0.929 |

- Follow-up resolution: 100.0%
- Top score, negatives: mean 0.6167, max 1.0000; answerable mean 0.5790
- Retrieval latency: p50 6067 ms, p95 6645 ms

## Per item

| Id | Type | Doc R@5 | Passage R@5 | In context | MRR | Top docs |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| S01 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SOP-003, MAN-003, INS-003, INS-004, Equipment |
| S02 | single_hop | 100.0% | 50.0% | 100.0% | 1.00 | MAN-002, MAN-003, INS-004, INC-002, INS-002 |
| S03 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MNT-003, MAN-003, LOG-001, MAN-001, INS-004 |
| S04 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SOP-002, MAN-003, MNT-003, SOP-001, SCN-002 |
| S05 | single_hop | 100.0% | 0.0% | 0.0% | 0.20 | SCN-002, MAN-003, MAN-002, SCN-001, PPT-002 |
| S06 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MNT-001, MAN-003, INS-004, LOG-001, LOG-002 |
| S07 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | INC-002, LOG-002, Spare, LOG-001, Equipment |
| S08 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-001, LOG-001, Maintenance, LOG-002, PPT-002 |
| S09 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-002, LOG-002, Equipment, LOG-001, Spare |
| S10 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, SOP-001, LOG-001, INS-002, LOG-002 |
| S11 | single_hop | 100.0% | 50.0% | 50.0% | 1.00 | MAN-003, INC-001, MNT-002, PPT-001, MAN-001 |
| S12 | single_hop | 100.0% | 0.0% | 0.0% | 1.00 | INS-004, LOG-002, Maintenance, LOG-001, Spare |
| S13 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-001, Equipment, PPT-001, MAN-003, SOP-001 |
| S14 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-002, MAN-003, MNT-002, LOG-002, INC-001 |
| S15 | single_hop | 100.0% | 0.0% | 100.0% | 1.00 | SCN-002, SOP-001, MAN-003, SOP-002, Equipment |
| S16 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | SCN-003, Equipment, LOG-001, MAN-003, PPT-002 |
| S17 | single_hop | 100.0% | 100.0% | 100.0% | 0.50 | MNT-002, Spare, LOG-001, MAN-001, Maintenance |
| S18 | single_hop | 100.0% | 50.0% | 100.0% | 1.00 | SOP-001, MAN-003, INC-001, MAN-001, LOG-001 |
| S19 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-004, LOG-002, LOG-001, Spare, Equipment |
| S20 | single_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, LOG-001, MAN-002, MNT-002, MAN-001 |
| M01 | multi_hop | 100.0% | 50.0% | 100.0% | 0.50 | PPT-001, INC-001, MNT-002, MNT-003, Maintenance |
| M02 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | INC-002, LOG-002, Spare, Maintenance, LOG-001 |
| M03 | multi_hop | 50.0% | 33.3% | 100.0% | 1.00 | Equipment, MAN-003, LOG-001, SCN-002, MAN-002 |
| M04 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | Spare, MNT-003, Maintenance, LOG-001, MAN-001 |
| M05 | multi_hop | 100.0% | 50.0% | 50.0% | 1.00 | SCN-003, PPT-001, MAN-003, INS-001, LOG-002 |
| M06 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | INS-003, Maintenance, LOG-002, SOP-003, INS-004 |
| M07 | multi_hop | 100.0% | 100.0% | 100.0% | 1.00 | MAN-003, Equipment, SOP-003, INS-003, LOG-001 |
| M08 | multi_hop | 100.0% | 33.3% | 66.7% | 1.00 | MNT-002, INC-001, LOG-001, PPT-001, SOP-001 |
| M09 | multi_hop | 100.0% | 50.0% | 50.0% | 1.00 | INS-004, Maintenance, Spare, LOG-002, LOG-001 |
| M10 | multi_hop | 100.0% | 66.7% | 66.7% | 1.00 | SCN-001, MNT-001, LOG-001, Equipment, LOG-002 |
| F01 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | INC-002, LOG-002, Spare, PPT-001, LOG-001 |
| F02 | follow_up | 100.0% | 0.0% | 0.0% | 0.50 | LOG-001, MAN-003, LOG-002, MAN-001, SOP-003 |
| F03 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | INS-004, Spare, Maintenance, LOG-002, LOG-001 |
| F04 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | MNT-002, INC-001, SOP-001, Maintenance, PPT-001 |
| F05 | follow_up | 100.0% | 100.0% | 100.0% | 1.00 | MAN-002, MAN-003, Maintenance, PPT-002, Spare |
| N01 | negative | — | — | — | — | INC-002, PPT-001, LOG-001, Spare, MNT-003 |
| N02 | negative | — | — | — | — | MAN-003, MNT-003, INC-001, PPT-001, Equipment |
| N03 | negative | — | — | — | — | INS-004, Maintenance, Spare, LOG-002, LOG-001 |
| N04 | negative | — | — | — | — | INS-003, SOP-003, Maintenance, LOG-002, Equipment |
| N05 | negative | — | — | — | — | INS-004, Spare, SCN-002, Equipment, LOG-002 |
