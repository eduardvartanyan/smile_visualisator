from dotenv import load_dotenv
import os
import time
from pathlib import Path

import requests
import replicate
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel


load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
YES_API_TOKEN = os.getenv("YES_API_TOKEN")
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN")

if not REPLICATE_API_TOKEN:
    raise RuntimeError("REPLICATE_API_TOKEN не найден")

if not YES_API_TOKEN:
    raise RuntimeError("YES_API_TOKEN не найден")

if not BACKEND_API_TOKEN:
    raise RuntimeError("BACKEND_API_TOKEN не найден")

def check_api_key(x_api_key: str | None):
    if x_api_key != BACKEND_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

OUTPUT_DIR = Path("output-images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

YES_CREATE_URL = "https://api.yesai.su/v2/yesvideo/aniimage/kling"
YES_STATUS_URL_TEMPLATE = "https://api.yesai.su/v2/yesvideo/animations/{task_id}"

YES_CUSTOMER_ID = "ncsehpgt"
YES_VERSION = "2.5"
YES_DURATION = "5"
YES_DIMENSIONS = "16:9"

POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 60 * 5

app = FastAPI(title="AI Animation Backend")


class GenerateVideoRequest(BaseModel):
    image_url: str
    edit_prompt: str = (
        "perfect white teeth, Hollywood smile, smooth nasolabial folds, "
        "youthful face skin, natural skin texture, professional portrait retouching, realistic lighting"
    )
    animate_prompt: str = (
        "The person looks into the camera, smiles wide showing beautiful white teeth, "
        "turns head slightly and nods, realistic skin texture, 4k"
    )


def generate_image_with_flux(source_image_url: str, prompt: str) -> str:
    input_data = {
        "prompt": prompt,
        "input_image": source_image_url,
        "output_format": "jpg",
    }

    output = replicate.run(
        "black-forest-labs/flux-kontext-pro",
        input=input_data,
    )

    return output.url


def create_animation_task(image_url: str, animate_prompt: str) -> int:
    headers = {
        "Authorization": f"Bearer {YES_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "version": YES_VERSION,
        "duration": YES_DURATION,
        "image_url": image_url,
        "prompt": animate_prompt,
        "final_frame_url": "",
        "dimensions": YES_DIMENSIONS,
        "customer_id": YES_CUSTOMER_ID,
    }

    response = requests.post(
        YES_CREATE_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(f"YES AI вернул ошибку: {data}")

    return data["results"]["animation_data"]["id"]


def get_animation_status(task_id: int) -> dict:
    headers = {
        "Authorization": f"Bearer {YES_API_TOKEN}",
        "Content-Type": "application/json",
    }

    status_url = YES_STATUS_URL_TEMPLATE.format(task_id=task_id)
    response = requests.get(status_url, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(f"Ошибка при проверке статуса: {data}")

    return data["results"]["animation_data"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-video-sync")
def generate_video_sync(payload: GenerateVideoRequest):
    try:
        generated_image_url = generate_image_with_flux(payload.image_url, payload.edit_prompt)
        yes_task_id = create_animation_task(generated_image_url, payload.animate_prompt)

        started_at = time.time()

        while True:
            if time.time() - started_at > POLL_TIMEOUT_SEC:
                raise HTTPException(status_code=504, detail="Timeout while waiting for video generation")

            animation_data = get_animation_status(yes_task_id)
            status = animation_data.get("status")
            result_url = animation_data.get("result_url", "")

            if status == 2 and result_url:
                return {
                    "success": True,
                    "generated_image_url": generated_image_url,
                    "yes_task_id": yes_task_id,
                    "result_url": result_url,
                    "status": "completed",
                }

            if status in (-1, 3, 4, 5):
                raise HTTPException(
                    status_code=500,
                    detail={
                        "message": "Video generation failed",
                        "yes_task_id": yes_task_id,
                        "animation_data": animation_data,
                    },
                )

            time.sleep(POLL_INTERVAL_SEC)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-video")
def generate_video(payload: GenerateVideoRequest, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    try:
        generated_image_url = generate_image_with_flux(payload.image_url, payload.edit_prompt)
        yes_task_id = create_animation_task(generated_image_url, payload.animate_prompt)

        return {
            "success": True,
            "generated_image_url": generated_image_url,
            "yes_task_id": yes_task_id,
            "status": "processing",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task/{task_id}")
def task_status(task_id: int, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)
    try:
        animation_data = get_animation_status(task_id)

        return {
            "success": True,
            "task_id": task_id,
            "status": animation_data.get("status"),
            "status_description": animation_data.get("status_description"),
            "result_url": animation_data.get("result_url"),
            "animation_data": animation_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))