# BVP Feature Contract — Data Specification v1.0
**Project:** AIVitals rPPG System  
**Owner:** Khang (Coding / AI Signal)  
**Consumer:** Khoa (Coding / AI Application – BP & Health Model)  
**Tài liệu tham chiếu:** `AIVitals_rPPG_Project_Development_Detail_Plan_V1.docx` (Tuần 5)

---

## 1. Tổng quan & Ranh giới kiến trúc

* **Vị trí trong pipeline:**
  $$\text{Clean BVP 1D} \longrightarrow \text{Beat Segmentation} \longrightarrow \text{BVPFeatureExtractor} \longrightarrow \text{BVPFeatures} \longrightarrow \text{Khoa's BP/Health Model}$$
* **Ranh giới:**
  * Toàn bộ tính toán trong module `aivitals_engine.features` là **xác định (deterministic)**, chạy thuần CPU bằng NumPy / SciPy, độ trễ trung vị $\le 2.7\text{ ms}$ trên cửa sổ 8s.
  * Không dùng OpenAI để tính toán đặc trưng.
  * Không gán nhãn chẩn đoán bệnh tật trực tiếp (tuân thủ ranh giới y tế).

---

## 2. Hướng dẫn sử dụng nhanh (Quickstart cho Khoa)

### Cách 1: Trích xuất trực tiếp từ mảng BVP (Offline / Batch dataset)
```python
import numpy as np
from aivitals_engine.features import BVPFeatureExtractor, BVPFeatures

extractor = BVPFeatureExtractor()
bvp_signal = ...  # np.ndarray shape (N,) float64 đã lọc sạch
fs = 30.0

# 1. Trích xuất dataclass
features: BVPFeatures = extractor.extract(bvp_signal, fs=fs)

# 2. Lấy vector NumPy phẳng cho Scikit-Learn / PyTorch
X = features.to_numpy()  # shape: (23,), dtype: float64

# 3. Lấy tên các cột để tạo Pandas DataFrame
columns = BVPFeatures.feature_names()
# df = pd.DataFrame([X], columns=columns)

# 4. Lấy dictionary cho API / JSON serialization
data_dict = features.to_dict()
json_str = features.to_json()
```

### Cách 2: Trích xuất từ Realtime Pipeline
```python
from aivitals_engine.signal_pipeline_realtime import RealtimeSignalPipeline

pipeline = RealtimeSignalPipeline()
# Sau khi nạp frame camera và pipeline.is_ready == True:
features = pipeline.extract_features()  # Trả về BVPFeatures hoặc None nếu chưa đủ buffer
if features is not None:
    X_pred = features.to_numpy()
```

---

## 3. Quy cách Vector Đặc trưng (`to_numpy()`)

* **Số chiều cố định:** `BVPFeatures.feature_dim() == 23` phần tử float64.
* **Quy tắc bất biến:** Thứ tự các phần tử trong vector `to_numpy()` khớp 100% với `BVPFeatures.feature_names()`. Thứ tự này được cố định theo schema version `1.0`.
* **Xử lý giá trị `NaN`:**
  * Khi tín hiệu bị nhiễu cục bộ hoặc không tìm thấy khuyết dicrotic / đỉnh thứ cấp rõ ràng, trường tương ứng sẽ mang giá trị `float("nan")`.
  * **Khuyến nghị cho Khoa:** Khi huấn luyện mô hình ML (LightGBM, XGBoost, Random Forest), có thể để mô hình tự xử lý NaN (native NaN support) hoặc sử dụng `SimpleImputer(strategy="median")` trước khi nạp vào mạng nơ-ron / Linear Regression.

---

## 4. Danh mục 23 đặc trưng chi tiết

### 🅰️ Group A: Hình thái học sóng xung (Morphology — 10 features)
| Index | Tên trường | Ý nghĩa sinh lý | Đơn vị | Dải giá trị kỳ vọng |
|:---:|:---|:---|:---:|:---:|
| 0 | `mean_rise_time_ms` | $T_s$: Thời gian co tâm thu trung bình (chân sóng $\to$ đỉnh tâm thu) | ms | 80 – 300 ms |
| 1 | `mean_decay_time_ms` | $T_d$: Thời gian giãn tâm trương trung bình (đỉnh $\to$ chân sóng sau) | ms | 300 – 900 ms |
| 2 | `std_rise_time_ms` | Độ lệch chuẩn của $T_s$ giữa các nhịp | ms | $\ge 0$ |
| 3 | `mean_systolic_ratio` | Tỷ lệ thời gian co tâm thu $T_s / (T_s + T_d)$ | Tỷ lệ | 0.15 – 0.45 |
| 4 | `mean_pw25_ms` | Độ rộng xung tại 25% chiều cao đỉnh | ms | 200 – 700 ms |
| 5 | `mean_pw50_ms` | Độ rộng xung tại 50% chiều cao đỉnh (Pulse Width 50) | ms | 150 – 550 ms |
| 6 | `mean_pw75_ms` | Độ rộng xung tại 75% chiều cao đỉnh | ms | 80 – 350 ms |
| 7 | `mean_area_ratio` | Tỷ lệ diện tích dưới đường cong tâm thu / tâm trương ($A_s / A_d$) | Tỷ lệ | 0.2 – 1.5 |
| 8 | `aix_proxy` | Augmentation Index proxy: $(P_2 - P_1)/P_1$ (phản xạ sóng dội) | Tỷ lệ | -0.8 – 0.5 |
| 9 | `apg_aging_index` | Chỉ số lão hóa mao mạch $(b - c - d - e) / a$ từ đạo hàm bậc 2 | Tỷ lệ | -1.5 – 0.5 |

### 🅱️ Group B: Biên độ xung (Amplitude — 3 features)
| Index | Tên trường | Ý nghĩa sinh lý | Đơn vị | Dải giá trị kỳ vọng |
|:---:|:---|:---|:---:|:---:|
| 10 | `mean_pulse_amplitude` | Chiều cao trung bình đỉnh xung BVP thô | a.u. | $> 0$ |
| 11 | `pulse_amp_cv` | Hệ số biến thiên biên độ ($\sigma / \mu$) đo tính ổn định sóng | Tỷ lệ | 0.0 – 0.6 |
| 12 | `notch_relative_amp` | Độ cao khuyết dicrotic tương đối so với đỉnh tâm thu | Tỷ lệ | 0.1 – 0.8 |

### 🅲 Group C: Tần số & Phổ (Spectral — 5 features)
| Index | Tên trường | Ý nghĩa sinh lý | Đơn vị | Dải giá trị kỳ vọng |
|:---:|:---|:---|:---:|:---:|
| 13 | `fundamental_freq_hz` | $f_0$: Tần số cơ bản nhịp tim trong dải [0.75–2.5 Hz] | Hz | 0.75 – 2.50 Hz |
| 14 | `harmonic_ratio_h2` | Tỷ số công suất hài bậc 2 / hài bậc 1: $P(2f_0) / P(f_0)$ | Tỷ lệ | 0.0 – 1.5 |
| 15 | `harmonic_ratio_h3` | Tỷ số công suất hài bậc 3 / hài bậc 1: $P(3f_0) / P(f_0)$ | Tỷ lệ | 0.0 – 1.0 |
| 16 | `spectral_entropy` | Shannon entropy chuẩn hóa của phổ trong dải tim mạch | [0, 1] | 0.1 – 0.9 |
| 17 | `in_band_power_ratio` | Tỷ lệ năng lượng dải [0.75–2.5 Hz] / tổng năng lượng Nyquist | [0, 1] | 0.4 – 1.0 |

### 🅳 Group D: Xu hướng & Thống kê động (Trend & Dynamics — 5 features)
| Index | Tên trường | Ý nghĩa sinh lý | Đơn vị | Dải giá trị kỳ vọng |
|:---:|:---|:---|:---:|:---:|
| 18 | `baseline_drift_slope` | Độ dốc trôi đường nền BVP (OLS slope) | a.u./s | Gần 0 khi tĩnh |
| 19 | `bvp_skewness` | Độ lệch của phân phối biên độ BVP | Float | -1.5 – 1.5 |
| 20 | `bvp_kurtosis` | Độ nhọn (Excess Kurtosis) phân phối biên độ BVP | Float | -2.0 – 4.0 |
| 21 | `ibi_std_ms` | Độ lệch chuẩn khoảng nhịp tim IBI (proxy SDNN) | ms | 10 – 150 ms |
| 22 | `ibi_mean_ms` | Trung bình khoảng nhịp tim IBI (proxy Mean RR) | ms | 400 – 1333 ms |

### ℹ️ Các trường Metadata (Không nằm trong vector `to_numpy()`)
* `valid_beat_count` (`int`): Số lượng chu kỳ nhịp tim hợp lệ tìm thấy trong cửa sổ.
* `window_duration_s` (`float`): Độ dài cửa sổ BVP (giây).
* `fs` (`float`): Tần số lấy mẫu thực tế (Hz).

---

## 5. Kiểm thử & Độ tin cậy
* Toàn bộ 134 unit và integration tests trong `tests/features/` chạy đạt 100% (`PASSED`).
* Latency trung vị: **$2.69\text{ ms}$** (dưới ngân sách tối đa $3.0\text{ ms}$).
* Script đo kiểm hiệu năng: `python scripts/benchmarks/bench_feature_extractor.py`.
