# HAO_PHONE_002 – phone02 QC

- Input: E:\HAO_Recordings\phone02.mp4; original file remains outside Git.
- Mode: video_only, research/wellness estimation, no independent reference.
- User-reported recording date/time: 2026-10-14 23:11 UTC+07, minute precision; start/end role unspecified. Not a hardware-clock or synchronization measurement.
- Participant/camera information carried from ongoing self-collection: SUBJ_001, OPPO A16, front camera; not inferred from face recognition/file metadata.
- Initial probe: 1798 reported/decoded frames, nominal decoder FPS 29.602815, duration by index/FPS 60.737467 s.
- Face probe at 5/20/40 s: rotation 270 detected face at all three times; raw orientation did not. Probe used half-size images and existing Haar cascade, not medical validation.
- Read-only timing audit: OpenCV POS_MSEC first=0, last=60703.588889 ms; 0 non-increasing intervals. Delta min=33.677778, median=33.766667, max=48.577778 ms. This is decoder timing, not capture UTC; interval variation means index/FPS is approximate. No certification of CFR/capture frame-drop or camera–reference synchronization.
- Full signal QC completed with exit 0; output hao_phone02_qc_run01. SHA256 4b5932af636d53bfab85ff5fbfcdfa9973e294f2bd0ecd06c63955e5225f19d3. 1798 decoded frames, 7 updates, max computed window 43.610717 s. Final root BAD; frontend READY/POOR, score 34. HR estimation 65.2 bpm BAD, confidence 0.575, SIGNAL_QUALITY_LOW/LOW_CONFIDENCE. HRV/RR null INVALID (COMPUTATION_FAILED). READY does not mean every vital is valid or reference validation succeeded.
- Frame statuses: BUFFERING=267, LOW_QUALITY=1503, ARTIFACT=28. Physical cause of low signal quality is not established by these counters. No thresholds or owner code changed in this test.
- Updated current metadata: ../CollectionPackage_V1/SESSION_METADATA_HAO_PHONE_002.json/.csv; run-produced metadata is preserved as original provenance. Full signed-policy confirmation remains incomplete; test processing authorized by video submission.
- Reference HR/BP, sensor timestamps, offset/drift, sync_error_ms and PTT remain missing. This sample cannot be accepted into the paired reference dataset merely because it has video.
