import json
from fastapi import FastAPI, HTTPException, Request, Response
from supabase import create_client

app = FastAPI(title="VN History Game API")

SUPABASE_URL = "https://cbqdrmiyqkhddlrjutnc.supabase.co"
SUPABASE_KEY = "sb_publishable_HVmuWEBMqizSPHRGhatFcQ_FNcet6MG"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.middleware("http")
async def custom_cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=200)
    else:
        response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.on_event("startup")
def ensure_default_admin():
    try:
        res = supabase.table("users").select("*").eq("username", "admin").execute()
        if not res.data:
            supabase.table("users").insert({
                "username": "admin",
                "password": "123",
                "role": "admin",
                "total_score": 0,
                "completed_events": "[]"
            }).execute()
    except Exception:
        pass


@app.get("/")
def root():
    return {"status": "Backend Game Lich Su dang hoat dong!"}


@app.post("/auth/login")
async def login(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    res = supabase.table("users").select("*").eq("username", username).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Tài khoản chưa tồn tại! Hãy chuyển sang tab Đăng ký.")
    user = res.data[0]
    if user["password"] != password:
        raise HTTPException(status_code=401, detail="Sai mật khẩu! Vui lòng thử lại.")

    return {"status": "login", "user": user}


@app.post("/auth/register")
async def register(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if username.lower() == "admin":
        raise HTTPException(status_code=400, detail="Tên 'admin' được hệ thống bảo lưu! Hãy chọn tên khác.")

    res = supabase.table("users").select("*").eq("username", username).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã có người dùng! Hãy chọn tên khác.")

    new_user = supabase.table("users").insert({
        "username": username,
        "password": password,
        "role": "player",
        "total_score": 0,
        "completed_events": "[]"
    }).execute()
    return {"status": "register", "user": new_user.data[0]}


@app.post("/game/score")
async def update_score(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    update_fields = {"total_score": data["score"]}
    if "completed_events" in data:
        update_fields["completed_events"] = json.dumps(data["completed_events"])

    supabase.table("users").update(update_fields).eq("username", data["username"]).execute()
    return {"message": "Đã đồng bộ điểm và tiến độ lên Supabase!"}


@app.post("/game/analytics")
async def log_analytics(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    supabase.table("analytics_logs").insert({
        "username": data["username"],
        "event_id": data["event_id"],
        "is_correct": data["is_correct"]
    }).execute()
    return {"message": "Đã ghi nhận thống kê!"}


@app.get("/leaderboard")
def get_leaderboard():
    res = (
        supabase.table("users")
        .select("username, total_score")
        .eq("role", "player")
        .order("total_score", desc=True)
        .limit(10)
        .execute()
    )
    return res.data


# ==================== API QUẢN TRỊ USER & PHÂN QUYỀN ====================

@app.get("/admin/overview")
def admin_overview():
    users_res = supabase.table("users").select("id, username, role, total_score, completed_events").order("total_score", desc=True).execute()
    logs_res = supabase.table("analytics_logs").select("is_correct").execute()

    users_list = users_res.data or []
    logs_list = logs_res.data or []
    total_logs = len(logs_list)
    correct_logs = sum(1 for item in logs_list if item.get("is_correct"))
    acc_rate = round((correct_logs / total_logs) * 100, 1) if total_logs > 0 else 0.0

    return {
        "total_users": len(users_list),
        "total_attempts": total_logs,
        "accuracy_rate": acc_rate,
        "users": users_list
    }


@app.post("/admin/user/reset")
async def admin_reset_user(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    target_user = data.get("username")
    supabase.table("users").update({
        "total_score": 0,
        "completed_events": "[]"
    }).eq("username", target_user).execute()
    return {"message": f"Đã đặt lại điểm và tiến độ của {target_user}!"}


@app.post("/admin/user/role")
async def admin_toggle_role(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    target_user = data.get("username")
    new_role = data.get("role", "player")
    if target_user == "admin":
        raise HTTPException(status_code=400, detail="Không thể hạ quyền tài khoản admin gốc!")
    supabase.table("users").update({"role": new_role}).eq("username", target_user).execute()
    return {"message": f"Đã cập nhật quyền {target_user} -> {new_role}"}


@app.post("/admin/user/delete")
async def admin_delete_user(request: Request):
    data = json.loads((await request.body()).decode("utf-8"))
    target_user = data.get("username")
    if target_user == "admin":
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản admin gốc!")
    supabase.table("users").delete().eq("username", target_user).execute()
    return {"message": f"Đã xóa tài khoản {target_user}!"}