# Week 4 – four-session video-only pilot

Status: four recordings received and full-file QC completed; collection package/automation and pilot-count subtask complete. Original paired-reference Week 4 DoD is NOT complete. No hardware reference was collected; this is estimation/wellness/research support only.

| Sample | Duration by decoder (s) | Frames | Updates | Final engine / frontend | Signal finding |
|---|---:|---:|---:|---|---|
| HAO_PHONE_001 | 64.372 | 1906 | 16 | INVALID / REJECTED | Score 23; no final vital values |
| HAO_PHONE_002 | 60.737 | 1798 | 7 | BAD / READY (POOR) | Score 34; HR BAD, HRV/RR unavailable |
| HAO_PHONE_003 | 60.357 | 1785 | 13 | BAD / READY (POOR) | Score 33; HR BAD, HRV/RR unavailable |
| HAO_PHONE_004 | 60.459 | 1783 | 0 | no result / PENDING | Frames decoded but no eligible vital update; score unavailable |

## Evidence and scope

- COLLECTION_MANIFEST_V1.json indexes four distinct video hashes and the current per-session 57-field metadata files. Raw videos remain E:\HAO_Recordings; no video was copied into Git.
- Full QC outputs in ../ReferenceDataset/hao_phone_qc_run02, hao_phone02_qc_run01, hao_phone03_qc_run01 and hao_phone04_qc_run01 include summaries, original run metadata, updates and raw result where available. The raw file for phone04 contains JSON null, not a valid VitalsResult.
- All recordings required rotation 270 for the observed decoded orientation. Original gates/algorithms retained; no success flag forced.
- Participant/camera context: SUBJ_001, OPPO A16 front camera, user-confirmed internal research/team access; user deletes data. Full signed policy/contact/retention acceptance not established; 90-day retention remains proposed.
- Time declarations: phone01 22:28 and phone02 23:11 on 2026-10-14 UTC+07, minute precision and start/end role unclear. phone03/04 capture date/time not supplied; run timestamps are not capture time.
- Demographics/lux remain unknown. Mean decoder FPS ~29.5–29.6 is not proof of CFR or meeting the current >=30 FPS collection target. No sensor timestamps, offset/drift, sync_error, reference HR/BP or PTT supplied.
- Four sessions of one person do not support subject-generalization claims or a subject-independent train/test split. Public dataset subjects stay separate from SUBJ_001.

## Completion checklist

- [x] Consent/privacy template, sync protocol, JSON/CSV templates and DB mapping prepared.
- [x] Metadata initialization and automated QC scripts validated.
- [x] Four distinct recordings ingested and QC evidence saved; failures retained transparently.
- [x] Current metadata and dataset exclusion decisions populated with actual known facts.
- [ ] Complete consent policy/record requirements and precise capture metadata.
- [ ] Independent reference recorded during these four sessions.
- [ ] Reference/video sync established under agreed gate.
- [ ] Original Week 4 paired collection DoD complete.

To close the original milestone, the group must provide paired reference collection or explicitly approve a revised milestone (video-only pilot + separately sourced public benchmark). This report does not approve that change on behalf of the group. More identical no-reference videos do not resolve the remaining gap.
