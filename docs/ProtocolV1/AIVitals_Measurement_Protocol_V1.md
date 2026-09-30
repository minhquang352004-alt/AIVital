# AIVitals Measurement Protocol V1

## 1. Purpose

## 2. Camera Setup
### 2.1 Resolution

The camera should record at a minimum resolution of 320 × 240 pixels.

Preferred recording resolution:
- 1280 × 720 (720p)
- 1920 × 1080 (1080p)

The same camera configuration should be maintained within the same
data collection session whenever possible.

### 2.2 Camera Position

The camera should be:
- Fixed and stable.
- Positioned approximately at eye level.
- Facing the participant directly.
- Not handheld during recording.

### 2.3 Camera Configuration

Where supported:
- Auto-exposure should be locked.
- White balance should be locked.

The camera configuration should remain unchanged during a recording session.
## 3. Frame Rate
### HR/RR

Minimum FPS: 30 FPS.

### BP/PTT

Target FPS: 60 FPS.

### Recording requirement

The video should use a constant frame rate (CFR).

The following metadata should be recorded:
- fps_configured
- fps_actual
- frame_count
- duration_sec

Variable frame rate (VFR) recordings should be rejected.
## 4. Participant Pose
### Standard resting pose

The participant should:

- Sit in a stable seated position.
- Face the camera.
- Keep the eyes approximately directed toward the camera.
- Maintain a neutral facial expression.
- Minimize unnecessary head movement.
- Avoid talking during the resting recording.
- Avoid chewing or other facial movements.

The upper face and main facial ROI should remain clearly visible.
## 5. Camera Distance
Camera distance should be recorded for every recording session using:

camera_distance_cm

Candidate distances for pilot testing:

- 40 cm
- 50 cm
- 60 cm
- 70 cm
- 80 cm

The final recommended distance will be selected based on:
- Face visibility
- Facial ROI coverage
- Image quality
- Stability of face detection
- Practicality of the recording setup
## 6. Lighting Conditions
### 6.1 Standard Condition

Target illumination:

≥ 500 lux

The participant's face should be evenly illuminated.

Avoid:
- Strong backlight
- Strong facial shadows
- Flickering light
- Uneven illumination

Where supported:
- Lock camera exposure.
- Lock white balance.

### 6.2 Low-Light Challenge Condition

Low-light recordings should be treated as a separate challenge condition.

Week 1 defines low-light scenarios around:
- 8 lux
- 42.4 lux

These recordings should be explicitly labelled as low-light.

### 6.3 Invalid Lighting

Recordings should be rejected when illumination is:

< 5 lux

or

> 700 lux
## 7. Recording Procedure
### Step 1 — Prepare the participant

- Seat the participant.
- Position the participant facing the camera.
- Confirm that the face is clearly visible.

### Step 2 — Prepare the camera

- Fix the camera.
- Confirm resolution.
- Confirm FPS.
- Confirm stable lighting.
- Lock exposure and white balance where possible.

### Step 3 — Prepare reference device

If ground-truth recording is available:
- Start the reference device.
- Confirm timestamp recording.
- Ensure the reference device is functioning correctly.

### Step 4 — Synchronization

Synchronize the start of video recording and reference-device recording.

Record:
- gt_start_timestamp
- gt_end_timestamp
- synchronization error

### Step 5 — Record

Record the required scenario.

### Step 6 — Save metadata

Immediately record the metadata associated with the video.

### Step 7 — Quality check

Check:
- Video duration
- FPS
- Frame drops
- Face visibility
- Occlusion
- Lighting
- Synchronization

Label the sample:
- PASS
- WARNING
- REJECT
## 8. Recording Scenarios
### 8.1 Resting

Duration: 60 seconds

Participant:
- seated
- facing camera
- neutral expression
- minimal movement
- no talking
- no chewing

### 8.2 Motion

Include:
- head nodding
- head turning approximately ±30°
- facial expressions
- talking
- chewing

### 8.3 Low Light

Use the low-light conditions defined in the Week 1 plan.

Target examples:
- approximately 8 lux
- approximately 42.4 lux

### 8.4 Elevated Heart Rate

Participant performs light exercise before recording
to obtain an elevated HR condition.

Target range defined in Week 1:
90–140 BPM.
## 9. Required Metadata

## 10. Sample Quality

## 11. Exclusion Criteria

## 12. Data Naming Convention

## 13. Version History