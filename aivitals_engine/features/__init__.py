"""
aivitals_engine/features
========================
BVP Feature Extraction Pipeline — Tuần 5.

Trích xuất đặc trưng sinh lý từ sóng BVP đã lọc sạch phục vụ
mô hình Huyết áp / Đánh giá sức khỏe tim mạch (BP / Health Model).

Public API:
    >>> from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures
    >>> extractor = BVPFeatureExtractor()
    >>> features = extractor.extract(bvp, fs=30.0)
"""
from aivitals_engine.features.config import BVPFeaturesConfig
from aivitals_engine.features.extractor import BVPFeatureExtractor
from aivitals_engine.features.schema import BVPFeatures
from aivitals_engine.features.segmentation import BeatSegmenter, SingleBeat

__all__ = [
    "BVPFeatures",
    "BVPFeatureExtractor",
    "BVPFeaturesConfig",
    "BeatSegmenter",
    "SingleBeat",
]
