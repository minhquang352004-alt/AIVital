import os
import sys
import argparse

# Đảm bảo đường dẫn import được aivitals_engine
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import json
import pandas as pd

from aivitals_engine.signal.reader import load_sample
from aivitals_engine.pipeline import SignalRPPGPipeline

def run_rppg_test(input_path: str, output_dir: str = "outputs", method: str = "ALL"):
    """
    Test script chạy pipeline Signal / rPPG trên input sample:
    1. Load sample (video hoặc CSV)
    2. Trích xuất mảng RGB và sampling rate
    3. Chạy thuật toán được chọn (POS / CHROM / GREEN hoặc ALL)
    4. Tạo BVP, tính quality và in metadata
    5. Lưu BVP ra outputs/
    """
    if not os.path.exists(input_path):
        # Thử tìm tương đối từ CURRENT_DIR
        alt_path = os.path.join(CURRENT_DIR, input_path)
        if os.path.exists(alt_path):
            input_path = alt_path
        else:
            print(f"Lỗi: Không tìm thấy file input: {input_path}")
            sys.exit(1)

    # 1. Load sample
    rgb_array, fs = load_sample(input_path)
    num_samples = len(rgb_array)

    # 2. In thông tin đầu vào
    source_name = os.path.basename(input_path)
    print("================================")
    print("AIVitals rPPG Test")
    print("================================")
    print("\nInput:")
    print(f"  source: {source_name}")
    print(f"  sampling_rate: {int(round(fs))} Hz")
    print(f"  samples: {num_samples}")

    # Đảm bảo thư mục output tồn tại
    os.makedirs(output_dir, exist_ok=True)
    pipeline = SignalRPPGPipeline(fps=fs)

    # Xác định danh sách thuật toán cần chạy
    method_upper = method.upper()
    if method_upper == "ALL":
        algorithms = ["POS", "CHROM", "GREEN"]
    elif method_upper in ["POS", "CHROM", "GREEN"]:
        algorithms = [method_upper]
    else:
        print(f"Lỗi: Thuật toán '{method}' không hợp lệ. Chọn 'POS', 'CHROM', 'GREEN' hoặc 'ALL'.")
        sys.exit(1)

    # 3. Chạy thuật toán
    saved_files = []
    summary_records = []
    for algo_name in algorithms:
        res = pipeline.run_on_rgb(rgb_array, fs=fs, algorithm_name=algo_name)

        print(f"\n--------------------------------")
        print(f"Method: {res.method}")
        print(f"--------------------------------")
        print(f"BVP samples: {res.signal_length}")
        print(f"Sampling rate: {res.sampling_rate} Hz")
        print(f"Quality: {res.quality:.2f}")

        # Lưu BVP ra file CSV
        output_file = os.path.join(output_dir, f"{algo_name.lower()}_bvp.csv")
        res.save_csv(output_file)
        saved_files.append(output_file)

        # Ghi nhận record metadata
        meta = res.to_metadata()
        meta["source"] = source_name
        meta["output_file"] = os.path.basename(output_file)
        summary_records.append(meta)

    # 4. Ghi lại sampling rate, method, quality ra file tổng hợp
    summary_csv_path = os.path.join(output_dir, "baseline_summary.csv")
    summary_json_path = os.path.join(output_dir, "baseline_summary.json")

    pd.DataFrame(summary_records).to_csv(summary_csv_path, index=False)
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary_records, f, indent=2, ensure_ascii=False)

    print("\n================================")
    print(f"Đã lưu các file BVP vào thư mục: {output_dir}/")
    for f in saved_files:
        print(f"  - {f}")
    print(f"Đã ghi lại metadata tổng hợp:")
    print(f"  - {summary_csv_path}")
    print(f"  - {summary_json_path}")
    print("================================")

def main():
    parser = argparse.ArgumentParser(description="AIVitals Signal & rPPG Test Runner")
    default_sample = os.path.join(CURRENT_DIR, "samples", "sample_rgb.csv")
    default_output = os.path.join(CURRENT_DIR, "outputs")
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=default_sample,
        help="Đường dẫn đến file video (.mp4/.avi) hoặc RGB sample (.csv)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=default_output,
        help="Thư mục lưu các file BVP kết quả (mặc định: aivitals_engine/outputs/)"
    )
    parser.add_argument(
        "--method", "-m",
        type=str,
        default="ALL",
        choices=["POS", "CHROM", "GREEN", "ALL", "pos", "chrom", "green", "all"],
        help="Chọn thuật toán cần chạy: POS, CHROM, GREEN hoặc ALL (mặc định: ALL)"
    )
    args = parser.parse_args()

    run_rppg_test(args.input, args.output_dir, args.method)

if __name__ == "__main__":
    main()
