from dotenv import load_dotenv
import os
import json
import uuid
from pathlib import Path
from enum import Enum

import requests
import replicate
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
YES_API_TOKEN = os.getenv("YES_API_TOKEN")
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

if not REPLICATE_API_TOKEN:
    raise RuntimeError("REPLICATE_API_TOKEN не найден")

if not YES_API_TOKEN:
    raise RuntimeError("YES_API_TOKEN не найден")

if not BACKEND_API_TOKEN:
    raise RuntimeError("BACKEND_API_TOKEN не найден")

if not PUBLIC_BASE_URL:
    raise RuntimeError("PUBLIC_BASE_URL не найден")


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

app = FastAPI(title="Smile Visualization API")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class Sex(str, Enum):
    male = "m"
    female = "f"


class GenerateMediaRequest(BaseModel):
    image_url: str
    edit_prompt: str = (
        "perfect white teeth, Hollywood smile, smooth nasolabial folds, "
        "youthful face skin, natural skin texture, professional portrait retouching, realistic lighting"
    )
    animate_prompt: str = (
        "The person looks into the camera, smiles wide showing beautiful white teeth, "
        "turns head slightly and nods, realistic skin texture, 4k"
    )
    age: Optional[str] = Field(None, description="Возраст человека на фото (например: '25', '35 лет', 'ребенок 7 лет')")
    sex: Optional[Sex] = Field(None, description="Пол человека на фото: m - мужской, f - женский")


def enhance_edit_prompt_with_person_info(original_prompt: str, age: Optional[str], sex: Optional[Sex]) -> str:
    """
    Дополняет промпт информацией о возрасте и поле человека для улучшения генерации
    """
    enhancements = []

    # Добавляем информацию о поле
    if sex:
        if sex == Sex.male:
            gender_desc = "man"
            gender_desc_ru = "мужчина"
        else:
            gender_desc = "woman"
            gender_desc_ru = "женщина"

        enhancements.append(gender_desc)

    # Добавляем информацию о возрасте
    if age:
        # Очищаем возраст от текста, оставляем только цифры
        age_clean = ''.join(filter(str.isdigit, age))

        if age_clean:
            age_num = int(age_clean)

            # Подбираем описание возраста для английского промпта
            if age_num < 12:
                age_desc = f"child about {age_num} years old"
            elif age_num < 18:
                age_desc = f"teenager about {age_num} years old"
            elif age_num < 30:
                age_desc = f"young adult about {age_num} years old"
            elif age_num < 45:
                age_desc = f"adult about {age_num} years old"
            elif age_num < 60:
                age_desc = f"middle-aged person about {age_num} years old"
            else:
                age_desc = f"elderly person about {age_num} years old"

            enhancements.append(age_desc)
        else:
            # Если в строке нет цифр, используем как есть
            enhancements.append(age)

    # Формируем улучшенный промпт
    if enhancements:
        # Создаем описание человека в начале промпта
        person_description = f"A {', '.join(enhancements)}. "

        # Добавляем основную задачу по ретуши
        enhanced_prompt = person_description + original_prompt
    else:
        enhanced_prompt = original_prompt

    return enhanced_prompt


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

    response = requests.post(
        YES_CREATE_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    try:
        data = response.json()
    except Exception:
        data = None

    if response.status_code >= 400:
        raise RuntimeError(f"Ошибка YesAI: status={response.status_code}, body={data or response.text}")

    if not data or not data.get("success"):
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

    try:
        data = response.json()
    except Exception:
        data = None

    if response.status_code >= 400:
        raise RuntimeError(
            f"Ошибка проверки статуса YesAI: status={response.status_code}, body={data or response.text}")

    if not data or not data.get("success"):
        raise RuntimeError(f"Ошибка при проверке статуса: {data}")

    animation_data = data.get("results", {}).get("animation_data")
    if not animation_data:
        raise RuntimeError(f"В ответе нет animation_data: {data}")

    return animation_data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-image")
def generate_image(payload: GenerateMediaRequest, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)

    try:
        # Улучшаем промпт с учетом возраста и пола
        enhanced_edit_prompt = enhance_edit_prompt_with_person_info(
            payload.edit_prompt,
            payload.age,
            payload.sex
        )

        remote_generated_image_url = generate_image_with_flux(payload.image_url, enhanced_edit_prompt)
        local_generated_image_url = save_generated_image_locally(remote_generated_image_url)

        response_data = {
            "success": True,
            "source_image": payload.image_url,
            "generated_image": local_generated_image_url,
            "used_prompt": enhanced_edit_prompt,  # Добавляем в ответ использованный промпт для отладки
        }

        # Добавляем информацию о возрасте и поле в ответ, если они были переданы
        if payload.age:
            response_data["age"] = payload.age
        if payload.sex:
            response_data["sex"] = payload.sex.value

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-video")
def generate_video(payload: GenerateMediaRequest, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)

    try:
        # Улучшаем промпт для изображения с учетом возраста и пола
        enhanced_edit_prompt = enhance_edit_prompt_with_person_info(
            payload.edit_prompt,
            payload.age,
            payload.sex
        )

        remote_generated_image_url = generate_image_with_flux(payload.image_url, enhanced_edit_prompt)
        local_generated_image_url = save_generated_image_locally(remote_generated_image_url)

        animation_data = create_animation_task(local_generated_image_url, payload.animate_prompt)

        task_id = animation_data["id"]
        status_description = animation_data.get("status_description", "unknown")

        meta_data = {
            "task_id": task_id,
            "source_image": payload.image_url,
            "generated_image": local_generated_image_url,
            "result": "",
            "result_cached": False,
            "used_prompt": enhanced_edit_prompt,
        }

        # Сохраняем возраст и пол в метаданные задачи
        if payload.age:
            meta_data["age"] = payload.age
        if payload.sex:
            meta_data["sex"] = payload.sex.value

        save_task_meta(task_id, meta_data)

        response_data = {
            "success": True,
            "task_id": task_id,
            "status_description": status_description,
            "source_image": payload.image_url,
            "generated_image": local_generated_image_url,
        }

        # Добавляем информацию о возрасте и поле в ответ
        if payload.age:
            response_data["age"] = payload.age
        if payload.sex:
            response_data["sex"] = payload.sex.value

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task/{task_id}")
def task_status(task_id: int, x_api_key: str | None = Header(default=None)):
    check_api_key(x_api_key)

    try:
        animation_data = get_animation_status(task_id)
        meta = load_task_meta(task_id) or {}

        result_url = meta.get("result", "")
        remote_result_url = animation_data.get("result_url", "")

        if remote_result_url and not meta.get("result_cached", False):
            local_result_url = save_result_video_locally(remote_result_url)
            meta["result"] = local_result_url
            meta["result_cached"] = True
            save_task_meta(task_id, meta)
            result_url = local_result_url

        response_data = {
            "success": True,
            "task_id": task_id,
            "status_description": animation_data.get("status_description", "unknown"),
            "source_image": meta.get("source_image", ""),
            "generated_image": meta.get("generated_image", ""),
            "result": result_url,
        }

        # Добавляем информацию о возрасте и поле в ответ, если они были сохранены
        if meta.get("age"):
            response_data["age"] = meta["age"]
        if meta.get("sex"):
            response_data["sex"] = meta["sex"]

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))