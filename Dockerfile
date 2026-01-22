# ============================================================
# DOCKERFILE FOR WAN22 ANIMATE - PRODUCTION OPTIMIZED
# Tương thích: handler.py + newWanAnimate_api.json
# Date: October 2025
# ============================================================

# Base image với CUDA support
FROM wlsdml1114/multitalk-base:1.4 as runtime

# ============================================================
# METADATA
# ============================================================
LABEL maintainer="AI Team"
LABEL version="2.0"
LABEL description="Wan 2.2 Animate Video Generation with ComfyUI"

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV COMFYUI_VERSION=latest
ENV SERVER_ADDRESS=127.0.0.1

# ============================================================
# SYSTEM DEPENDENCIES
# Critical: Cần cho build các Python packages
# ============================================================
RUN apt-get update && apt-get install -y \
    # Build tools
    pkg-config \
    cmake \
    build-essential \
    gcc \
    g++ \
    # Cairo dependencies (cho một số custom nodes)
    libcairo2-dev \
    libgirepository1.0-dev \
    # Network tools
    curl \
    wget \
    # ONNX runtime dependencies
    libgomp1 \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ============================================================
# PYTHON CORE DEPENDENCIES
# ============================================================
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Hugging Face với transfer acceleration
RUN pip install --no-cache-dir -U "huggingface_hub[hf_transfer]"

# RunPod serverless framework
RUN pip install --no-cache-dir runpod websocket-client

# 🚨 CRITICAL: MinIO support - BẮT BUỘC cho handler.py
RUN pip install --no-cache-dir minio

# ✨ ONNX Support - Để fix lỗi OnnxDetectionModelLoader
# Sử dụng onnxruntime-gpu cho CUDA acceleration
RUN pip install --no-cache-dir \
    onnx \
    onnxruntime-gpu

# Additional useful packages
RUN pip install --no-cache-dir \
    pillow \
    numpy \
    opencv-python-headless

# ============================================================
# COMFYUI INSTALLATION
# ============================================================
WORKDIR /

# Clone và cài đặt ComfyUI
RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    cd /ComfyUI && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# COMFYUI CUSTOM NODES
# Thứ tự quan trọng: Dependencies trước, specific features sau
# ============================================================

# 1. ComfyUI Manager - Quản lý custom nodes
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Comfy-Org/ComfyUI-Manager.git && \
    cd ComfyUI-Manager && \
    pip install --no-cache-dir -r requirements.txt

# 2. WanVideo Wrapper - Core node cho Wan22 Animate
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper && \
    cd ComfyUI-WanVideoWrapper && \
    pip install --no-cache-dir -r requirements.txt

# 3. KJNodes - Utility nodes (ImageResize, etc)
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-KJNodes && \
    cd ComfyUI-KJNodes && \
    pip install --no-cache-dir -r requirements.txt

# 4. Video Helper Suite - Video processing nodes
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite && \
    cd ComfyUI-VideoHelperSuite && \
    pip install --no-cache-dir -r requirements.txt

# 5. ControlNet Aux - ONNX-based preprocessing (VỚI ERROR HANDLING)
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/Fannovel16/comfyui_controlnet_aux && \
    cd comfyui_controlnet_aux && \
    (pip install --no-cache-dir -r requirements.txt || echo "⚠️ Warning: comfyui_controlnet_aux install failed, continuing...")

# 6. ✨ WanAnimate Preprocess - NEW: Detection & pose estimation
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-WanAnimatePreprocess && \
    cd ComfyUI-WanAnimatePreprocess && \
    (pip install --no-cache-dir -r requirements.txt || echo "⚠️ Warning: ComfyUI-WanAnimatePreprocess install failed, continuing...")

# 7. Segment Anything 2 - Segmentation nodes
RUN cd /ComfyUI/custom_nodes && \
    git clone https://github.com/kijai/ComfyUI-segment-anything-2

# ============================================================
# MODEL DOWNLOADS - Core AI Models
# Tổng dung lượng: ~20GB
# ============================================================

# Create model directories
RUN mkdir -p /ComfyUI/models/vae \
             /ComfyUI/models/clip_vision \
             /ComfyUI/models/text_encoders \
             /ComfyUI/models/loras \
             /ComfyUI/models/diffusion_models \
             /ComfyUI/models/detection

# 1. VAE Model (1.8GB)
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors \
    -O /ComfyUI/models/vae/Wan2_1_VAE_bf16.safetensors

# 2. CLIP Vision Model (1.3GB)
RUN wget -q --show-progress \
    https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors \
    -O /ComfyUI/models/clip_vision/clip_vision_h.safetensors

# 3. Text Encoder Model (4.3GB)
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors \
    -O /ComfyUI/models/text_encoders/umt5-xxl-enc-bf16.safetensors

# 4. Relight LoRA (600MB)
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors \
    -O /ComfyUI/models/loras/WanAnimate_relight_lora_fp16.safetensors

# 5. LightX2V LoRA (1.1GB)
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors \
    -O /ComfyUI/models/loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors

# 6. Main Diffusion Model (11GB) - Wan 2.2 Animate
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors \
    -O /ComfyUI/models/diffusion_models/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors

# ============================================================
# ✨ DETECTION MODELS - NEW: ONNX-based models
# Để fix lỗi OnnxDetectionModelLoader (node #172)
# ============================================================

# 7. YOLOv10 Detection Model (54MB)
RUN wget -q --show-progress \
    https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/resolve/main/process_checkpoint/det/yolov10m.onnx \
    -O /ComfyUI/models/detection/yolov10m.onnx

# 8. ViTPose Wholebody Model (500MB)
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/vitpose_comfy/resolve/main/onnx/vitpose_h_wholebody_model.onnx \
    -O /ComfyUI/models/detection/vitpose_h_wholebody_model.onnx

# 9. ViTPose Data Binary (7MB)
RUN wget -q --show-progress \
    https://huggingface.co/Kijai/vitpose_comfy/resolve/main/onnx/vitpose_h_wholebody_data.bin \
    -O /ComfyUI/models/detection/vitpose_h_wholebody_data.bin

# ============================================================
# VERIFY MODEL DOWNLOADS
# ============================================================
RUN echo "📊 Verifying downloaded models..." && \
    ls -lh /ComfyUI/models/vae/ && \
    ls -lh /ComfyUI/models/clip_vision/ && \
    ls -lh /ComfyUI/models/text_encoders/ && \
    ls -lh /ComfyUI/models/loras/ && \
    ls -lh /ComfyUI/models/diffusion_models/ && \
    ls -lh /ComfyUI/models/detection/ && \
    echo "✅ All models downloaded successfully"

# ============================================================
# COPY PROJECT FILES
# ============================================================
WORKDIR /

# Copy handler and workflow
COPY handler.py /handler.py
COPY newWanAnimate_api.json /newWanAnimate_api.json
COPY entrypoint.sh /entrypoint.sh

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# ============================================================
# HEALTHCHECK
# ============================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8188/ || exit 1

# ============================================================
# PORTS
# ============================================================
EXPOSE 8188

# ============================================================
# VOLUME (Optional - cho caching models)
# ============================================================
# VOLUME ["/ComfyUI/models", "/ComfyUI/output"]

# ============================================================
# FINAL SETUP & LAUNCH
# ============================================================
CMD ["/entrypoint.sh"]
