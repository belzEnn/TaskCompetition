import os
import time
import uuid
import shutil
import random
import json
from fastapi import FastAPI, Request, Form, UploadFile, File, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Створюємо потрібні папки, якщо їх немає
os.makedirs("uploads", exist_ok=True)
os.makedirs("website", exist_ok=True)
os.makedirs("images", exist_ok=True)

# Монтуємо папки для статики
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/images", StaticFiles(directory="images"), name="images")

templates = Jinja2Templates(directory="website")

# --- ЗАВАНТАЖЕННЯ ЗАВДАНЬ З JSON ---
def load_tasks():
    if not os.path.exists("tasks.json"):
        print("Помилка: Файл tasks.json не знайдено!")
        return {}
    
    with open("tasks.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        # Перетворюємо список [{"id": 0, ...}, ...] на словник {0: {"id": 0, ...}, ...}
        # Це дозволить швидко знаходити завдання за його ID
        return {task["id"]: task for task in data.get("pool", [])}

# Завантажуємо завдання при старті сервера
TASKS = load_tasks()

# Стан гравців
users_db = {}

# Черга для перевірки суддею
pending_queue = []

# --- ДОПОМІЖНІ ФУНКЦІЇ ---
def get_next_task(username: str):
    """Видає наступне випадкове завдання, яке гравець ще не робив"""
    if username not in users_db:
        return None
    completed = users_db[username]["completed_tasks"]
    available_tasks = [t_id for t_id in TASKS.keys() if t_id not in completed]
    
    if not available_tasks:
        return None # Усі завдання виконані!
    
    return random.choice(available_tasks)

# --- РОУТИ (МАРШРУТИ) ---

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    """Головна сторінка входу"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/login")
async def login(username: str = Form(...)):
    """Зберігаємо ім'я в кукі і пускаємо в гру"""
    if username not in users_db:
        users_db[username] = {"points": 0, "completed_tasks": [], "current_task_id": None}
        # Видаємо перше завдання при реєстрації
        users_db[username]["current_task_id"] = get_next_task(username)
    
    response = RedirectResponse(url="/game", status_code=303)
    response.set_cookie(key="player_name", value=username)
    return response

@app.get("/game", response_class=HTMLResponse)
async def game_page(request: Request, player_name: str = Cookie(None)):
    """Основна сторінка гри гравця"""
    if not player_name or player_name not in users_db:
        return RedirectResponse(url="/")

    user_data = users_db[player_name]
    task_id = user_data["current_task_id"]
    current_task = TASKS.get(task_id) if task_id is not None else None

    # Шукаємо суперника
    opponent_name = next((name for name in users_db if name != player_name), "Чекаємо гравця...")
    opponent_data = users_db.get(opponent_name, {"points": 0, "current_task_id": None})
    opponent_task = TASKS.get(opponent_data["current_task_id"])

    context = {
        "request": request,
        "username": player_name,
        "user_points": user_data["points"],
        "user_task": current_task,
        "opponent": {
            "name": opponent_name,
            "points": opponent_data["points"],
            "task": opponent_task
        },
        "just_sent": False
    }
    return templates.TemplateResponse("game.html", context)

@app.post("/task_complete/{task_id}")
async def complete_task(task_id: int, request: Request, file: UploadFile = File(...), player_name: str = Cookie(None)):
    """Обробка відправки фото. Гравець одразу йде далі!"""
    if not player_name:
        return RedirectResponse(url="/")

    # Зберігаємо файл
    file_ext = file.filename.split(".")[-1]
    unique_filename = f"{player_name}_{task_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    file_path = os.path.join("uploads", unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Додаємо завдання в чергу для адміна
    pending_queue.append({
        "uid": str(uuid.uuid4()),
        "username": player_name,
        "task_id": task_id,
        "task_name": TASKS[task_id]["name"],
        "points": TASKS[task_id]["points"],
        "file_path": f"uploads/{unique_filename}"
    })

    # Відзначаємо виконаним і видаємо НОВЕ завдання
    if task_id not in users_db[player_name]["completed_tasks"]:
        users_db[player_name]["completed_tasks"].append(task_id)
        
    new_task_id = get_next_task(player_name)
    users_db[player_name]["current_task_id"] = new_task_id

    current_task = TASKS.get(new_task_id) if new_task_id is not None else None
    opponent_name = next((name for name in users_db if name != player_name), "Чекаємо гравця...")
    opponent_data = users_db.get(opponent_name, {"points": 0, "current_task_id": None})
    
    context = {
        "request": request,
        "username": player_name,
        "user_points": users_db[player_name]["points"],
        "user_task": current_task,
        "opponent": {
            "name": opponent_name,
            "points": opponent_data["points"],
            "task": TASKS.get(opponent_data["current_task_id"])
        },
        "just_sent": True
    }
    return templates.TemplateResponse("game.html", context)

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request, "pending": pending_queue})

@app.post("/admin/action/{uid}/{action}")
async def admin_action(uid: str, action: str, request: Request):
    """Суддя приймає або відхиляє фото"""   
    global pending_queue
    
    task_to_process = next((item for item in pending_queue if item["uid"] == uid), None)
    
    if task_to_process:
        if action == "approve":
            username = task_to_process["username"]
            if username in users_db:
                users_db[username]["points"] += task_to_process["points"]
        
        pending_queue = [item for item in pending_queue if item["uid"] != uid]

    return templates.TemplateResponse("admin.html", {"request": request, "pending": pending_queue})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)