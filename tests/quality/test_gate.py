from aivitals_engine.quality.gate import QualityGate, QualityState, RejectReason

def test_quality_gate_clean():
    gate = QualityGate(hysteresis_sec=2.0)
    metrics = {
        'window_len': 240, 'min_window_len': 90,
        'artifact_ratio': 0.0, 'snr': 0.8, 'periodicity': 0.8,
        'r_mean': 0.9, 'motion_score': 0.1
    }
    state, reasons = gate.evaluate(metrics, timestamp_sec=1.0)
    assert state == QualityState.ACCEPTED
    assert len(reasons) == 0

def test_quality_gate_suspicious():
    gate = QualityGate(hysteresis_sec=2.0)
    metrics = {
        'window_len': 240, 'min_window_len': 90,
        'artifact_ratio': 0.0, 'snr': 0.3, 'periodicity': 0.8, # Only SNR is low
        'r_mean': 0.9, 'motion_score': 0.1
    }
    state, reasons = gate.evaluate(metrics, timestamp_sec=1.0)
    assert state == QualityState.SUSPICIOUS
    assert RejectReason.LOW_SNR in reasons

def test_quality_gate_rejected_and_hysteresis():
    gate = QualityGate(hysteresis_sec=2.0)
    
    # 1. Reject (2 reasons)
    metrics_bad = {
        'window_len': 240, 'min_window_len': 90,
        'artifact_ratio': 0.0, 'snr': 0.2, 'periodicity': 0.3, # 2 bad
        'r_mean': 0.9, 'motion_score': 0.1
    }
    state, reasons = gate.evaluate(metrics_bad, timestamp_sec=1.0)
    assert state == QualityState.REJECTED
    assert len(reasons) == 2
    
    # 2. Good metrics immediately after -> Should still be REJECTED due to hysteresis
    metrics_good = {
        'window_len': 240, 'min_window_len': 90,
        'artifact_ratio': 0.0, 'snr': 0.8, 'periodicity': 0.8,
        'r_mean': 0.9, 'motion_score': 0.1
    }
    state, reasons = gate.evaluate(metrics_good, timestamp_sec=2.0) # Delta = 1.0s < 2.0s
    assert state == QualityState.REJECTED
    # Reasons shouldn't include any current reasons, just state is rejected
    assert len(reasons) == 0
    
    # 3. Good metrics after cooldown -> Should recover to ACCEPTED
    state, reasons = gate.evaluate(metrics_good, timestamp_sec=3.1) # Delta = 2.1s > 2.0s
    assert state == QualityState.ACCEPTED

def test_quality_gate_artifact_ratio():
    gate = QualityGate()
    metrics = {
        'window_len': 240, 'min_window_len': 90,
        'artifact_ratio': 0.3, 'snr': 0.9, 'periodicity': 0.9, # Only Artifact is high
        'r_mean': 0.9, 'motion_score': 0.1
    }
    # High artifact instantly REJECTS, not SUSPICIOUS
    state, reasons = gate.evaluate(metrics, timestamp_sec=1.0)
    assert state == QualityState.REJECTED
    assert RejectReason.HIGH_ARTIFACT in reasons
