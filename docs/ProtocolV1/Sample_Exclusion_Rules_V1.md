# AIVitals Sample Exclusion Rules V1

## 1. PASS

Sample is PASS when:
- Required metadata is available.
- Video is readable.
- Face is visible.
- Lighting is valid.
- Frame rate is valid.
- Synchronization is within the defined threshold.
- No critical exclusion condition is present.

## 2. WARNING

Sample may be labelled WARNING when:
- Minor deviation exists.
- The sample is still usable for a specific challenge analysis.
- The deviation is documented in metadata.

## 3. REJECT

A sample should be rejected when one or more critical conditions occur.

### 3.1 Video

- Variable frame rate (VFR)
- Frame drop >5%
- Corrupted/unreadable video
- Insufficient recording duration
- Insufficient resolution

### 3.2 Face / ROI

- No detectable face
- Severe face/ROI occlusion
- Main ROI occlusion >50%

### 3.3 Synchronization

- Missing reference data
- Missing timestamps
- Synchronization error >100 ms

### 3.4 Lighting

- Illumination <5 lux
- Illumination >700 lux