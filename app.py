from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import datetime
import io
import csv

app = FastAPI()

# 静的ファイル配信
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# データモデル
class TaskCreate(BaseModel):
    name: str
    base_points: int
    description: Optional[str] = ""

class LogCreate(BaseModel):
    task_id: int
    user_id: str
    load: float = 1.0
    health: float = 1.0

# データストレージ
tasks = [
    {"id": 1, "name": "食器洗い", "base_points": 10, "description": "食器を洗う"},
    {"id": 2, "name": "洗濯", "base_points": 15, "description": "洗濯をする"},
    {"id": 3, "name": "掃除", "base_points": 20, "description": "部屋を掃除する"},
    {"id": 4, "name": "料理", "base_points": 25, "description": "料理を作る"}
]

logs = []
scores = {"wife": 0, "husband": 0}

def get_next_task_id():
    if not tasks:
        return 1
    return max(task["id"] for task in tasks) + 1

# API エンドポイント
@app.get("/tasks")
async def get_tasks():
    return {"tasks": tasks}

@app.post("/tasks")
async def create_task(task: TaskCreate):
    new_id = get_next_task_id()
    new_task = {
        "id": new_id,
        "name": task.name,
        "base_points": task.base_points,
        "description": task.description
    }
    tasks.append(new_task)
    return new_task

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskCreate):
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            tasks[i].update({
                "name": task.name,
                "base_points": task.base_points,
                "description": task.description
            })
            return tasks[i]
    raise HTTPException(status_code=404, detail="タスクが見つかりません")

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    for i, t in enumerate(tasks):
        if t["id"] == task_id:
            deleted_task = tasks.pop(i)
            return {"message": f"タスク '{deleted_task['name']}' を削除しました"}
    raise HTTPException(status_code=404, detail="タスクが見つかりません")

@app.post("/logs")
async def create_log(log: LogCreate):
    # タスクを探す
    task = None
    for t in tasks:
        if t["id"] == log.task_id:
            task = t
            break
    
    if not task:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    
    # ポイント計算
    points = int(task["base_points"] * log.load * log.health)
    
    # 現在時刻を取得
    now = datetime.datetime.now()
    
    # ログ作成
    new_log = {
        "id": len(logs) + 1,
        "task_id": log.task_id,
        "task_name": task["name"],
        "user_id": log.user_id,
        "points": points,
        "load": log.load,
        "health": log.health,
        "created_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M")
    }
    logs.append(new_log)
    
    # スコア更新
    scores[log.user_id] += points
    
    return {
        "message": "記録しました",
        "log": new_log,
        "total_points": scores[log.user_id]
    }

@app.get("/scores/weekly")
async def get_weekly_scores():
    return {
        "wife_points": scores["wife"],
        "husband_points": scores["husband"],
        "period": "今週"
    }

@app.get("/logs")
async def get_logs():
    return {"logs": sorted(logs, key=lambda x: x["created_at"], reverse=True)}

# カレンダー機能のエンドポイント
@app.get("/calendar/{year}/{month}")
async def get_calendar_data(year: int, month: int):
    """指定された年月のカレンダーデータを返す"""
    # 指定月のログをフィルタリング
    month_str = f"{year}-{month:02d}"
    month_logs = [log for log in logs if log.get("date", "").startswith(month_str)]
    
    # 日別の集計
    daily_data: Dict[str, Dict[str, int]] = {}
    for log in month_logs:
        date = log.get("date", "")
        if date not in daily_data:
            daily_data[date] = {
                "total_points": 0,
                "wife_points": 0,
                "husband_points": 0,
                "task_count": 0
            }
        
        daily_data[date]["total_points"] += log["points"]
        daily_data[date]["task_count"] += 1
        
        if log["user_id"] == "wife":
            daily_data[date]["wife_points"] += log["points"]
        else:
            daily_data[date]["husband_points"] += log["points"]
    
    # 月間サマリー
    total_points = sum(log["points"] for log in month_logs)
    wife_points = sum(log["points"] for log in month_logs if log["user_id"] == "wife")
    husband_points = sum(log["points"] for log in month_logs if log["user_id"] == "husband")
    
    return {
        "year": year,
        "month": month,
        "daily_data": daily_data,
        "summary": {
            "total_points": total_points,
            "wife_points": wife_points,
            "husband_points": husband_points,
            "total_tasks": len(month_logs)
        }
    }

