from enum import Enum
from typing import Dict, List, Tuple
import time

class QualityState(str, Enum):
    ACCEPTED = "ACCEPTED"
    SUSPICIOUS = "SUSPICIOUS"
    REJECTED = "REJECTED"

class RejectReason(str, Enum):
    LOW_SNR = "LOW_SNR"
    NOT_PERIODIC = "NOT_PERIODIC"
    ROI_DISAGREE = "ROI_DISAGREE"
    HIGH_MOTION = "HIGH_MOTION"
    HIGH_ARTIFACT = "HIGH_ARTIFACT"
    WINDOW_TOO_SHORT = "WINDOW_TOO_SHORT"

class QualityGate:
    def __init__(self, hysteresis_sec: float = 2.0):
        self.hysteresis_sec = hysteresis_sec
        self.last_rejected_time = -hysteresis_sec - 1.0
        self.current_state = QualityState.ACCEPTED
        
        # UNCALIBRATED thresholds
        self.th_snr = 0.4
        self.th_periodicity = 0.46
        self.th_roi_agree = 0.4
        self.th_motion = 0.5
        self.th_artifact = 0.25

    def evaluate(self, sqi_metrics: Dict[str, float], timestamp_sec: float) -> Tuple[QualityState, List[RejectReason]]:
        reasons = []
        
        if sqi_metrics.get('window_len', 0) < sqi_metrics.get('min_window_len', 1):
            reasons.append(RejectReason.WINDOW_TOO_SHORT)
        else:
            if sqi_metrics.get('artifact_ratio', 0.0) > self.th_artifact:
                reasons.append(RejectReason.HIGH_ARTIFACT)
            if sqi_metrics.get('snr', 1.0) < self.th_snr:
                reasons.append(RejectReason.LOW_SNR)
            if sqi_metrics.get('periodicity', 1.0) < self.th_periodicity:
                reasons.append(RejectReason.NOT_PERIODIC)
            if sqi_metrics.get('r_mean', 1.0) < self.th_roi_agree:
                reasons.append(RejectReason.ROI_DISAGREE)
            if sqi_metrics.get('motion_score', 0.0) > self.th_motion:
                reasons.append(RejectReason.HIGH_MOTION)
                
        if RejectReason.WINDOW_TOO_SHORT in reasons or RejectReason.HIGH_ARTIFACT in reasons or len(reasons) > 1:
            raw_state = QualityState.REJECTED
        elif len(reasons) == 1:
            raw_state = QualityState.SUSPICIOUS
        else:
            raw_state = QualityState.ACCEPTED
            
        # Hysteresis
        if raw_state == QualityState.REJECTED:
            self.last_rejected_time = timestamp_sec
            self.current_state = QualityState.REJECTED
        else:
            if (timestamp_sec - self.last_rejected_time) < self.hysteresis_sec:
                self.current_state = QualityState.REJECTED
            else:
                self.current_state = raw_state
                
        return self.current_state, reasons
