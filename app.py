from dotenv import load_dotenv
import os
import json
import uuid
from pathlib import Path

import requests
import replicate
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
YES_API_TOKEN = os.getenv("YES_API_TOKEN")
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://91.229.11.38")

if not REPLICATE_API_TOKEN:
    raise RuntimeError("REPLICATE_API_TOKEN не найден")

if not YES_API_TOKEN:
    raise RuntimeError("YES_API_TOKEN не найден")

if not BACKEND_API_TOKEN:
    raise RuntimeError("BACKEND_API_TOKEN не найден")


def check_api_key(x_api_key: str | None):
    if x_api_key != BACKEND_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
GENERATED_DIR = STATIC_DIR / "generated"
RESULT_DIR = STATIC_DIR / "result"
TASKS_DIR = BASE_DIR / "tasks"

GENERATED_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(parents=True, exist_ok=True)

YES_CREATE_URL = "https://api.yesai.su/v2/yesvideo/aniimage/kling"
YES_STATUS_URL_TEMPLATE = "https://api.yesai.su/v2/yesvideo/animations/{task_id}"

YES_CUSTOMER_ID = "ncsehpgt"
YES_VERSION = "2.5"
YES_DURATION = "5"
YES_DIMENSIONS = "16:9"

app = FastAPI(title="AI Animation Backend")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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


def task_file_path(task_id: int) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def save_task_meta(task_id: int, data: dict) -> None:
    with open(task_file_path(task_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_task_meta(task_id: int) -> dict | None:
    path = task_file_path(task_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def download_file(url: str, dest_path: Path) -> None:
    response = requests.get(url, timeout=120, stream=True)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


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


def save_generated_image_locally(remote_image_url: str) -> str:
    file_name = f"{uuid.uuid4().hex}.jpg"
    local_path = GENERATED_DIR / file_name

    download_file(remote_image_url, local_path)

    return f"{PUBLIC_BASE_URL}/static/generated/{file_name}"


def save_result_video_locally(remote_video_url: str) -> str:
    file_name = f"{uuid.uuid4().hex}.mp4"
    local_path = RESULT_DIR / file_name

    download_file(remote_video_url, local_path)

    return f"{PUBLIC_BASE_URL}/static/result/{file_name}"


def create_animation_task(image_url: str, animate_prompt: str) -> dict:
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

    print("YESAI CREATE URL:", YES_CREATE_URL)
    print("YESAI PAYLOAD:", payload)

    response = requests.post(
        YES_CREATE_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print("YESAI STATUS:", response.status_code)
    print("YESAI RESPONSE:", response.text)

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(f"Ошибка создания задачи анимации: {data}")

    animation_data = data.get("results", {}).get("animation_data")
    if not animation_data:
        raise RuntimeError(f"В ответе нет animation_data: {data}")

    return animation_data


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

    animation_data = data.get("results", {}).get("animation_data")
    if not animation_data:
        raise RuntimeError(f"В ответе нет animation_data: {data}")

    return animation_data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-video")
def generate_video(payload: GenerateVideoRequest, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)

    try:
        remote_generated_image_url = generate_image_with_flux(payload.image_url, payload.edit_prompt)
        local_generated_image_url = save_generated_image_locally(remote_generated_image_url)

        animation_data = create_animation_task(local_generated_image_url, payload.animate_prompt)

        task_id = animation_data["id"]
        status_description = animation_data.get("status_description", "unknown")

        save_task_meta(task_id, {
            "task_id": task_id,
            "source_image": payload.image_url,
            "generated_image": local_generated_image_url,
            "result": "",
            "result_cached": False,
        })

        return {
            "success": True,
            "task_id": task_id,
            "status_description": status_description,
            "source_image": payload.image_url,
            "generated_image": local_generated_image_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task/{task_id}")
def task_status(task_id: int, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)

    try:
        animation_data = get_animation_status(task_id)
        meta = load_task_meta(task_id) or {}

        result_url = meta.get("result", "")

        # Если видео уже готово у внешнего сервиса, но ещё не скачано к нам — скачиваем и кэшируем локально
        remote_result_url = animation_data.get("result_url", "")
        if remote_result_url and not meta.get("result_cached", False):
            local_result_url = save_result_video_locally(remote_result_url)
            meta["result"] = local_result_url
            meta["result_cached"] = True
            save_task_meta(task_id, meta)
            result_url = local_result_url

        return {
            "success": True,
            "task_id": task_id,
            "status_description": animation_data.get("status_description", "unknown"),
            "source_image": meta.get("source_image", ""),
            "generated_image": meta.get("generated_image", ""),
            "result": result_url,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))