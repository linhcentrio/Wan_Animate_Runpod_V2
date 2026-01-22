# WanAnimate for RunPod Serverless - Enhanced with MinIO Support

This project is a template designed to easily deploy and use WanAnimate in the RunPod Serverless environment with enhanced MinIO storage support.

WanAnimate is an AI model that generates high-quality animated videos from images using advanced video generation techniques.

## ✨ Key Features

- **High-Quality Video Generation**: Creates smooth and realistic animated videos from static images
- **MinIO Storage Integration**: Supports both MinIO storage URLs and Base64 output formats
- **Flexible Input Support**: Accepts images and videos via path, URL, or Base64 encoding
- **ComfyUI Integration**: Built on top of ComfyUI for flexible workflow management
- **Robust Error Handling**: Includes fallback mechanisms and comprehensive logging

## 🚀 Recent Updates - MinIO Support

### New Features Added:
- **MinIO Storage**: Automatic upload of generated videos to MinIO storage
- **Output Format Options**: Choose between `minio` (default) or `base64` output
- **Fallback Mechanism**: Automatically falls back to Base64 if MinIO upload fails
- **Enhanced Logging**: Detailed logging for better debugging and monitoring

## 📝 Input Parameters

The `input` object must contain the following fields. Images and videos can be input using **path, URL, or Base64** encoding.

### Required Parameters
| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `prompt` | `string` | **Yes** | Description text for the video to be generated |
| `fps` | `integer` | **Yes** | Frame rate for the output video |
| `seed` | `integer` | **Yes** | Random seed for generation |
| `cfg` | `float` | **Yes** | CFG scale for generation |
| `width` | `integer` | **Yes** | Width of the output video in pixels |
| `height` | `integer` | **Yes** | Height of the output video in pixels |
| `points_store` | `array` | **Yes** | Motion points configuration |
| `coordinates` | `array` | **Yes** | Motion coordinates |
| `neg_coordinates` | `array` | **Yes** | Negative motion coordinates |

### Optional Parameters  
| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `steps` | `integer` | `6` | Number of diffusion steps |
| `output_format` | `string` | `"minio"` | Output format: `"minio"` or `"base64"` |

### Image Input (choose one)
| Parameter | Type | Description |
| --- | --- | --- |
| `image_path` | `string` | Local path to the input image |
| `image_url` | `string` | URL to the input image |
| `image_base64` | `string` | Base64 encoded image data |

### Video Input (choose one, optional)
| Parameter | Type | Description |
| --- | --- | --- |
| `video_path` | `string` | Local path to the input video |
| `video_url` | `string` | URL to the input video |
| `video_base64` | `string` | Base64 encoded video data |

## 📤 Output Formats

### MinIO Storage (Recommended)
When `output_format` is set to `"minio"` (default), the generated video is uploaded to MinIO storage and returns a public URL.

**Success Response:**
```json
{
  "video_url": "https://media.aiclip.ai/video/wan_animate_task_12345_abc123.mp4",
  "output_format": "minio", 
  "status": "completed"
}
```

### Base64 Output
When `output_format` is set to `"base64"`, the video is returned as Base64 encoded data.

**Success Response:**
```json
{
  "video_base64": "data:video/mp4;base64,AAAAHGZ0eXBpc29tAAACAGlzb21pc28y...",
  "output_format": "base64",
  "status": "completed"
}
```

### Fallback Response
If MinIO upload fails, the system automatically falls back to Base64 format:

```json
{
  "video_base64": "data:video/mp4;base64,AAAAHGZ0eXBpc29tAAACAGlzb21pc28y...",
  "output_format": "base64",
  "status": "completed", 
  "warning": "Tải lên MinIO thất bại, trả về base64 sơ sở"
}
```

## 🎯 Example Usage

### Basic Request with MinIO Output
```json
{
  "input": {
    "prompt": "A beautiful landscape animation with flowing water",
    "image_url": "https://example.com/landscape.jpg",
    "fps": 8,
    "seed": 42,
    "cfg": 2.0,
    "width": 512,
    "height": 512,
    "steps": 6,
    "points_store": [],
    "coordinates": [[256, 256]],
    "neg_coordinates": [],
    "output_format": "minio"
  }
}
```

### Request with Base64 Output
```json
{
  "input": {
    "prompt": "Dynamic animation of a portrait",
    "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD...",
    "fps": 8,
    "seed": 42,
    "cfg": 2.0,
    "width": 512,
    "height": 512,
    "points_store": [],
    "coordinates": [[256, 256]], 
    "neg_coordinates": [],
    "output_format": "base64"
  }
}
```

## ⚙️ Technical Details

### MinIO Configuration
The MinIO client is configured with:
- **Endpoint**: `media.aiclip.ai`
- **Bucket**: `video`
- **Security**: Uses access keys for authentication
- **Auto-retry**: Falls back to Base64 if upload fails

### Error Handling
- Comprehensive input validation
- Automatic fallback mechanisms
- Detailed error logging
- Temp file cleanup

## 🛠️ Deployment

1. Build the Docker image from this repository
2. Deploy to RunPod Serverless
3. Configure your endpoint 
4. Send requests according to the API specification above

## 📄 License

This project follows the same license as the original WanAnimate model and ComfyUI framework.