@app.get("/calendar/day/{date}")
async def get_day_logs(date: str):
    """指定日のログ詳細を返す"""
    day_logs = [log for log in logs if log.get("date", "") == date]
    
    # 時刻順にソート
    day_logs.sort(key=lambda x: x.get("time", ""))
    
    total_points = sum(log["points"] for log in day_logs)
    wife_points = sum(log["points"] for log in day_logs if log["user_id"] == "wife")
    husband_points = sum(log["points"] for log in day_logs if log["user_id"] == "husband")
    
    return {
        "date": date,
        "logs": day_logs,
        "summary": {
            "total_points": total_points,
            "wife_points": wife_points,
            "husband_points": husband_points,
            "task_count": len(day_logs)
        }
    }

# CSV機能
@app.get("/tasks/export")
async def export_tasks_csv():
    """家事タスクをCSV形式でエクスポート"""
    try:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # ヘッダー行
        writer.writerow(["name", "base_points", "description"])
        
        # データ行
        for task in tasks:
            writer.writerow([task["name"], task["base_points"], task["description"]])
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=housework_tasks.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV エクスポートエラー: {str(e)}")

@app.post("/tasks/import")
async def import_tasks_csv(request: Request):
    """CSVファイルから家事タスクをインポート"""
    try:
        body = await request.body()
        
        # バイトデータを文字列に変換
        try:
            csv_content = body.decode('utf-8-sig')
        except:
            csv_content = body.decode('utf-8')
        
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                # 必須フィールドのチェック
                if not row.get('name') or not row.get('base_points'):
                    errors.append(f"行{row_num}: name と base_points は必須です")
                    continue
                
                # ポイントの数値チェック
                try:
                    points = int(row['base_points'])
                    if points <= 0:
                        errors.append(f"行{row_num}: base_points は正の整数である必要があります")
                        continue
                except ValueError:
                    errors.append(f"行{row_num}: base_points は数値である必要があります")
                    continue
                
                # 新しいIDを生成
                new_id = get_next_task_id()
                
                # タスクを追加
                new_task = {
                    "id": new_id,
                    "name": row['name'].strip(),
                    "base_points": points,
                    "description": row.get('description', '').strip()
                }
                tasks.append(new_task)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"行{row_num}: {str(e)}")
        
        return {
            "message": f"{imported_count}件のタスクをインポートしました",
            "imported_count": imported_count,
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSVファイルの処理中にエラーが発生しました: {str(e)}")

@app.get("/debug")
async def debug():
    return {
        "tasks_count": len(tasks),
        "logs_count": len(logs),
        "scores": scores,
        "status": "OK"
    }

# カレンダー機能のエンドポイント
@app.get("/calendar/{year}/{month}")
async def get_calendar_data(year: int, month: int):
    """指定された年月のカレンダーデータを返す"""
    month_str = f"{year}-{month:02d}"
    month_logs = [log for log in logs if log.get("date", "").startswith(month_str)]
    
    daily_data = {}
    for log in month_logs:
        date = log.get("date", "")
        if date not in daily_data:
            daily_data[date] = {
                "total_points": 0,
                "wife_points": 0,
                "husband_points": 0,
                "task_count": 0
            }
        
        daily_data[date]["total_points"] += log["points"]
        daily_data[date]["task_count"] += 1
        
        if log["user_id"] == "wife":
            daily_data[date]["wife_points"] += log["points"]
        else:
            daily_data[date]["husband_points"] += log["points"]
    
    total_points = sum(log["points"] for log in month_logs)
    wife_points = sum(log["points"] for log in month_logs if log["user_id"] == "wife")
    husband_points = sum(log["points"] for log in month_logs if log["user_id"] == "husband")
    
    return {
        "year": year,
        "month": month,
        "daily_data": daily_data,
        "summary": {
            "total_points": total_points,
            "wife_points": wife_points,
            "husband_points": husband_points,
            "total_tasks": len(month_logs)
        }
    }

@app.get("/calendar/day/{date}")
async def get_day_logs(date: str):
    """指定日のログ詳細を返す"""
    day_logs = [log for log in logs if log.get("date", "") == date]
    day_logs.sort(key=lambda x: x.get("time", ""))
    
    total_points = sum(log["points"] for log in day_logs)
    wife_points = sum(log["points"] for log in day_logs if log["user_id"] == "wife")
    husband_points = sum(log["points"] for log in day_logs if log["user_id"] == "husband")
    
    return {
        "date": date,
        "logs": day_logs,
        "summary": {
            "total_points": total_points,
            "wife_points": wife_points,
            "husband_points": husband_points,
            "task_count": len(day_logs)
        }
    }
```

# ヘルスチェック
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
