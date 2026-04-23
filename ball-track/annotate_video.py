import base64
import io
import os
import cv2
import numpy as np
from PIL import Image
from inference_sdk import InferenceHTTPClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────────────
INPUT_VIDEO   = "test.mp4"
OUTPUT_VIDEO  = "annotated.mp4"
API_KEY       = os.getenv("ROBOFLOW_API_KEY")
WORKSPACE     = os.getenv("ROBOFLOW_WORKSPACE", "owens-workspace-aiu3d")
WORKFLOW_ID   = os.getenv("ROBOFLOW_WORKFLOW_ID", "detect-count-and-visualize")

FPS_SAMPLE    = 10                # how many frames per second to run inference on
START_TIME    = 0                # start of window in seconds  (e.g. 10 = start at 0:10)
END_TIME      = None              # end of window in seconds    (None = until end of video)
# ─────────────────────────────────────────────────────────────────────────────

client = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=API_KEY
)

# Open input video
cap = cv2.VideoCapture(INPUT_VIDEO)
if not cap.isOpened():
    raise FileNotFoundError(f"Could not open video: {INPUT_VIDEO}")

native_fps   = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
duration_s   = total_frames / native_fps

print(f"Video: {width}x{height} @ {native_fps:.1f}fps | {duration_s:.1f}s total")

# Resolve window boundaries
start_frame = int(START_TIME * native_fps)
end_frame   = int((END_TIME if END_TIME is not None else duration_s) * native_fps)
end_frame   = min(end_frame, total_frames)

window_frames = end_frame - start_frame
window_s      = window_frames / native_fps
print(f"Annotating: {START_TIME}s → {END_TIME or duration_s:.1f}s  ({window_s:.1f}s, ~{window_frames} frames)")

# How often to sample (every N native frames)
sample_every = max(1, round(native_fps / FPS_SAMPLE))
estimated_calls = window_frames // sample_every
print(f"Sampling every {sample_every} frames → ~{estimated_calls} API calls\n")

# Output video writer (same resolution, output at FPS_SAMPLE)
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out    = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, FPS_SAMPLE, (width, height))

cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

frame_idx     = start_frame
written       = 0
last_annotated = None   # cache last annotated frame for skipped frames

while frame_idx < end_frame:
    ret, frame = cap.read()
    if not ret:
        break

    # Only call the API every sample_every frames
    if (frame_idx - start_frame) % sample_every == 0:
        # Encode frame as JPEG in memory
        _, buf   = cv2.imencode(".jpg", frame)
        b64_img  = base64.b64encode(buf).decode("utf-8")

        try:
            result = client.run_workflow(
                workspace_name=WORKSPACE,
                workflow_id=WORKFLOW_ID,
                images={"image": f"data:image/jpeg;base64,{b64_img}"},
                use_cache=False
            )

            # Decode the annotated output image
            out_b64   = result[0]["output_image"]
            img_bytes = base64.b64decode(out_b64)
            pil_img   = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            annotated = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            annotated = cv2.resize(annotated, (width, height))

            # Print detection info
            preds = result[0].get("predictions", {}).get("predictions", [])
            if preds:
                p = preds[0]
                print(f"  Frame {frame_idx:5d} | ball at ({p['x']:.0f}, {p['y']:.0f}) | conf {p['confidence']:.2f}")
            else:
                print(f"  Frame {frame_idx:5d} | no detection")

            last_annotated = annotated

        except Exception as e:
            print(f"  Frame {frame_idx:5d} | API error: {e}")
            last_annotated = frame   # fall back to raw frame

        out.write(last_annotated)
        written += 1

    frame_idx += 1

cap.release()
out.release()
print(f"\nDone! Wrote {written} frames → {OUTPUT_VIDEO}")