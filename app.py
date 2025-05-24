from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional, Dict
import calendar

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイルの設定
app.mount("/static", StaticFiles(directory="static"), name="static")

# データモデル
class TaskCreate(BaseModel):
    name: str
    base_points: int
    description: Optional[str] = ""

class Task(TaskCreate):
    id: int

class LogCreate(BaseModel):
    task_id: int
    user_id: str  # "wife" or "husband"
    load: float = 1.0
    health: float = 1.0

class Log(BaseModel):
    id: int
    task_id: int
    task_name: str
    user_id: str
    points: int
    load: float
    health: float
    created_at: str
    date: str
    time: str

# インメモリデータストレージ
tasks_db: List[Task] = [
    Task(id=1, name="掃除機かけ", base_points=20, description="リビング・寝室の掃除"),
    Task(id=2, name="風呂掃除", base_points=15, description="浴槽・床・壁の掃除"),
    Task(id=3, name="トイレ掃除", base_points=10, description="便器・床の掃除"),
    Task(id=4, name="洗濯", base_points=15, description="洗濯機を回す・干す"),
    Task(id=5, name="料理", base_points=30, description="朝食・昼食・夕食の準備"),
    Task(id=6, name="食器洗い", base_points=10, description="食後の片付け"),
    Task(id=7, name="ゴミ出し", base_points=5, description="ゴミをまとめて出す"),
    Task(id=8, name="買い物", base_points=25, description="食材・日用品の買い出し"),
]

logs_db: List[Log] = []
next_task_id = len(tasks_db) + 1
next_log_id = 1

# ルートエンドポイント
@app.get("/")
def read_root():
    return {"message": "家事ポイントゲーム API"}

# タスク管理エンドポイント
@app.get("/tasks")
def get_tasks():
    return {"tasks": tasks_db}

@app.post("/tasks")
def create_task(task: TaskCreate):
    global next_task_id
    new_task = Task(
        id=next_task_id,
        name=task.name,
        base_points=task.base_points,
        description=task.description
    )
    tasks_db.append(new_task)
    next_task_id += 1
    return new_task

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskCreate):
    for i, t in enumerate(tasks_db):
        if t.id == task_id:
            tasks_db[i] = Task(
                id=task_id,
                name=task.name,
                base_points=task.base_points,
                description=task.description
            )
            return tasks_db[i]
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    for i, t in enumerate(tasks_db):
        if t.id == task_id:
            tasks_db.pop(i)
            return {"message": "Task deleted successfully"}
    raise HTTPException(status_code=404, detail="Task not found")

# ログ管理エンドポイント
@app.get("/logs")
def get_logs():
    return {"logs": logs_db}

@app.post("/logs")
def create_log(log: LogCreate):
    global next_log_id
    
    # タスクを検索
    task = None
    for t in tasks_db:
        if t.id == log.task_id:
            task = t
            break
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # ポイント計算
    points = int(task.base_points * log.load * log.health)
    
    # 現在時刻
    now = datetime.now()
    
    new_log = Log(
        id=next_log_id,
        task_id=log.task_id,
        task_name=task.name,
        user_id=log.user_id,
        points=points,
        load=log.load,
        health=log.health,
        created_at=now.isoformat(),
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M")
    )
    
    logs_db.append(new_log)
    next_log_id += 1
    
    return {
        "log": new_log,
        "message": f"{log.user_id}が{task.name}を完了しました！ {points}ポイント獲得！"
    }

# スコア管理エンドポイント
@app.get("/scores/weekly")
def get_weekly_scores():
    wife_score = sum(log.points for log in logs_db if log.user_id == "wife")
    husband_score = sum(log.points for log in logs_db if log.user_id == "husband")
    
    return {
        "wife": wife_score,
        "husband": husband_score,
        "total": wife_score + husband_score
    }

# カレンダー関連エンドポイント
@app.get("/calendar/{year}/{month}")
def get_calendar_data(year: int, month: int):
    # 月の日数を取得
    _, days_in_month = calendar.monthrange(year, month)
    
    # 月の最初の日の曜日を取得
    first_weekday = calendar.monthrange(year, month)[0]
    
    # 日別のデータを集計
    daily_data = {}
    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        daily_logs = [log for log in logs_db if log.date == date_str]
        
        daily_data[day] = {
            "date": date_str,
            "total_points": sum(log.points for log in daily_logs),
            "wife_points": sum(log.points for log in daily_logs if log.user_id == "wife"),
            "husband_points": sum(log.points for log in daily_logs if log.user_id == "husband"),
            "task_count": len(daily_logs)
        }
    
    # 月全体の統計
    month_str = f"{year}-{month:02d}"
    month_logs = [log for log in logs_db if log.date.startswith(month_str)]
    
    return {
        "year": year,
        "month": month,
        "days_in_month": days_in_month,
        "first_weekday": first_weekday,
        "daily_data": daily_data,
        "monthly_stats": {
            "total_points": sum(log.points for log in month_logs),
            "wife_points": sum(log.points for log in month_logs if log.user_id == "wife"),
            "husband_points": sum(log.points for log in month_logs if log.user_id == "husband"),
            "total_tasks": len(month_logs)
        }
    }

@app.get("/calendar/day/{date_str}")
def get_day_details(date_str: str):
    daily_logs = [log for log in logs_db if log.date == date_str]
    
    return {
        "date": date_str,
        "logs": daily_logs,
        "summary": {
            "total_points": sum(log.points for log in daily_logs),
            "wife_points": sum(log.points for log in daily_logs if log.user_id == "wife"),
            "husband_points": sum(log.points for log in daily_logs if log.user_id == "husband"),
            "task_count": len(daily_logs)
        }
    }

@app.get("/calendar/stats/{year}")
def get_yearly_stats(year: int):
    year_str = str(year)
    year_logs = [log for log in logs_db if log.date.startswith(year_str)]
    
    monthly_stats = {}
    for month in range(1, 13):
        month_str = f"{year}-{month:02d}"
        month_logs = [log for log in year_logs if log.date.startswith(month_str)]
        
        monthly_stats[month] = {
            "total_points": sum(log.points for log in month_logs),
            "wife_points": sum(log.points for log in month_logs if log.user_id == "wife"),
            "husband_points": sum(log.points for log in month_logs if log.user_id == "husband"),
            "task_count": len(month_logs)
        }
    
    return {
        "year": year,
        "yearly_total": {
            "total_points": sum(log.points for log in year_logs),
            "wife_points": sum(log.points for log in year_logs if log.user_id == "wife"),
            "husband_points": sum(log.points for log in year_logs if log.user_id == "husband"),
            "task_count": len(year_logs)
        },
        "monthly_stats": monthly_stats
    }

# CSV機能（基本的な実装）
@app.get("/tasks/export")
def export_tasks():
    csv_content = "id,name,base_points,description\n"
    for task in tasks_db:
        csv_content += f"{task.id},{task.name},{task.base_points},{task.description}\n"
    
    return {"csv": csv_content}

@app.post("/tasks/import")
def import_tasks(csv_data: Dict[str, str]):
    # 簡単な実装例
    return {"message": "CSV import functionality to be implemented"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
