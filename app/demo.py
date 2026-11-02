"""Foundation UI. Talks only to the configured local API; never calls a teacher."""

import os

import gradio as gr
import httpx

API_BASE = os.environ.get("VIDOCLENS_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def check_service() -> dict:
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.get(f"{API_BASE}/health/ready")
            return {"http_status": response.status_code, "response": response.json()}
    except (httpx.HTTPError, ValueError) as exc:
        return {"status": "unreachable", "error_type": type(exc).__name__}


with gr.Blocks(title="ViDocLens — Foundation") as demo:
    gr.Markdown(
        "# ViDocLens\n"
        "Bộ khung dự án đã được dựng. OCR, student và teacher chưa được triển khai. "
        "Ứng dụng hiện chỉ kiểm tra trạng thái API; chưa nhận ảnh hay tạo câu trả lời."
    )
    status = gr.JSON(label="API readiness")
    gr.Button("Kiểm tra API").click(check_service, outputs=status)

if __name__ == "__main__":
    demo.launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=7860,
        share=False,
    )
