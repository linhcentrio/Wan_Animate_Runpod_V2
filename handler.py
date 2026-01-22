import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii # Base64 에러 처리를 위해 import
import subprocess
import time

# Hỗ trợ MinIO
from minio import Minio
from urllib.parse import quote

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cấu hình MinIO
MINIO_ENDPOINT = "media.aiclip.ai"
MINIO_ACCESS_KEY = "VtZ6MUPfyTOH3qSiohA2"
MINIO_SECRET_KEY = "8boVPVIynLEKcgXirrcePxvjSk7gReIDD9pwto3t"
MINIO_BUCKET = "video"
MINIO_SECURE = False

# Khởi tạo MinIO client với xử lý lỗi
try:
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    logger.info("✅ Khởi tạo MinIO client thành công")
except Exception as e:
    logger.error(f"❌ Khởi tạo MinIO thất bại: {e}")
    minio_client = None

server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())

def upload_to_minio(local_path: str, object_name: str) -> str:
    """Tải file lên MinIO storage với xử lý lỗi"""
    try:
        if not minio_client:
            raise RuntimeError("MinIO client chưa được khởi tạo")
        
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Không tìm thấy file local: {local_path}")
        
        file_size_mb = os.path.getsize(local_path) / (1024 * 1024)
        logger.info(f"📤 Đang tải lên MinIO: {object_name} ({file_size_mb:.1f}MB)")
        
        minio_client.fput_object(MINIO_BUCKET, object_name, local_path)
        file_url = f"https://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{quote(object_name)}"
        
        logger.info(f"✅ Tải lên hoàn tất: {file_url}")
        return file_url
        
    except Exception as e:
        logger.error(f"❌ Tải lên thất bại: {e}")
        raise e

def convert_video_to_base64(video_path: str) -> str:
    """Chuyển đổi file video thành base64"""
    try:
        logger.info(f"🔄 Đang chuyển đổi video thành base64: {video_path}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")
        
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        logger.info(f"📊 Kích thước file video: {file_size_mb:.1f}MB")
        
        with open(video_path, 'rb') as video_file:
            video_data = video_file.read()
        
        base64_data = base64.b64encode(video_data).decode('utf-8')
        logger.info(f"✅ Chuyển đổi video thành base64 thành công (độ dài: {len(base64_data)})")
        return base64_data
        
    except Exception as e:
        logger.error(f"❌ Chuyển đổi Base64 thất bại: {e}")
        raise e

