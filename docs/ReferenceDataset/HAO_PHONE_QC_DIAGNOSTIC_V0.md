# Phone video QC diagnostic V0

- Date: 2026-10-14; session: hao-phone-01; engine baseline main@5d9b4ae.
- Mode: video-only, no independent reference; estimation/wellness/research support only.
- Input inspected locally: phone01.mp4; no frames or biometric waveform stored here.
- OpenCV: 848x480, 29.6091 FPS, 1906 reported/decoded frames, index/FPS duration 64.372 s, final decoded PTS 64.338 s. This does not certify CFR or reference synchronization.

## Observed user output

- At t=48.5–52.6 s, usable windows 15.3–19.4 s, SQI 0.20–0.30.
- HR mostly INVALID; one BAD estimate 81.1 bpm at t=51.5 s. Final frontend payload REJECTED with null vitals.
- HRV/RR COMPUTATION_FAILED and WINDOW_TOO_SHORT; minimum configured window 30 s.

## Read-only diagnostic executed

Python -B in E:\AIVitals_HAO_venv replayed decoded frames through the engine's existing face/ROI extraction and short-buffer acceptance, then the existing 60-second SlidingWindowBuffer matching integration defaults. No engine source, gates or configuration modified. The diagnostic did not rerun BVP/SQI computation or the complete service.

- Short-buffer accepted: 1796 frames; artifact-rejected: 110; FACE_LOST: 0 returned statuses (does not guarantee true face detection because detector has fallback).
- Long-buffer reset times (index/FPS seconds): 5.505, 7.599, 9.760, 13.340, 30.869, 33.132.
- Additional long-buffer artifact rejections: 0; maximum/final long-buffer span: 31.207 s.
- Reset rule: gap from last accepted timestamp >0.5 s clears buffer. Repeated RGB artifact rejections can cause this even when every video frame decodes.
- At last user-reported update: 52.6 - 33.132 = about 19.47 s, matching its 19.4 s window. Longer recording alone does not prevent resets.
- Updates may stop before EOF because integration computes only when current frame/buffers/gate permit. A final buffer span >30 s does not prove an eligible HRV/RR computation occurred.
- Final frontend result reflects latest computed result, not best historical HR. BAD estimation is not validated reference.

## Conclusions and next checks

Short windows are explained by observed acceptance-gap resets in this replay, not by a 19-second video. Low SQI is independently established by user logs; its physical cause remains undetermined. RGB changes may involve motion, lighting/exposure or ROI instability; the diagnostic does not distinguish them.

Use a stationary camera, stable frontal light, stable face/ROI, no beauty effects, and fixed exposure/white balance if available for the next controlled run. Keep the rejected sample as QC evidence; do not lower thresholds to force acceptance. If the controlled run still resets, provide this report to Khang/Khoa for owner-side review of ROI/artifact handling. Reference HR/sync remain missing; Week 3 validation and Week 4 reference DoD are incomplete.

## Authorized orientation fix and verification

- User subsequently authorized an engine-side fix and tests. Seven sampled times (2, 10, 20, 30, 40, 50, 60 s) yielded no face at decoded orientation and a detected face after 270° clockwise rotation. Half-size detector probe used the same cascade; this is evidence of wrong input orientation, not reference validation.
- Runner now accepts --rotate 0/90/180/270, default 0; frame rotation precedes ROI extraction and leaves timestamps unchanged. No source video rewrite, algorithm, schema, gate or threshold changes.
- Tests passed: 5 runner rotation/CLI-path tests, 5 existing sliding-buffer tests, 8 existing sub-ROI buffer tests (18 total).
- Full rotated replay ran through run(..., rotation=270), with OpenCV threads limited to 1 for the diagnostic process only. Updates at t=40.6–57.5 s had continuous matching windows; WINDOW_TOO_SHORT disappeared from HRV/RR in those updates. SQI remained low and estimates BAD/INVALID; rotation did not make the recording pass.
- Full replay returned, but the diagnostic wrapper's final print failed with UnicodeEncodeError (Windows cp1252). Final JSON payload was not verified in that replay; the production CLI main already sets stdout UTF-8. Do not classify this wrapper error as an engine validation fix or claim final payload success.
- Next command: use the documented production CLI with --rotate 270, keep quality gates unchanged, and collect independent reference before closing Week 3/4.
- Production CLI --rotate 270 --max-sec 2 smoke check: exit 0, UTF-8 JSON PENDING as expected for a window shorter than minimum. git diff --check passed. Full CLI final payload remains unverified.

## Subsequent successful full automated evidence export

run_video_qc.py completed with exit 0 on the same video (sha256 ca742d3f43776520bdd95d10f65eea29c8f4773e59a980c4dfc9a01a95510aba), rotate 270, existing engine/gates. It captured full raw and frontend outputs in UTF-8, resolving the prior evidence-export limitation. 1906 decoded frames; frame statuses BUFFERING=89, LOW_QUALITY=1728, ARTIFACT=11, OK=78; 16 vital updates; max computed window 57.482 s; final raw INVALID/frontend REJECTED, quality score 23. Updated direction substantially reduced artifact rejections relative to the prior sideways-input replay but did not establish reference accuracy or final signal acceptance. See hao_phone_qc_run02 and HAO_WEEK3_WEEK4_STATUS.md.
