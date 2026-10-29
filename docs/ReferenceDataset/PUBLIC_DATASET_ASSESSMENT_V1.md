# Public reference datasets – applicability review

Reviewed 2026-10-14 for AIVitals estimation/wellness/research support. Public benchmark data must not be relabeled as reference for Hào's four phone recordings. Source descriptions are not sample-level sync measurements.

| Dataset | Verified official evidence | Fit / access finding | Decision |
|---|---|---|---|
| UBFC-rPPG | Authors describe 30 FPS, 640x480 face video and CMS50E PPG waveform/HR; official Drive contains dataset folders and Agreement.xlsx | Strong first choice for POS/HR; author source has research/citation terms. readme download currently returned quota-exceeded; no usable paired record acquired | Suitable when lawful paired files/terms/timing obtained; not evaluated in this session |
| PURE | Official TU Ilmenau dataset link is provided by rPPG-Toolbox, whose README describes requesting raw data from authors | Useful motion benchmark; official page could not be reliably retrieved here (timeout/TLS), no authorized raw files or license confirmed | Conditional, no access request sent and no unverified mirror used |
| COHFACE | Idiap describes 160 one-minute videos, 40 subjects, 640x480 at 20 Hz with BVP/breathing reference; official data link points to Zenodo 4081054 | Useful HR/respiration benchmark; 20 Hz is below current local collection target. Zenodo returned 429/403 during checks; raw files not obtained | Separate external benchmark when access/license confirmed; not a substitute for local 30 FPS protocol |
| MPU-rPPG | Paper describes CMS60D reference at 60 Hz and author-reported ±8 ms alignment. Official Figshare sample is CC BY 4.0; public CSV/video files accessible | Downloaded bounded public subset and verified sizes/MD5. CSV has Count/PPG/HR/SPO2, no timestamp column; candidate pair has 34496 rows/frames at 60 FPS | Run exploratory index-aligned POS baseline; no sample-specific sync certificate or strict PASS yet |

## Primary sources and attribution

- UBFC: [author dataset page](https://sites.google.com/view/ybenezeth/ubfcrppg); cite Bobbia et al., “Unsupervised skin tissue segmentation for remote photoplethysmography,” Pattern Recognition Letters, 2017. Do not confuse UBFC-rPPG with UBFC-Phys.
- PURE: [official TU Ilmenau page](https://www.tu-ilmenau.de/universitaet/fakultaeten/fakultaet-informatik-und-automatisierung/profil/institute-und-fachgebiete/institut-fuer-technische-informatik-und-ingenieurinformatik/fachgebiet-neuroinformatik-und-kognitive-robotik/data-sets-code/pulse-rate-detection-dataset-pure); [toolbox acquisition instructions](https://github.com/ubicomplab/rPPG-Toolbox). Request guidance is not permission to send an application or sign terms on behalf of Hào.
- COHFACE: [Idiap dataset page](https://www.idiap.ch/en/dataset/cohface); [Zenodo](https://zenodo.org/records/4081054). Cite Heusch, Anjos, Marcel, “A reproducible study on remote heart rate measurement.” No respiration reference acquired in this session.
- MPU: [original paper](https://www.nature.com/articles/s41597-026-07310-3), [PMC full-text record](https://pmc.ncbi.nlm.nih.gov/articles/PMC13500808/), [Figshare DOI](https://doi.org/10.6084/m9.figshare.29377835), [public API/file metadata](https://api.figshare.com/v2/articles/29377835). Attribute the public sample to William Chen as credited in that record; preserve article title/DOI and CC BY 4.0 notice. Full dataset requires research-use application; none sent. Associated GitHub currently contains README/license/plan, not the claimed full preprocessing implementation.

## Acquired MPU sample and limits

- Cache: external_cache/mpu_public_sample (ignored by Git); scripts/data_qc/fetch_mpu_sample.py downloaded ~110 MB, no full-dataset request, credentials, signature, or bulk >1 TB download.
- Candidate video file ID 55553429 and reference ID 55553426: identical 34496 frames/rows, 60 FPS/60 Hz per paper. Other inspected CSV lengths differ. Matching length plus adjacent IDs supports candidate pairing but does not replace an explicit released per-file manifest.
- No individual CSV timestamp, offset/drift or marker log was provided. Do not fill sync_error_ms with the paper's ±8 ms as though independently measured here. Do not infer capture UTC or public subject demographics from images.
- Comparison predeclares first 60 s, two 30 s windows; analysis decimates 60→30 Hz without shifting reference times. Reference HR averaging uses the engine's actual HR support interval, not the full video mean. Status/gates are retained; BAD estimates are labeled, INVALID values stay null.
- Any reported errors are exploratory under index alignment, not clinical accuracy, not population generalization, and not a strict Reference Dataset V0 acceptance. Benchmark output: mpu_public_benchmark_run01 when complete.
- Benchmark has completed with exit 0: two windows, reference device HR mean 71.0 in each HR support interval; both engine estimates INVALID/null (SQI 0.10/0.00). No MAE/RMSE/bias computable. Actual results and limits: WEEK3_PUBLIC_REFERENCE_BENCHMARK_V1.md. Do not convert that failure into a PASS or attach external labels to phone videos.

## Week 3/4 implication

External data can supply a separate reference benchmark, not missing measurements on phone01–04. Four video-only sessions meet the pilot count, but original Week 4 paired collection DoD and strict Week 3 sync/acceptance evidence remain distinct. Dataset access failures/uncertainty must be reported, not bypassed or replaced by synthetic labels.