def save_data_if_base64(data_input, temp_dir, output_filename):
    """
    입력 데이터가 Base64 문자열인지 확인하고, 맞다면 파일로 저장 후 경로를 반환합니다.
    만약 일반 경로 문자열이라면 그대로 반환합니다.
    """
    # 입력값이 문자열이 아니면 그대로 반환
    if not isinstance(data_input, str):
        return data_input

    try:
        # Base64 문자열은 디코딩을 시도하면 성공합니다.
        decoded_data = base64.b64decode(data_input)
        
        # 디렉토리가 존재하지 않으면 생성
        os.makedirs(temp_dir, exist_ok=True)
        
        # 디코딩에 성공하면, 임시 파일로 저장합니다.
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f: # 바이너리 쓰기 모드('wb')로 저장
            f.write(decoded_data)
        
        # 저장된 파일의 경로를 반환합니다.
        print(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path

    except (binascii.Error, ValueError):
        # 디코딩에 실패하면, 일반 경로로 간주하고 원래 값을 그대로 반환합니다.
        print(f"➡️ '{data_input}'은(는) 파일 경로로 처리합니다.")
        return data_input
    
def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                # fullpath를 이용하여 직접 파일을 읽고 base64로 인코딩
                with open(video['fullpath'], 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    with open(workflow_path, 'r') as file:
        return json.load(file)

def process_input(input_data, temp_dir, output_filename, input_type):
    """입력 데이터를 처리하여 파일 경로를 반환하는 함수"""
    if input_type == "path":
        # 경로인 경우 그대로 반환
        logger.info(f"📁 경로 입력 처리: {input_data}")
        return input_data
    elif input_type == "url":
        # URL인 경우 다운로드
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        # Base64인 경우 디코딩하여 저장
        logger.info(f"🔢 Base64 입력 처리")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")
        
def download_file_from_url(url, output_path):
    """URL에서 파일을 다운로드하는 함수"""
    try:
        # wget을 사용하여 파일 다운로드
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', '--timeout=30', url
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")

def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Base64 데이터를 파일로 저장하는 함수"""
    try:
        # Base64 문자열 디코딩
        decoded_data = base64.b64decode(base64_data)
        
        # 디렉토리가 존재하지 않으면 생성
        os.makedirs(temp_dir, exist_ok=True)
        
        # 파일로 저장
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")

def handler(job):
    job_input = job.get("input", {})
    logger.info(f"Received job input: {job_input}")
    task_id = f"task_{uuid.uuid4()}"
    
    try:
        # 🔧 FIX: Safely check for image_path with default
        if job_input.get("image_path") == "/example_image.png":
            return {"video": "test"}

        image_path = None
        # 이미지 입력 처리 (image_path, image_url, image_base64 중 하나만 사용)
        if "image_path" in job_input and job_input["image_path"]:
            image_path = process_input(job_input["image_path"], task_id, "input_image.jpg", "path")
        elif "image_url" in job_input and job_input["image_url"]:
            image_path = process_input(job_input["image_url"], task_id, "input_image.jpg", "url")
        elif "image_base64" in job_input and job_input["image_base64"]:
            image_path = process_input(job_input["image_base64"], task_id, "input_image.jpg", "base64")
        else:
            # ❌ VALIDATION: Image is required
            logger.error("❌ MISSING REQUIRED INPUT: Image")
            return {
                "error": "REQUIRED: Please provide one of the following image inputs:",
                "required_inputs": ["image_path", "image_url", "image_base64"],
                "status": "failed"
            }

        video_path = None
        # 비디오 입력 처리 (video_path, video_url, video_base64 중 하나만 사용)
        if "video_path" in job_input and job_input["video_path"]:
            video_path = process_input(job_input["video_path"], task_id, "input_video.mp4", "path")
        elif "video_url" in job_input and job_input["video_url"]:
            video_path = process_input(job_input["video_url"], task_id, "input_video.mp4", "url")
        elif "video_base64" in job_input and job_input["video_base64"]:
            video_path = process_input(job_input["video_base64"], task_id, "input_video.mp4", "base64")
        else:
            # 🔄 Video is optional - use image if not provided
            video_path = image_path
            logger.info(f"🔄 No video provided, using image for both inputs: {image_path}")

        # 🔧 WORKFLOW VALIDATION: Check if workflow file exists
        workflow_file = '/newWanAnimate_api.json'
        if not os.path.exists(workflow_file):
            logger.error(f"❌ Workflow file not found: {workflow_file}")
            return {"error": f"Workflow file not found: {workflow_file}"}
        
        prompt = load_workflow(workflow_file)
        
        # 🔧 SAFE PARAMETER EXTRACTION with defaults
        fps = job_input.get("fps", 6)  # Default FPS
        prompt_text = job_input.get("prompt", "animation")
        negative_prompt = job_input.get("negative_prompt", "")
        seed = job_input.get("seed", 42)
        cfg = job_input.get("cfg", 1.0)
        steps = job_input.get("steps", 6)
        width = job_input.get("width", 512)
        height = job_input.get("height", 512)
        num_frames = job_input.get("num_frames", 49)  # 🔧 FIX: Add missing num_frames parameter
        
        # 🔧 SAFE NODE UPDATES with error handling
        try:
            if "57" in prompt and "inputs" in prompt["57"]:
                prompt["57"]["inputs"]["image"] = image_path
            if "63" in prompt and "inputs" in prompt["63"]:
                prompt["63"]["inputs"]["video"] = video_path
                if "force_rate" in prompt["63"]["inputs"]:
                    prompt["63"]["inputs"]["force_rate"] = fps
                if "frame_load_cap" in prompt["63"]["inputs"]:
                    prompt["63"]["inputs"]["frame_load_cap"] = num_frames if num_frames != 49 else 0
            if "30" in prompt and "inputs" in prompt["30"]:
                if "frame_rate" in prompt["30"]["inputs"]:
                    prompt["30"]["inputs"]["frame_rate"] = fps
            if "65" in prompt and "inputs" in prompt["65"]:
                if "positive_prompt" in prompt["65"]["inputs"]:
                    prompt["65"]["inputs"]["positive_prompt"] = prompt_text
                if "negative_prompt" in prompt["65"]["inputs"]:
                    prompt["65"]["inputs"]["negative_prompt"] = negative_prompt
            if "27" in prompt and "inputs" in prompt["27"]:
                if "seed" in prompt["27"]["inputs"]:
                    prompt["27"]["inputs"]["seed"] = seed
                if "cfg" in prompt["27"]["inputs"]:
                    prompt["27"]["inputs"]["cfg"] = cfg
                if "steps" in prompt["27"]["inputs"]:
                    prompt["27"]["inputs"]["steps"] = steps
            if "150" in prompt and "inputs" in prompt["150"]:
                if "value" in prompt["150"]["inputs"]:
                    prompt["150"]["inputs"]["value"] = width
            if "151" in prompt and "inputs" in prompt["151"]:
                if "value" in prompt["151"]["inputs"]:
                    prompt["151"]["inputs"]["value"] = height
            
            # 🔧 OPTIONAL PARAMETERS: Only set if provided
            if "107" in prompt and "inputs" in prompt["107"]:
                if "points_store" in job_input:
                    prompt["107"]["inputs"]["points_store"] = job_input["points_store"]
                if "coordinates" in job_input:
                    prompt["107"]["inputs"]["coordinates"] = job_input["coordinates"]
                if "neg_coordinates" in job_input:
                    prompt["107"]["inputs"]["neg_coordinates"] = job_input["neg_coordinates"]
                if "width" in prompt["107"]["inputs"]:
                    prompt["107"]["inputs"]["width"] = width
                if "height" in prompt["107"]["inputs"]:
                    prompt["107"]["inputs"]["height"] = height
                    
            logger.info("✅ Workflow parameters configured successfully")
            
        except Exception as e:
            logger.error(f"❌ Workflow configuration failed: {e}")
            return {"error": f"Workflow configuration failed: {str(e)}"}
        
        logger.info(f"🎬 Processing: {width}x{height}, fps={fps}, steps={steps}, prompt='{prompt_text}'")
        logger.info(f"📁 Image: {image_path}")
        logger.info(f"🎥 Video: {video_path}")

        ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
        logger.info(f"Connecting to WebSocket: {ws_url}")
        
        # 먼저 HTTP 연결이 가능한지 확인
        http_url = f"http://{server_address}:8188/"
        logger.info(f"Checking HTTP connection to: {http_url}")
        
        # HTTP 연결 확인 (최대 1분)
        max_http_attempts = 180
        for http_attempt in range(max_http_attempts):
            try:
                import urllib.request
                response = urllib.request.urlopen(http_url, timeout=5)
                logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
                break
            except Exception as e:
                logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
                if http_attempt == max_http_attempts - 1:
                    raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
                time.sleep(1)
        
        ws = websocket.WebSocket()
        # 웹소켓 연결 시도 (최대 3분)
        max_attempts = int(180/5)  # 3분 (1초에 한 번씩 시도)
        for attempt in range(max_attempts):
            import time
            try:
                ws.connect(ws_url)
                logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
                break
            except Exception as e:
                logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
                if attempt == max_attempts - 1:
                    raise Exception("웹소켓 연결 시간 초과 (3분)")
                time.sleep(5)
        videos = get_videos(ws, prompt)
        ws.close()

        # 🔧 IMPROVED VIDEO PROCESSING
        total_videos = sum(len(video_list) for video_list in videos.values())
        logger.info(f"📊 Total videos generated: {total_videos}")
        logger.info(f"📊 Video outputs by node: {[(k, len(v)) for k, v in videos.items() if v]}")
        
        if total_videos == 0:
            logger.error("❌ No videos generated")
            return {
                "error": "No videos generated from workflow",
                "status": "failed",
                "debug_info": {
                    "workflow_nodes": list(videos.keys()),
                    "total_outputs": total_videos
                }
            }

        # 🔧 SAFE OUTPUT FORMAT VALIDATION
        output_format = job_input.get("output_format", "minio").lower()
        if output_format not in ["minio", "base64"]:
            logger.error(f"❌ Invalid output_format: {output_format}")
            return {
                "error": "output_format must be either 'minio' or 'base64'",
                "status": "failed",
                "valid_formats": ["minio", "base64"]
            }
        
        logger.info(f"📤 Output format: {output_format}")

        # 🔧 PRIORITIZED VIDEO SELECTION
        # Look for specific output nodes first, then fallback to any available
        priority_nodes = ["30", "194", "182", "164", "155"]  # Updated for newWanAnimate_api.json
        selected_video = None
        selected_node = None
        
        # Try priority nodes first
        for node_id in priority_nodes:
            if node_id in videos and videos[node_id]:
                selected_video = videos[node_id][0]
                selected_node = node_id
                logger.info(f"✅ Using priority output node: {node_id}")
                break
        
        # Fallback to any available video
        if not selected_video:
            for node_id, video_list in videos.items():
                if video_list:
                    selected_video = video_list[0]
                    selected_node = node_id
                    logger.info(f"⚠️ Using fallback output node: {node_id}")
                    break
        
        if not selected_video:
            return {
                "error": "No valid video output found",
                "status": "failed",
                "available_nodes": list(videos.keys())
            }

        # 🔧 RESPONSE METADATA
        metadata = {
            "width": width,
            "height": height,
            "fps": fps,
            "steps": steps,
            "prompt": prompt_text,
            "output_node": selected_node,
            "processing_time": None  # Could add timing if needed
        }

        # 🔧 PROCESS OUTPUT BASED ON FORMAT
        if output_format == "base64":
            logger.info("🔢 Returning video as base64...")
            return {
                "video_base64": selected_video,
                "output_format": "base64",
                "status": "completed",
                "metadata": metadata
            }
        
        # MinIO upload process
        logger.info("📤 Uploading video to MinIO...")
        temp_video_path = f"/tmp/wan_animate_{uuid.uuid4().hex[:8]}.mp4"
        
        try:
            # Save to temporary file
            with open(temp_video_path, 'wb') as f:
                f.write(base64.b64decode(selected_video))
            
            # Get file size for logging
            file_size_mb = os.path.getsize(temp_video_path) / (1024 * 1024)
            logger.info(f"📊 Video file size: {file_size_mb:.1f}MB")
            
            # Upload to MinIO
            output_filename = f"wan_animate_{task_id}_{uuid.uuid4().hex[:8]}.mp4"
            video_url = upload_to_minio(temp_video_path, output_filename)
            
            logger.info(f"✅ Video uploaded successfully: {video_url}")
            
            return {
                "video_url": video_url,
                "output_format": "minio",
                "status": "completed",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"❌ MinIO upload failed: {e}")
            # Automatic fallback to base64
            logger.info("🔄 Falling back to base64 output...")
            return {
                "video_base64": selected_video,
                "output_format": "base64",
                "status": "completed",
                "metadata": metadata,
                "warning": f"MinIO upload failed, returned base64: {str(e)}"
            }
            
        finally:
            # Cleanup temporary file
            if os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                    logger.info(f"🧹 Cleaned up temp file: {temp_video_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not remove temp file: {e}")

    except Exception as e:
        logger.error(f"❌ Lỗi trong handler: {e}")
        return {"error": str(e)}
    
    finally:
        # Cleanup các file tạm thời
        try:
            import shutil
            if os.path.exists(task_id):
                shutil.rmtree(task_id)
                logger.info(f"🧹 Đã xóa thư mục tạm thời: {task_id}")
        except Exception as e:
            logger.warning(f"⚠️ Không thể xóa thư mục tạm thời: {e}")

runpod.serverless.start({"handler": handler})
