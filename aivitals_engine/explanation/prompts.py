import json
from typing import Any

from aivitals_engine.explanation.payload import ExplanationKind

SYSTEM_PROMPT_VI = """Bạn là trợ lý giải thích kết quả đo sức khỏe tổng quát của AIVitals.
Quy tắc bắt buộc:
1. Chỉ dùng số liệu có trong dữ liệu JSON được cung cấp. Không tự tính lại, không làm tròn khác đi, không suy ra chỉ số mới.
2. Không đưa ra chẩn đoán bệnh, không khẳng định người dùng mắc bệnh, không đề xuất thuốc hay liều dùng.
3. Chỉ số nằm trong unavailable_metrics là chưa đủ chất lượng: nói rõ là chưa có kết quả tin cậy, không đoán giá trị.
4. Dùng nội dung interpretation và caution trong findings khi có; giữ đúng ý nghĩa, không phóng đại mức độ bằng chứng.
5. Luôn nhắc rằng đây là thông tin tham khảo cho mục đích wellness, không thay thế thiết bị y tế hoặc chuyên gia y tế.
6. Viết tiếng Việt có dấu, ngắn gọn, dễ hiểu, giọng trung tính."""

KIND_INSTRUCTIONS: dict[ExplanationKind, str] = {
    ExplanationKind.REPORT: "Hãy viết phần giải thích kết quả đo này cho người dùng trong tối đa 150 từ.",
    ExplanationKind.QUESTION: "Hãy trả lời câu hỏi của người dùng chỉ dựa trên dữ liệu đo bên dưới, tối đa 120 từ. Nếu dữ liệu không đủ để trả lời, hãy nói rõ.",
    ExplanationKind.TREND_SUMMARY: "Hãy tóm tắt xu hướng các chỉ số qua các lần đo trong tối đa 150 từ, chỉ dùng các số thống kê đã cho.",
}


def build_user_prompt(kind: ExplanationKind, data: dict[str, Any], question: str | None = None) -> str:
    sections = [KIND_INSTRUCTIONS[kind], "Dữ liệu đo đã được kiểm tra chất lượng (JSON):", json.dumps(data, ensure_ascii=False, indent=2)]
    if kind is ExplanationKind.QUESTION and question:
        sections.append(f"Câu hỏi của người dùng: {question}")
    return "\n\n".join(sections)
