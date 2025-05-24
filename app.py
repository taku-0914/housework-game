from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import datetime

app = FastAPI(
    title="家事ポイントゲームAPI",
    description="勤務形態や体調に応じてポイントを補正し、週・月単位でスコアを集計するアプリ",
    version="1.0.0"
)

# 静的ファイル（HTML/CSS/JS）を配信
app.mount("/static", StaticFiles(directory="static"), name="static")

# ルートアクセスでHTMLを表示
@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# Pydanticモデル（データ構造の定義）
class TaskCreate(BaseModel):
    name: str
    base_points: int
    description: Optional[str] = None

class LogCreate(BaseModel):
    task_id: int
    user_id: str
    load: float = 1.0
    health: float = 1.0

class TaskResponse(BaseModel):
    id: int
    name: str
    base_points: int
    description: str

class LogResponse(BaseModel):
    id: int
    task_name: str
    user_id: str
    points: int
    load: float
    health: float
    created_at: str

# インメモリデータベース（実際の開発ではSQLiteやPostgreSQLを使用）
tasks_db = [
    {"id": 1, "name": "🍽️ 食器洗い", "base_points": 10, "description": "食後の食器洗いと片付け"},
    {"id": 2, "name": "👕 洗濯", "base_points": 15, "description": "洗濯物を洗って干す"},
    {"id": 3, "name": "🧹 掃除機かけ", "base_points": 20, "description": "リビングと寝室の掃除機かけ"},
    {"id": 4, "name": "🍳 料理", "base_points": 25, "description": "食事の準備と調理"},
    {"id": 5, "name": "🛏️ ベッドメイキング", "base_points": 5, "description": "ベッドを整える"}
]

logs_db = []
user_scores = {"wife": 0, "husband": 0}

# APIエンドポイント
@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(task: TaskCreate):
    """新しい家事タスクを作成"""
    new_id = max([t["id"] for t in tasks_db], default=0) + 1
    new_task = {
        "id": new_id,
        "name": task.name,
        "base_points": task.base_points,
        "description": task.description or ""
    }
    tasks_db.append(new_task)
    return new_task

@app.get("/tasks")
async def get_tasks():
    """家事タスク一覧を取得"""
    return {"tasks": tasks_db}

@app.post("/logs", response_model=dict)
async def create_log(log: LogCreate):
    """家事実行ログを記録"""
    # タスクを検索
    task = next((t for t in tasks_db if t["id"] == log.task_id), None)
    if not task:
        return {"error": "タスクが見つかりません", "status_code": 404}
    
    # ポイント計算（勤務負荷と体調で補正）
    adjusted_points = int(task["base_points"] * log.load * log.health)
    
    # ログを保存
    new_log = {
        "id": len(logs_db) + 1,
        "task_id": log.task_id,
        "task_name": task["name"],
        "user_id": log.user_id,
        "points": adjusted_points,
        "load": log.load,
        "health": log.health,
        "created_at": datetime.datetime.now().isoformat()
    }
    logs_db.append(new_log)
    
    # ユーザースコアを更新
    user_scores[log.user_id] += adjusted_points
    
    return {
        "message": "家事ログが記録されました",
        "log": new_log,
        "total_points": user_scores[log.user_id]
    }

@app.get("/scores/weekly")
async def get_weekly_scores():
    """週次スコアを取得"""
    return {
        "wife_points": user_scores["wife"],
        "husband_points": user_scores["husband"],
        "period": "今週"
    }

@app.get("/scores/monthly")
async def get_monthly_scores():
    """月次スコアを取得"""
    return {
        "wife_points": user_scores["wife"],
        "husband_points": user_scores["husband"],
        "period": "今月"
    }

@app.get("/logs")
async def get_logs():
    """家事実行ログ一覧を取得"""
    return {"logs": sorted(logs_db, key=lambda x: x["created_at"], reverse=True)}

# デバッグ用エンドポイント
@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskCreate):
    """家事タスクを更新"""
    task_index = next((i for i, t in enumerate(tasks_db) if t["id"] == task_id), None)
    if task_index is None:
        return {"error": "タスクが見つかりません", "status_code": 404}
    
    tasks_db[task_index].update({
        "name": task.name,
        "base_points": task.base_points,
        "description": task.description or ""
    })
    return tasks_db[task_index]

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    """家事タスクを削除"""
    task_index = next((i for i, t in enumerate(tasks_db) if t["id"] == task_id), None)
    if task_index is None:
        return {"error": "タスクが見つかりません", "status_code": 404}
    
    deleted_task = tasks_db.pop(task_index)
    return {"message": f"タスク '{deleted_task['name']}' を削除しました"}

@app.get("/tasks/export")
async def export_tasks_csv():
    """家事タスクをCSV形式でエクスポート"""
    import io
    import csv
    from fastapi.responses import StreamingResponse
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # ヘッダー行
    writer.writerow(["name", "base_points", "description"])
    
    # データ行
    for task in tasks_db:
        writer.writerow([task["name"], task["base_points"], task["description"]])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=housework_tasks.csv"}
    )

@app.post("/tasks/import")
async def import_tasks_csv(file: bytes):
    """CSVファイルから家事タスクをインポート"""
    import csv
    import io
    
    try:
        # バイトデータを文字列に変換
        csv_content = file.decode('utf-8-sig')
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):  # 2行目から開始（ヘッダーは1行目）
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
                new_id = max([t["id"] for t in tasks_db], default=0) + 1
                
                # タスクを追加
                new_task = {
                    "id": new_id,
                    "name": row['name'].strip(),
                    "base_points": points,
                    "description": row.get('description', '').strip()
                }
                tasks_db.append(new_task)
                imported_count += 1
                
            except Exception as e:
                errors.append(f"行{row_num}: {str(e)}")
        
        return {
            "message": f"{imported_count}件のタスクをインポートしました",
            "imported_count": imported_count,
            "errors": errors
        }
        
    except Exception as e:
        return {"error": f"CSVファイルの処理中にエラーが発生しました: {str(e)}", "status_code": 400}

@app.get("/debug/reset")
async def reset_data():
    """データをリセット（開発用）"""
    global logs_db, user_scores
    logs_db = []
    user_scores = {"wife": 0, "husband": 0}
    return {"message": "データをリセットしました"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)