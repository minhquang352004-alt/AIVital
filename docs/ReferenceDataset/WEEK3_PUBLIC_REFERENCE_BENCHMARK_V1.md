# Week 3 – public reference candidate baseline

Completed actions: official-source assessment, bounded lawful public MPU sample acquisition, basic reference integrity checks, actual POS test and schema validation. Strict Reference Dataset V0 acceptance is NOT complete; sample-specific pairing/timing lacks released verification and both estimates were rejected.

## Dataset and provenance

- Source: [MPU-rPPG Figshare record](https://doi.org/10.6084/m9.figshare.29377835), CC BY 4.0, record credits William Chen. Associated article: [Scientific Data](https://www.nature.com/articles/s41597-026-07310-3). Preserve attribution; raw public sample remains in ignored external_cache, not copied to personal-phone sessions or Git.
- Candidate video 55553429_Output.mp4, CSV 55553426_Output.csv: exactly 34496 frames/rows; 60 FPS observed, 60 Hz reference described in paper. Other candidate CSV lengths 44548/47312/54005 do not match that video.
- CSV Count is consecutive 0–34495, HR values finite/positive, whole-file HR range 67–83 bpm. PPG nonconstant in compared intervals. These basic checks do not certify waveform quality or clock sync.
- No timestamp/offset log or per-file pairing manifest was acquired. Index alignment remains an explicit assumption. The article's reported ±8 ms is not an independently measured sample sync_error_ms; that field stays null. No capture UTC inferred.

## Predeclared test and observed results

Offline engine ROI/POS, first 60 s, two disjoint 30 s windows; explicit 60→30 Hz analysis decimation. No gate or algorithm change, no result-based window selection. HR uses the final 10 s of each analysis window, so reference averages use [20,30) and [50,60), not a 60 s mean. Raw model date-times encode relative seconds on a synthetic epoch, not actual capture date.

| Analysis window (s) | HR support (s) | Independent device HR mean (bpm) | Engine estimate | SQI | Status/issues |
|---|---|---:|---|---:|---|
| 0–30 | 20–30 | 71.0 | null | 0.10 | INVALID; SIGNAL_QUALITY_UNUSABLE, LOW_CONFIDENCE |
| 30–60 | 50–60 | 71.0 | null | 0.00 | INVALID; SIGNAL_QUALITY_UNUSABLE, VERY_LOW_CONFIDENCE |

- Attempted windows=2; windows with non-null estimate=0; OK windows=0. MAE/RMSE/bias are unavailable, not zero. Runtime contracts retain null INVALID results; HRV/RR also unavailable.
- This is an actual unsuccessful baseline measurement, not a simulated example and not evidence of clinical accuracy. It is offline/exploratory, not identical to realtime integration gate behavior.
- Evidence: mpu_public_benchmark_run01/benchmark_summary.json, hr_comparison.csv, window_1_raw_result.json, window_2_raw_result.json. Cache provenance lists verified download sizes/MD5.

## Reference acceptance and what remains

Candidate decision: keep for exploratory research with alignment warning; EXCLUDE from strict accepted Reference Dataset V0 until pairing/timebase/sync evidence is resolved. Do not assign this 71 bpm reference to Hào's phone recordings.
Review with Khang/Khoa the ROI/POS/SQI outputs using these fixed windows before any tuning; do not lower thresholds to mark SUCCESS. Obtain an officially mapped/synchronized UBFC/PURE/COHFACE/MPU record under confirmed terms for acceptance testing, or have the group approve a different milestone. No access application/signature/email was sent on Hào's behalf.
