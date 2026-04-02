from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import random
import urllib.parse
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.staticfiles import StaticFiles

from app.database import engine, SessionLocal, get_db
from app.models import (
    Base,
    Device,
    EventLog,
    FamilyMember,
    ResponsibilityTask,
    TaskCompletion,
    FocusSession,
    EveningRoutine,
    Achievement,
    MemberAchievement,
    FamilyAgreement,
    TelecomNotification,
    Appliance,
    SensorReading,
    Camera,
)
from app.schemas import (
    DeviceResponse,
    DeviceUpdate,
    SensorReadingResponse,
    EventLogResponse,
    FamilyMemberResponse,
    ResponsibilityTaskResponse,
    TaskCompletionResponse,
    FocusSessionCreate,
    FocusSessionResponse,
    EveningRoutineResponse,
    TeenDashboard,
    AchievementResponse,
    MemberAchievementResponse,
    FamilyAgreementResponse,
    TelecomNotificationCreate,
    TelecomNotificationResponse,
    ApplianceResponse,
    LightScene,
    HomeStatus,
    CameraResponse,
    CameraCreate,
)

Base.metadata.create_all(bind=engine)

LEVELS = [
    (0, "Новичок"),
    (50, "Помощник"),
    (150, "Организатор"),
    (300, "Мастер порядка"),
    (500, "Хранитель дома"),
    (800, "Легенда"),
]


def get_level(points):
    level, level_name = 0, "Новичок"
    for threshold, name in LEVELS:
        if points >= threshold:
            level += 1
            level_name = name
    return level, level_name


@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_data()
    asyncio.create_task(simulate_sensors())
    yield


async def simulate_sensors():
    while True:
        await asyncio.sleep(10)
        db = SessionLocal()
        try:
            devices = db.query(Device).filter(Device.device_type == "thermostat").all()
            for d in devices:
                r = SensorReading(
                    device_id=d.id,
                    sensor_type="temperature",
                    value=round(random.uniform(20, 28), 1),
                    unit="C",
                )
                db.add(r)
            db.commit()
        finally:
            db.close()


app = FastAPI(title="Ростелеком", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ============ DEVICES ============
@app.get("/api/devices", response_model=List[DeviceResponse])
def get_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


@app.post("/api/devices/{device_id}/toggle")
def toggle_device(device_id: int, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "Устройство не найдено")
    device.is_on = not device.is_on
    db.add(
        EventLog(
            event_type="device_toggle",
            device_id=device_id,
            message=f"{device.name} {'включён' if device.is_on else 'выключен'}",
        )
    )
    db.commit()
    return {"id": device.id, "is_on": device.is_on}


@app.put("/api/devices/{device_id}", response_model=DeviceResponse)
def update_device(device_id: int, update: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "Устройство не найдено")
    if update.is_on is not None:
        device.is_on = update.is_on
    if update.state is not None:
        device.state = update.state
    db.commit()
    db.refresh(device)
    return device


# ============ LIGHTS ============
@app.get("/api/lights", response_model=List[DeviceResponse])
def get_lights(db: Session = Depends(get_db)):
    return db.query(Device).filter(Device.device_type == "light").all()


@app.get("/api/lights/scenes")
def get_light_scenes():
    return [
        {"name": "Кино", "brightness": 20, "color": "warm"},
        {"name": "Вечер", "brightness": 40, "color": "warm"},
        {"name": "Утро", "brightness": 80, "color": "cool"},
        {"name": "Ночь", "brightness": 10, "color": "warm"},
        {"name": "Чтение", "brightness": 90, "color": "white"},
        {"name": "Вечеринка", "brightness": 100, "color": "blue"},
    ]


@app.post("/api/lights/scene/{scene_name}")
def apply_light_scene(scene_name: str, db: Session = Depends(get_db)):
    scenes = {
        "Кино": (20, "warm"),
        "Вечер": (40, "warm"),
        "Утро": (80, "cool"),
        "Ночь": (10, "warm"),
        "Чтение": (90, "white"),
        "Вечеринка": (100, "blue"),
    }
    brightness, color = scenes.get(scene_name, (50, "white"))
    lights = db.query(Device).filter(Device.device_type == "light").all()
    for l in lights:
        l.state = {"brightness": brightness, "color": color}
    db.add(
        EventLog(event_type="scene_applied", message=f"Сцена '{scene_name}' применена")
    )
    db.commit()
    return {"scene": scene_name, "brightness": brightness, "color": color}


# ============ APPLIANCES ============
@app.get("/api/appliances", response_model=List[ApplianceResponse])
def get_appliances(db: Session = Depends(get_db)):
    return db.query(Appliance).all()


@app.post("/api/appliances/{appliance_id}/toggle")
def toggle_appliance(appliance_id: int, db: Session = Depends(get_db)):
    a = db.query(Appliance).filter(Appliance.id == appliance_id).first()
    if not a:
        raise HTTPException(404, "Прибор не найден")
    a.is_on = not a.is_on
    db.commit()
    return {"id": a.id, "is_on": a.is_on}


# ============ SENSORS ============
@app.get("/api/sensors", response_model=List[SensorReadingResponse])
def get_sensors(
    sensor_type: Optional[str] = None, limit: int = 50, db: Session = Depends(get_db)
):
    q = db.query(SensorReading)
    if sensor_type:
        q = q.filter(SensorReading.sensor_type == sensor_type)
    return q.order_by(SensorReading.timestamp.desc()).limit(limit).all()


# ============ EVENTS ============
@app.get("/api/events", response_model=List[EventLogResponse])
def get_events(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(EventLog).order_by(EventLog.timestamp.desc()).limit(limit).all()


# ============ TEEN DASHBOARD ============
@app.get("/api/teen/dashboard/{member_id}", response_model=TeenDashboard)
def get_dashboard(member_id: int, db: Session = Depends(get_db)):
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    completions = (
        db.query(TaskCompletion)
        .filter(
            TaskCompletion.member_id == member_id,
            TaskCompletion.completed_at >= week_ago,
        )
        .all()
    )
    total_points = sum(c.points_earned for c in completions)
    today_completions = [c for c in completions if c.completed_at >= today]
    tasks_today = (
        db.query(ResponsibilityTask)
        .filter(ResponsibilityTask.is_active == True)
        .count()
    )
    focus_sessions = (
        db.query(FocusSession)
        .filter(FocusSession.member_id == member_id, FocusSession.started_at >= today)
        .all()
    )
    streak = 0
    d = today
    for _ in range(30):
        dc = (
            db.query(TaskCompletion)
            .filter(
                TaskCompletion.member_id == member_id,
                TaskCompletion.completed_at >= d,
                TaskCompletion.completed_at < d + timedelta(days=1),
            )
            .count()
        )
        if dc > 0:
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    lights_on = (
        db.query(Device)
        .filter(Device.device_type == "light", Device.is_on == True)
        .count()
    )
    appliances_on = db.query(Appliance).filter(Appliance.is_on == True).count()
    level, level_name = get_level(total_points)
    next_threshold = LEVELS[level][0] if level < len(LEVELS) - 1 else LEVELS[-1][0]
    return TeenDashboard(
        total_points=total_points,
        level=level,
        level_name=level_name,
        points_to_next=max(0, next_threshold - total_points),
        tasks_today=tasks_today,
        tasks_completed_today=len(today_completions),
        streak_days=streak,
        focus_sessions_today=len(focus_sessions),
        focus_minutes_today=sum(s.actual_duration for s in focus_sessions),
        home_status="ready" if lights_on == 0 and appliances_on == 0 else "active",
        lights_on=lights_on,
        appliances_on=appliances_on,
    )


@app.get("/api/teen/members", response_model=List[FamilyMemberResponse])
def get_members(db: Session = Depends(get_db)):
    return db.query(FamilyMember).all()


@app.get("/api/teen/tasks", response_model=List[ResponsibilityTaskResponse])
def get_tasks(category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(ResponsibilityTask).filter(ResponsibilityTask.is_active == True)
    if category:
        q = q.filter(ResponsibilityTask.category == category)
    return q.all()


@app.post(
    "/api/teen/tasks/{task_id}/complete/{member_id}",
    response_model=TaskCompletionResponse,
)
def complete_task(task_id: int, member_id: int, db: Session = Depends(get_db)):
    task = db.query(ResponsibilityTask).filter(ResponsibilityTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Задание не найдено")
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    already = (
        db.query(TaskCompletion)
        .filter(
            TaskCompletion.task_id == task_id,
            TaskCompletion.member_id == member_id,
            TaskCompletion.completed_at >= today,
        )
        .first()
    )
    if already and not task.is_recurring:
        raise HTTPException(400, "Уже выполнено сегодня")
    completion = TaskCompletion(
        member_id=member_id, task_id=task_id, points_earned=task.points
    )
    db.add(completion)
    db.add(
        EventLog(
            event_type="task_completed",
            message=f"'{task.name}' выполнено! +{task.points} XP",
        )
    )
    db.commit()
    db.refresh(completion)
    return completion


@app.get(
    "/api/teen/tasks/completions/{member_id}",
    response_model=List[TaskCompletionResponse],
)
def get_completions(member_id: int, days: int = 7, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(TaskCompletion)
        .filter(
            TaskCompletion.member_id == member_id, TaskCompletion.completed_at >= since
        )
        .order_by(TaskCompletion.completed_at.desc())
        .all()
    )


@app.post("/api/teen/focus/start", response_model=FocusSessionResponse)
def start_focus(session: FocusSessionCreate, db: Session = Depends(get_db)):
    db_session = FocusSession(**session.model_dump())
    db.add(db_session)
    lights = db.query(Device).filter(Device.device_type == "light").all()
    for l in lights:
        l.state = {"brightness": 80, "color": "cool"}
    db.add(
        EventLog(
            event_type="focus_started",
            message=f"Фокус: {session.subject or 'учёба'} на {session.planned_duration} мин",
        )
    )
    db.commit()
    db.refresh(db_session)
    return db_session


@app.post("/api/teen/focus/{session_id}/end", response_model=FocusSessionResponse)
def end_focus(session_id: int, completed: bool = True, db: Session = Depends(get_db)):
    s = db.query(FocusSession).filter(FocusSession.id == session_id).first()
    if not s:
        raise HTTPException(404, "Сессия не найдена")
    s.ended_at = datetime.utcnow()
    s.completed = completed
    s.actual_duration = int((s.ended_at - s.started_at).total_seconds() / 60)
    lights = db.query(Device).filter(Device.device_type == "light").all()
    for l in lights:
        l.state = {"brightness": 60, "color": "warm"}
    db.add(
        EventLog(
            event_type="focus_ended", message=f"Фокус завершён: {s.actual_duration} мин"
        )
    )
    db.commit()
    db.refresh(s)
    return s


@app.get("/api/teen/focus/{member_id}", response_model=List[FocusSessionResponse])
def get_focus(member_id: int, days: int = 7, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(FocusSession)
        .filter(FocusSession.member_id == member_id, FocusSession.started_at >= since)
        .order_by(FocusSession.started_at.desc())
        .all()
    )


@app.get(
    "/api/teen/evening-routine/{member_id}", response_model=List[EveningRoutineResponse]
)
def get_routines(member_id: int, db: Session = Depends(get_db)):
    return db.query(EveningRoutine).filter(EveningRoutine.member_id == member_id).all()


@app.post("/api/teen/evening-routine/{routine_id}/start")
def start_routine(routine_id: int, db: Session = Depends(get_db)):
    r = db.query(EveningRoutine).filter(EveningRoutine.id == routine_id).first()
    if not r:
        raise HTTPException(404, "Проверка не найдена")
    r.current_step = 0
    r.completed_at = None
    r.is_active = True
    db.commit()
    return {"message": "Проверка начата"}


@app.post("/api/teen/evening-routine/{routine_id}/next-step")
def next_step(routine_id: int, db: Session = Depends(get_db)):
    r = db.query(EveningRoutine).filter(EveningRoutine.id == routine_id).first()
    if not r:
        raise HTTPException(404, "Проверка не найдена")
    r.current_step += 1
    if r.current_step >= len(r.steps):
        r.completed_at = datetime.utcnow()
    step = r.steps[r.current_step - 1] if r.current_step <= len(r.steps) else None
    if step and step.get("action") == "lights_dim":
        for l in db.query(Device).filter(Device.device_type == "light").all():
            l.state = {"brightness": step.get("brightness", 30), "color": "warm"}
    db.commit()
    return {"current_step": r.current_step, "completed": r.completed_at is not None}


@app.get("/api/teen/home-status", response_model=HomeStatus)
def get_home_status(db: Session = Depends(get_db)):
    lights_on = (
        db.query(Device)
        .filter(Device.device_type == "light", Device.is_on == True)
        .all()
    )
    appliances_on = db.query(Appliance).filter(Appliance.is_on == True).all()
    issues = []
    for l in lights_on:
        issues.append({"type": "light", "name": l.name, "room": l.room})
    for a in appliances_on:
        issues.append({"type": "appliance", "name": a.name, "room": a.room})
    return HomeStatus(
        all_clear=len(issues) == 0,
        lights_on=len(lights_on),
        appliances_on=len(appliances_on),
        issues=issues,
    )


# ============ ACHIEVEMENTS ============
@app.get("/api/achievements", response_model=List[AchievementResponse])
def get_achievements(category: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Achievement).filter(Achievement.is_active == True)
    if category:
        q = q.filter(Achievement.category == category)
    return q.all()


@app.get(
    "/api/achievements/member/{member_id}",
    response_model=List[MemberAchievementResponse],
)
def get_member_achievements(member_id: int, db: Session = Depends(get_db)):
    result = []
    for ma in (
        db.query(MemberAchievement)
        .filter(MemberAchievement.member_id == member_id)
        .all()
    ):
        a = db.query(Achievement).filter(Achievement.id == ma.achievement_id).first()
        if a:
            result.append(
                {
                    "id": ma.id,
                    "member_id": ma.member_id,
                    "achievement_id": ma.achievement_id,
                    "unlocked_at": ma.unlocked_at,
                    "progress": ma.progress,
                    "achievement": a,
                }
            )
    return result


@app.post("/api/achievements/check/{member_id}")
def check_achievements(member_id: int, db: Session = Depends(get_db)):
    completions = (
        db.query(TaskCompletion).filter(TaskCompletion.member_id == member_id).all()
    )
    total_completions = len(completions)
    total_points = sum(c.points_earned for c in completions)
    focus_sessions = (
        db.query(FocusSession).filter(FocusSession.member_id == member_id).all()
    )
    total_focus = len(focus_sessions)
    total_focus_minutes = sum(s.actual_duration for s in focus_sessions)
    routines = (
        db.query(EveningRoutine).filter(EveningRoutine.member_id == member_id).all()
    )
    completed_routines = len([r for r in routines if r.completed_at])
    unlocked = []
    for a in db.query(Achievement).filter(Achievement.is_active == True).all():
        ma = (
            db.query(MemberAchievement)
            .filter(
                MemberAchievement.member_id == member_id,
                MemberAchievement.achievement_id == a.id,
            )
            .first()
        )
        progress_map = {
            "task_completions": total_completions,
            "total_points": total_points,
            "focus_sessions": total_focus,
            "focus_minutes": total_focus_minutes,
            "routines_completed": completed_routines,
        }
        progress = progress_map.get(a.requirement_type, 0)
        if not ma:
            ma = MemberAchievement(
                member_id=member_id, achievement_id=a.id, progress=progress
            )
            db.add(ma)
        else:
            ma.progress = progress
        if progress >= a.requirement_value and not ma.unlocked_at:
            ma.unlocked_at = datetime.utcnow()
            unlocked.append({"achievement_id": a.id, "name": a.name, "icon": a.icon})
            db.add(
                EventLog(
                    event_type="achievement_unlocked", message=f"🏆 {a.icon} {a.name}!"
                )
            )
    db.commit()
    return {"unlocked": unlocked}


# ============ AGREEMENTS ============
@app.get("/api/agreements", response_model=List[FamilyAgreementResponse])
def get_agreements(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(FamilyAgreement)
    if active_only:
        q = q.filter(FamilyAgreement.is_active == True)
    return q.all()


@app.post("/api/agreements/{agreement_id}/agree/{member_id}")
def agree(agreement_id: int, member_id: int, db: Session = Depends(get_db)):
    a = db.query(FamilyAgreement).filter(FamilyAgreement.id == agreement_id).first()
    if not a:
        raise HTTPException(404, "Не найдено")
    agreed_by = a.agreed_by or []
    if member_id not in agreed_by:
        agreed_by.append(member_id)
        a.agreed_by = agreed_by
    db.commit()
    return {"agreed_by": agreed_by}


# ============ TELECOM ============
@app.post("/api/telecom/notifications", response_model=TelecomNotificationResponse)
def create_notification(n: TelecomNotificationCreate, db: Session = Depends(get_db)):
    db_n = TelecomNotification(**n.model_dump())
    db.add(db_n)
    db.commit()
    db.refresh(db_n)
    return db_n


@app.get("/api/telecom/notifications", response_model=List[TelecomNotificationResponse])
def get_notifications(
    member_id: Optional[int] = None, limit: int = 50, db: Session = Depends(get_db)
):
    q = db.query(TelecomNotification)
    if member_id:
        q = q.filter(TelecomNotification.member_id == member_id)
    return q.order_by(TelecomNotification.created_at.desc()).limit(limit).all()


@app.post("/api/telecom/notifications/{notification_id}/send")
def send_notification(notification_id: int, db: Session = Depends(get_db)):
    n = (
        db.query(TelecomNotification)
        .filter(TelecomNotification.id == notification_id)
        .first()
    )
    if not n:
        raise HTTPException(404, "Не найдено")
    n.is_sent = True
    n.sent_at = datetime.utcnow()
    db.commit()
    return {"message": "Отправлено", "channel": n.channel}


# ============ CAMERAS ============
@app.get("/api/cameras", response_model=List[CameraResponse])
def get_cameras(db: Session = Depends(get_db)):
    return db.query(Camera).all()


@app.post("/api/cameras", response_model=CameraResponse)
def create_camera(camera: CameraCreate, db: Session = Depends(get_db)):
    db_camera = Camera(
        name=camera.name,
        location=camera.location,
        stream_url=camera.stream_url,
        snapshot_url=camera.snapshot_url,
        is_recording=camera.is_recording,
        is_online=camera.is_online,
    )
    db.add(db_camera)
    db.add(
        EventLog(
            event_type="camera_added",
            message=f"Камера '{camera.name}' добавлена ({camera.location})",
        )
    )
    db.commit()
    db.refresh(db_camera)
    return db_camera


@app.delete("/api/cameras/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    c = db.query(Camera).filter(Camera.id == camera_id).first()
    if not c:
        raise HTTPException(404, "Камера не найдена")
    name = c.name
    db.delete(c)
    db.add(
        EventLog(
            event_type="camera_deleted",
            message=f"Камера '{name}' удалена",
        )
    )
    db.commit()
    return {"status": "ok", "message": f"Камера '{name}' удалена"}


@app.post("/api/cameras/{camera_id}/toggle-recording")
def toggle_recording(camera_id: int, db: Session = Depends(get_db)):
    c = db.query(Camera).filter(Camera.id == camera_id).first()
    if not c:
        raise HTTPException(404, "Камера не найдена")
    c.is_recording = not c.is_recording
    db.add(
        EventLog(
            event_type="camera_recording",
            message=f"Камера '{c.name}' {'запись включена' if c.is_recording else 'запись выключена'}",
        )
    )
    db.commit()
    return {"id": c.id, "is_recording": c.is_recording}


@app.put("/api/cameras/{camera_id}", response_model=CameraResponse)
def update_camera(camera_id: int, update: dict, db: Session = Depends(get_db)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Камера не найдена")
    if "stream_url" in update:
        camera.stream_url = update["stream_url"]
    if "snapshot_url" in update:
        camera.snapshot_url = update["snapshot_url"]
    if "is_online" in update:
        camera.is_online = update["is_online"]
    if "is_recording" in update:
        camera.is_recording = update["is_recording"]
    if "name" in update:
        camera.name = update["name"]
    if "location" in update:
        camera.location = update["location"]
    db.commit()
    db.refresh(camera)
    return camera


@app.get("/api/cameras/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: int, db: Session = Depends(get_db)):
    c = db.query(Camera).filter(Camera.id == camera_id).first()
    if not c:
        raise HTTPException(404, "Камера не найдена")
    if not c.is_online:
        raise HTTPException(503, "Камера оффлайн")
    return {
        "camera_id": camera_id,
        "snapshot_url": c.snapshot_url,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============ STATUS ============
@app.get("/api/status")
def get_status(db: Session = Depends(get_db)):
    return {
        "status": "running",
        "devices_total": db.query(Device).count(),
        "devices_on": db.query(Device).filter(Device.is_on == True).count(),
    }


# ============ SEED DATA ============
@app.on_event("startup")
def seed_data():
    db = SessionLocal()
    try:
        if db.query(Device).count() == 0:
            devices = [
                Device(
                    name="Свет в гостиной",
                    device_type="light",
                    room="Гостиная",
                    is_on=True,
                    state={"brightness": 70, "color": "warm"},
                ),
                Device(
                    name="Свет в спальне",
                    device_type="light",
                    room="Спальня",
                    is_on=False,
                    state={"brightness": 50, "color": "cool"},
                ),
                Device(
                    name="Свет на кухне",
                    device_type="light",
                    room="Кухня",
                    is_on=True,
                    state={"brightness": 100, "color": "white"},
                ),
                Device(
                    name="Свет в прихожей",
                    device_type="light",
                    room="Прихожая",
                    is_on=False,
                    state={"brightness": 60, "color": "warm"},
                ),
                Device(
                    name="Свет в детской комнате",
                    device_type="light",
                    room="Детская комната",
                    is_on=True,
                    state={"brightness": 80, "color": "cool"},
                ),
                Device(
                    name="Термостат",
                    device_type="thermostat",
                    room="Гостиная",
                    is_on=True,
                    state={"temperature": 23, "mode": "auto"},
                ),
                Device(
                    name="Кондиционер",
                    device_type="ac",
                    room="Гостиная",
                    is_on=False,
                    state={"temperature": 22, "mode": "cool"},
                ),
                Device(
                    name="Увлажнитель",
                    device_type="humidifier",
                    room="Спальня",
                    is_on=True,
                    state={"humidity": 45},
                ),
                Device(
                    name="Датчик двери",
                    device_type="door_sensor",
                    room="Прихожая",
                    is_on=True,
                    state={"status": "closed"},
                ),
                Device(
                    name="Датчик окна",
                    device_type="window_sensor",
                    room="Гостиная",
                    is_on=True,
                    state={"status": "closed"},
                ),
                Device(
                    name="Камера вход",
                    device_type="camera",
                    room="Прихожая",
                    is_on=True,
                    state={"recording": True},
                ),
                Device(
                    name="Камера двор",
                    device_type="camera",
                    room="Двор",
                    is_on=True,
                    state={"recording": True},
                ),
                Device(
                    name="Сигнализация",
                    device_type="alarm",
                    room="Прихожая",
                    is_on=False,
                    state={"mode": "disarmed"},
                ),
                Device(
                    name="Датчик движения",
                    device_type="motion_sensor",
                    room="Гостиная",
                    is_on=True,
                    state={"sensitivity": "medium"},
                ),
                Device(
                    name="Датчик температуры",
                    device_type="temp_sensor",
                    room="Спальня",
                    is_on=True,
                    state={"temperature": 22},
                ),
            ]
            db.add_all(devices)
            db.commit()

            appliances = [
                Appliance(
                    name="Стиральная машина",
                    appliance_type="washing_machine",
                    room="Ванная",
                    is_on=False,
                    energy_today=0,
                ),
                Appliance(
                    name="Посудомойка",
                    appliance_type="dishwasher",
                    room="Кухня",
                    is_on=False,
                    energy_today=0,
                ),
                Appliance(
                    name="Робот-пылесос",
                    appliance_type="robot_vacuum",
                    room="Гостиная",
                    is_on=False,
                    energy_today=0.5,
                ),
                Appliance(
                    name="Микроволновка",
                    appliance_type="microwave",
                    room="Кухня",
                    is_on=False,
                    energy_today=0,
                ),
                Appliance(
                    name="Телевизор",
                    appliance_type="tv",
                    room="Гостиная",
                    is_on=True,
                    energy_today=1.2,
                ),
                Appliance(
                    name="Утюг",
                    appliance_type="iron",
                    room="Спальня",
                    is_on=False,
                    energy_today=0,
                ),
                Appliance(
                    name="Умная розетка",
                    appliance_type="smart_plug",
                    room="Детская комната",
                    is_on=True,
                    energy_today=0.3,
                ),
            ]
            db.add_all(appliances)
            db.commit()

            members = [
                FamilyMember(name="Ребенок", role="teen", avatar_color="#4fc3f7"),
                FamilyMember(name="Мама", role="parent", avatar_color="#f48fb1"),
                FamilyMember(name="Папа", role="parent", avatar_color="#81c784"),
            ]
            db.add_all(members)
            db.commit()

            tasks = [
                ResponsibilityTask(
                    name="Проверить свет",
                    description="Выключить свет в пустых комнатах",
                    category="lights",
                    points=15,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Сделать уроки",
                    description="Выполнить домашнее задание",
                    category="study",
                    points=50,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Проверить дверь",
                    description="Убедиться что входная дверь закрыта",
                    category="security",
                    points=20,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Выключить ТВ",
                    description="Выключить телевизор когда не смотришь",
                    category="appliances",
                    points=10,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Убрать комнату",
                    description="Порядок на столе и кровати",
                    category="chores",
                    points=20,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Полить растения",
                    description="Полить цветы в гостиной и на кухне",
                    category="chores",
                    points=15,
                    is_recurring=False,
                ),
                ResponsibilityTask(
                    name="Вынести мусор",
                    description="Проверить и вынести мусор",
                    category="chores",
                    points=15,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Проверка перед сном",
                    description="Пройти все шаги вечерней проверки",
                    category="routine",
                    points=30,
                    is_recurring=True,
                ),
                ResponsibilityTask(
                    name="Прочитать 30 минут",
                    description="Чтение книги перед сном",
                    category="study",
                    points=25,
                    is_recurring=True,
                ),
            ]
            db.add_all(tasks)
            db.commit()

            routines = [
                EveningRoutine(
                    member_id=members[0].id,
                    name="Проверка перед сном ребенка",
                    start_time="21:00",
                    steps=[
                        {
                            "name": "Уроки проверены",
                            "action": "check_homework",
                            "icon": "book",
                        },
                        {
                            "name": "Свет приглушён",
                            "action": "lights_dim",
                            "brightness": 30,
                            "icon": "lightbulb",
                        },
                        {
                            "name": "Техника выключена",
                            "action": "devices_off",
                            "icon": "power",
                        },
                        {
                            "name": "Двери проверены",
                            "action": "check_doors",
                            "icon": "door",
                        },
                        {"name": "Время отдыхать", "action": "relax", "icon": "moon"},
                    ],
                    is_active=True,
                )
            ]
            db.add_all(routines)
            db.commit()

            achievements = [
                Achievement(
                    name="Мастер порядка",
                    description="Выполни 50 задач",
                    icon="🏆",
                    category="tasks",
                    requirement_type="task_completions",
                    requirement_value=50,
                ),
                Achievement(
                    name="Эко-воин",
                    description="Набери 500 очков",
                    icon="🌱",
                    category="points",
                    requirement_type="total_points",
                    requirement_value=500,
                ),
                Achievement(
                    name="Фокус-мастер",
                    description="Проведи 20 сессий фокуса",
                    icon="🎯",
                    category="focus",
                    requirement_type="focus_sessions",
                    requirement_value=20,
                ),
                Achievement(
                    name="Ночной страж",
                    description="Заверши 10 вечерних проверок",
                    icon="🌙",
                    category="routine",
                    requirement_type="routines_completed",
                    requirement_value=10,
                ),
                Achievement(
                    name="Марафонец",
                    description="Накопи 1000 минут фокуса",
                    icon="⏱️",
                    category="focus",
                    requirement_type="focus_minutes",
                    requirement_value=1000,
                ),
            ]
            db.add_all(achievements)
            db.commit()

            agreements = [
                FamilyAgreement(
                    title="Правила использования интернета",
                    description="Соглашение между родителями и ребенком",
                    rules=[
                        {"rule": "Уроки сделаны до развлечений", "type": "condition"},
                        {
                            "rule": "Максимум 2 часа развлечений в будни",
                            "type": "limit",
                        },
                        {"rule": "Интернет отключается в 22:00", "type": "schedule"},
                    ],
                    rewards=[
                        {
                            "reward": "+30 минут за каждую выполненную задачу",
                            "type": "bonus",
                        },
                        {
                            "reward": "Свободный выбор фильма в пятницу",
                            "type": "privilege",
                        },
                    ],
                    created_by=2,
                    agreed_by=[2, 3],
                )
            ]
            db.add_all(agreements)
            db.commit()

            cameras = [
                Camera(
                    name="Камера вход",
                    location="Прихожая",
                    stream_url="/api/cameras/1/stream",
                    snapshot_url="data:image/svg+xml,"
                    + urllib.parse.quote(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect fill="#1a1d27" width="640" height="480"/><text x="320" y="240" text-anchor="middle" fill="#4fc3f7" font-size="24" font-family="sans-serif">📹 Камера вход</text><text x="320" y="270" text-anchor="middle" fill="#9aa0a6" font-size="14" font-family="sans-serif">Прихожая</text></svg>'
                    ),
                    is_recording=True,
                    is_online=True,
                ),
                Camera(
                    name="Камера двор",
                    location="Двор",
                    stream_url="/api/cameras/2/stream",
                    snapshot_url="data:image/svg+xml,"
                    + urllib.parse.quote(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect fill="#1a1d27" width="640" height="480"/><text x="320" y="240" text-anchor="middle" fill="#4fc3f7" font-size="24" font-family="sans-serif">📹 Камера двор</text><text x="320" y="270" text-anchor="middle" fill="#9aa0a6" font-size="14" font-family="sans-serif">Двор</text></svg>'
                    ),
                    is_recording=True,
                    is_online=True,
                ),
            ]
            db.add_all(cameras)
            db.commit()
    finally:
        db.close()


# ============ EMBEDDED HTML APP ============
@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ростелеком</title>
 <style>
 
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#FFFFFF;--bg2:#FF8820;--card:#8800FF;--hover:#2d3244;--text:#FFFFFF;--text2:#000000;--accent:#FFFFFF;--success:#66bb6a;--warn:#ffa726;--danger:#ef5350;--border:#323744;--r:12px}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;font-size:16px}
.app{display:flex;min-height:100vh}
.sidebar{width:240px;background:var(--bg2);border-right:1px solid var(--border);padding:20px 0;position:fixed;height:100vh;z-index:10;overflow-y:auto}
.logo{padding:0 20px 24px;border-bottom:none solid var(--border);margin-bottom:16px;font-size:22px;font-weight:800;color:var(--text2);display:flex; justify-content:center;align-items:center;gap:8px}
.nav{padding:14px 20px;color:var(--text2);cursor:pointer;transition:.2s;border-left:4px solid transparent;display:flex;align-items:center;gap:10px;font-size:17px;font-weight:600}
.nav:hover{color:var(--text)}
.nav.active{color:var(--accent);border-left-color:var(--accent)}
.nav-section{padding:10px 20px;color:var(--text2);font-size:13px;text-transform:uppercase;letter-spacing:1px;margin-top:12px;font-weight:700}
.main{flex:1;margin-left:240px;padding:32px}
.page{display:none}.page.active{display:block}
h1{font-size:32px;margin-bottom:8px;font-weight:800;color: var(--text2);text-align: center;}h2{font-size:24px;font-weight:700;margin-bottom:16px; color: var(--text2)}.sub{color:var(--text2);margin-bottom:32px;font-size:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;margin-bottom:32px; margin-top: 140px}
.stat{background:var(--card);border-radius:var(--r);padding:24px}.stat .label{color:var(--text2);font-size:15px;margin-bottom:8px;font-weight:500}.stat .value{font-size:36px;font-weight:800}.stat .icon{color:var(--accent);margin-bottom:12px;font-size:28px}
.dcard{background:var(--card);border-radius:var(--r);padding:24px;cursor:pointer;transition:.2s;border:1px solid transparent; margin-bottom: 20px;}.dcard:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,0,0,.4)}.dcard.on{border-color:var(--accent)}
.dhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.dname{font-weight:700;font-size:17px}.droom{color:var(--text2);font-size:14px}
.tgl{width:52px;height:28px;border-radius:14px;border:none;background:var(--hover);cursor:pointer;position:relative;transition:.3s}.tgl.on{background:#00FF44}.tgl::after{content:'';position:absolute;width:22px;height:22px;border-radius:50%;background:#fff;top:3px;left:3px;transition:.3s}.tgl.on::after{left:27px}
.slider{margin-top:12px}.slider label{color:var(--text2);font-size:14px;display:block;margin-bottom:8px;font-weight:500}.slider input[type=range]{width:100%;height:6px;border-radius:3px;background:var(--hover);outline:none;-webkit-appearance:none}.slider input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:18px;height:18px;border-radius:50%;background:var(--accent);cursor:pointer}
.btn{padding:12px 24px;border-radius:8px;border:none;cursor:pointer;font-size:15px;font-weight:600;transition:.2s;color:#fff}.btn-p{background:#00FF44;}.btn-s{background:var(--success)}.btn-d{background:var(--danger)}.btn-w{background:var(--warn)}
.elist{background:var(--card);border-radius:var(--r);padding:20px}.eitem{padding:14px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}.eitem:last-child{border:none}.etime{color:var(--text2);font-size:14px}
.badge{padding:5px 12px;border-radius:12px;font-size:13px;font-weight:700}.badge-s{background:rgba(102,187,106,.15);color:var(--success)}.badge-w{background:rgba(255,167,38,.15);color:var(--warn)}.badge-d{background:rgba(239,83,80,.15);color:var(--danger)}
.tabs{display:flex;gap:8px;margin-bottom:24px}.tab{padding:10px 18px;border-radius:8px;background:var(--hover);color:var(--text2);cursor:pointer;font-size:15px;font-weight:600;border:none}.tab.active{background:var(--accent);color:#fff}
.progress-bar{height:10px;background:var(--hover);border-radius:5px;overflow:hidden;margin:8px 0}.progress-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--success));border-radius:5px;transition:width .5s}
.ach-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.ach-card{background:var(--card);border-radius:var(--r);padding:24px;border:2px solid transparent;transition:.3s}.ach-card.unlocked{border-color:var(--success)}
.ach-icon{font-size:36px;margin-bottom:8px}.ach-name{font-weight:700;font-size:17px;margin-bottom:4px}.ach-desc{color:var(--text2);font-size:14px;margin-bottom:12px}
.task-item{background:var(--card);border-radius:var(--r);padding:18px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}.task-item .task-name{font-weight:700;font-size:16px}.task-item .task-desc{color:var(--text2);font-size:14px}
.task-cat{font-size:13px;padding:3px 10px;border-radius:8px;background:var(--hover);color:var(--text2);font-weight:600}
.alert-box{background:rgba(17, 255, 0, 0.15);border:1px solid var(--danger);border-radius:var(--r);padding:18px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;font-size:15px; color: #000000;}
.form-group{margin-bottom:16px}.form-group label{display:block;color:var(--text2);font-size:15px;margin-bottom:8px;font-weight:600}.form-group input,.form-group select,.form-group textarea{width:100%;padding:12px 14px;background:var(--hover);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:15px}
.form-group textarea{min-height:80px;resize:vertical}
.agreement-card{background:var(--card);border-radius:var(--r);padding:24px;margin-bottom:16px;border-left:4px solid var(--accent)}
.agreement-card h3{margin-bottom:8px;font-weight:700;font-size:18px}.agreement-card p{color:var(--text2);font-size:15px;margin-bottom:12px}
.agreement-rules li,.agreement-rewards li{padding:6px 0;font-size:15px;display:flex;align-items:center;gap:8px}
.notif-card{background:var(--card);border-radius:var(--r);padding:18px;margin-bottom:8px;border-left:4px solid var(--accent)}.notif-card.danger{border-left-color:var(--danger)}.notif-card.success{border-left-color:var(--success)}
.notif-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.notif-msg{color:var(--text2);font-size:15px}.notif-time{color:var(--text2);font-size:13px}
.page-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px}
.color-dots{display:flex;gap:8px;margin-top:8px}.color-dot{width:26px;height:26px;border-radius:50%;cursor:pointer;border:2px solid transparent}.color-dot.active{border-color:#fff}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
</style>
</head>
<body>
<div class="app">
<nav class="sidebar">
<div class="logo" aria-label="Ростелеком" role="img">
  <img src="/static/logo.png" alt="Ростелеком" style="height:190px; width:auto; display:block;">
</div>
<div class="nav active" onclick="showPage('dashboard')">Главная</div>
<div class="nav" onclick="showPage('myhome')">Мой дом</div>
<div class="nav" onclick="showPage('lights')">Освещение</div>
<div class="nav" onclick="showPage('appliances')">Smart техника</div>
<div class="nav" onclick="showPage('cameras')">Камеры</div>
<div class="nav" onclick="showPage('focus')">Фокус</div>
<div class="nav" onclick="showPage('evening')">Проверка перед сном</div>
<div class="nav" onclick="showPage('achievements')">Достижения</div>
<div class="nav" onclick="showPage('agreements')">Соглашения</div>
<div class="nav" onclick="showPage('notifications')">Уведомления</div>
<div class="nav" onclick="showPage('voice')">Голосовой помощник</div>
</nav>
<main class="main">

<!-- DASHBOARD -->
<div id="dashboard" class="page active">
<h1> Добро пожаловать в умный дом от Ростелеком</h1>
<div class="grid" id="dash-stats"></div>
<div id="dash-alerts"></div>
<h2 style="margin-bottom:16px">⚡ Быстрые действия</h2>
<div class="grid" style="grid-template-columns:repeat(4,1fr)">
<div class="stat" style="cursor:pointer;text-align:center" onclick="showPage('lights')"><div class="icon">💡</div><div class="label">Свет</div></div>
<div class="stat" style="cursor:pointer;text-align:center" onclick="showPage('myhome')"><div class="icon">🔒</div><div class="label">Двери</div></div>
<div class="stat" style="cursor:pointer;text-align:center" onclick="showPage('focus')"><div class="icon">🎯</div><div class="label">Фокус</div></div>
<div class="stat" style="cursor:pointer;text-align:center" onclick="showPage('evening')"><div class="icon">🌙</div><div class="label">Вечер</div></div>
</div>
</div>

<!-- MY HOME -->
<div id="myhome" class="page">
<h1>⭐ Мой дом</h1>
<p class="sub">Статус дома и задачи</p>
<div class="grid" id="home-stats"></div>
<div id="home-issues"></div>
<h2 style="margin-bottom:16px">📋 Задачи на сегодня</h2>
<div id="tasks-list"></div>
</div>

<!-- FOCUS -->
<div id="focus" class="page">
<h1>🎯 Фокус-режим</h1>
<p class="sub" style="text-align:center">Таймер для концентрации</p>
<div style="display:flex; justify-content:center; align-items:center; min-height:300px;">
    <div style="width:100%; max-width:450px;">
        <div class="form-group" style="margin-bottom:20px; text-align:center;">
            <label style="display:block; margin-bottom:10px; font-weight:600;">📚 Предмет</label>
            <select id="focus-subject" style="width:100%; padding:12px; background:#8800FF; border:1px solid var(--border); border-radius:8px; color:var(--text); font-size:15px;">
                <option>Математика</option>
                <option>Русский язык</option>
                <option>Физика</option>
                <option>История</option>
                <option>Английский</option>
                <option>Информатика</option>
                <option>Другое</option>
            </select>
        </div>
        
        <div class="form-group" style="margin-bottom:30px; text-align:center;">
            <label style="display:block; margin-bottom:10px; font-weight:600;">⏱️ Длительность</label>
            <select id="focus-duration" style="width:100%; padding:12px; background:#8800FF; border:1px solid var(--border); border-radius:8px; color:var(--text); font-size:15px;">
                <option value="15">15 минут</option>
                <option value="25" selected>25 минут</option>
                <option value="45">45 минут</option>
                <option value="60">60 минут</option>
            </select>
        </div>
        
        <button class="btn btn-p" onclick="startFocus()" style="width:100%; background:#FF8820; color:#fff; padding:14px; border-radius:8px; border:none; cursor:pointer; font-size:16px; font-weight:600; transition:.2s;">🚀 Начать фокус</button>
    </div>
</div>

<div id="focus-active" style="display:none;margin-top:32px;text-align:center">
    <div style="font-size:64px;font-weight:700;color:var(--accent)" id="focus-timer">25:00</div>
    <p style="color:var(--text2);margin:16px 0" id="focus-subject-display"></p>
    <div style="display:flex;gap:12px;justify-content:center">
        <button class="btn btn-w" onclick="endFocus(false)">⏹ Завершить</button>
        <button class="btn btn-s" onclick="endFocus(true)">✅ Готово!</button>
    </div>
</div>

<div id="focus-history" style="margin-top:32px"></div>
</div>

<!-- EVENING ROUTINE -->
<div id="evening" class="page">
<h1>🌙 Проверка перед сном</h1>
<p class="sub">Пошаговая подготовка ко сну</p>
<div id="routine-status"></div>
<div id="routine-steps"></div>
</div>

<!-- LIGHTS -->
<div id="lights" class="page">
<h1>💡 Освещение</h1>
<p class="sub">Управление светом</p>
<div class="tabs">
<button class="tab active" onclick="showLightTab('devices')">Устройства</button>
<button class="tab" onclick="showLightTab('scenes')">Сцены</button>
</div>
<div id="lights-devices"></div>
<div id="lights-scenes" style="display:none"></div>
</div>

<!-- APPLIANCES -->
<div id="appliances" class="page">
<h1>🔌 Smart техника</h1>
<p class="sub">Управление бытовой техникой</p>
<div id="appliances-list"></div>
</div>

<!-- ACHIEVEMENTS -->
<div id="achievements" class="page">
<div class="page-header">
<div><h1>🏆 Достижения</h1><p class="sub">Разблокируй достижения за активность</p></div>
<button class="btn btn-p" onclick="checkAchievements()">Проверить прогресс</button>
</div>
<div class="grid" id="ach-stats"></div>
<div class="ach-grid" id="ach-list"></div>
</div>

<!-- AGREEMENTS -->
<div id="agreements" class="page">
<h1>📋 Семейные соглашения</h1>
<p class="sub">Правила и договорённости</p>
<div id="agreements-list"></div>
</div>

<!-- NOTIFICATIONS -->
<div id="notifications" class="page">
<div class="page-header">
<div><h1>🔔 Уведомления</h1><p class="sub">Управление через оператора</p></div>
<button class="btn btn-p" onclick="showNotifForm()">Создать</button>
</div>
<div id="notif-form" style="display:none" class="card" style="background:var(--card);padding:24px;border-radius:var(--r);margin-bottom:24px">
<div class="form-group"><label>Тип</label><select id="notif-type"><option value="info">Информация</option><option value="alert">Тревога</option><option value="reminder">Напоминание</option></select></div>
<div class="form-group"><label>Канал</label><select id="notif-channel"><option value="push">Push</option><option value="sms">SMS</option></select></div>
<div class="form-group"><label>Сообщение</label><textarea id="notif-message" placeholder="Текст уведомления"></textarea></div>
<button class="btn btn-p" onclick="createNotification()">Отправить</button>
</div>
<div id="notifications-list"></div>
</div>

<!-- CAMERAS -->
<div id="cameras" class="page">
<h1>📹 Видеонаблюдение</h1>
<p class="sub">Камеры наблюдения в реальном времени</p>
<div id="cameras-stats" class="grid" style="margin-bottom:24px"></div>
<div style="margin-bottom:24px;display:flex;gap:12px;align-items:center">
<select id="camera-select" style="padding:10px 14px;background:var(--hover);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:15px;flex:1"></select>
<button class="btn btn-p" onclick="startWebcam()">📷 Включить камеру</button>
<button class="btn btn-d" onclick="stopWebcam()">⏹ Выключить</button>
<button class="btn btn-s" onclick="showAddCameraForm()" style="padding:10px 20px;font-size:15px">➕ Добавить камеру</button>
</div>
<div id="add-camera-form" style="display:none;margin-bottom:24px;background:var(--card);border-radius:var(--r);padding:24px">
<h2 style="margin-bottom:16px">Подключение новой камеры</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
<div>
<label style="display:block;margin-bottom:6px;font-size:14px;color:var(--text2)">Название</label>
<input id="new-cam-name" type="text" placeholder="Например: Камера вход" style="width:100%;padding:10px 14px;background:var(--hover);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:15px">
</div>
<div>
<label style="display:block;margin-bottom:6px;font-size:14px;color:var(--text2)">Расположение</label>
<input id="new-cam-location" type="text" placeholder="Например: Прихожая" style="width:100%;padding:10px 14px;background:var(--hover);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:15px">
</div>
</div>
<div style="margin-bottom:16px">
<label style="display:block;margin-bottom:6px;font-size:14px;color:var(--text2)">URL видеопотока (HTTP/MJPEG)</label>
<input id="new-cam-url" type="text" placeholder="http://192.168.1.100:8080/video" style="width:100%;padding:10px 14px;background:var(--hover);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:15px">
</div>
<div style="margin-bottom:16px;display:flex;gap:16px;align-items:center">
<label style="display:flex;align-items:center;gap:8px;cursor:pointer">
<input id="new-cam-recording" type="checkbox" checked style="width:18px;height:18px;accent-color:var(--accent)">
<span style="font-size:14px">Запись</span>
</label>
<label style="display:flex;align-items:center;gap:8px;cursor:pointer">
<input id="new-cam-online" type="checkbox" checked style="width:18px;height:18px;accent-color:var(--accent)">
<span style="font-size:14px">Онлайн</span>
</label>
</div>
<div style="display:flex;gap:12px">
<button class="btn btn-p" onclick="addCamera()" style="padding:10px 24px">Подключить</button>
<button class="btn btn-s" onclick="hideAddCameraForm()" style="padding:10px 24px">Отмена</button>
</div>
</div>
<div id="webcam-container" style="display:none;margin-bottom:32px">
<div style="background:#000;border-radius:var(--r);overflow:hidden;position:relative;aspect-ratio:16/9;max-width:800px;margin:0 auto">
<video id="webcam-video" autoplay playsinline style="width:100%;height:100%;object-fit:cover"></video>
<canvas id="webcam-canvas" style="display:none"></canvas>
<div style="position:absolute;top:12px;left:12px;display:flex;gap:8px;align-items:center">
<span id="rec-indicator" class="badge badge-d" style="display:none;animation:pulse 1.5s infinite">● REC</span>
<span id="live-badge" class="badge badge-s">● LIVE</span>
</div>
<div style="position:absolute;bottom:12px;right:12px">
<button class="btn btn-p" onclick="takeSnapshot()" style="padding:8px 16px;font-size:13px">📸 Снимок</button>
</div>
</div>
</div>
<div id="snapshots-section" style="margin-bottom:32px">
<h2 style="margin-bottom:12px">📸 Снимки</h2>
<div id="snapshots-grid" class="grid" style="grid-template-columns:repeat(auto-fill,minmax(200px,1fr))"></div>
</div>
<div id="cameras-grid" class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))"></div>
</div>

<!-- VOICE ASSISTANT -->
<div id="voice" class="page">
<h1>Голосовой помощник</h1>
<p class="sub" style="text-align:center">Управляйте умным домом голосом</p>
<div style="display:flex; justify-content:center; align-items:center; min-height:300px; flex-direction:column; gap:24px;">
    <div id="voice-status" style="text-align:center; font-size:18px; color:var(--text2);">Нажмите кнопку и скажите команду</div>
    <div id="voice-wave" style="display:none; width:200px; height:60px; position:relative;">
        <div style="position:absolute; left:0; top:50%; width:100%; height:2px; background:var(--accent); transform:translateY(-50%);"></div>
        <div class="wave-bar" style="position:absolute; left:20px; bottom:0; width:6px; height:20px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:40px; bottom:0; width:6px; height:35px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.1s infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:60px; bottom:0; width:6px; height:50px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.2s infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:80px; bottom:0; width:6px; height:40px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.3s infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:100px; bottom:0; width:6px; height:30px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.4s infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:120px; bottom:0; width:6px; height:45px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.5s infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:140px; bottom:0; width:6px; height:25px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.6s infinite;"></div>
        <div class="wave-bar" style="position:absolute; left:160px; bottom:0; width:6px; height:35px; background:#00FF44; border-radius:3px; animation:waveAnim 0.8s ease-in-out 0.7s infinite;"></div>
    </div>
    <div id="voice-text" style="text-align:center; font-size:20px; color:var(--text); min-height:30px; font-weight:600;"></div>
    <div id="voice-result" style="text-align:center; font-size:16px; color:var(--text2); min-height:40px;"></div>
    <button id="voice-btn" class="btn btn-p" onclick="toggleVoice()" style="width:80px; height:80px; border-radius:50%; background:#FF8820; font-size:36px; display:flex; align-items:center; justify-content:center; border:none; cursor:pointer; transition:.3s; box-shadow:0 4px 20px rgba(255,136,32,0.4);">🎙</button>
    <div style="margin-top:20px; text-align:center;">
        <h3 style="margin-bottom:12px; color:var(--text2);">Команды:</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; max-width:400px;">
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>💡 Включи свет в гостиной</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>🔌 Выключи телевизор</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>🎬 Сцена кино</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>🌙 Ночной режим</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>📹 Камеры</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>🏠 Статус дома</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>🎯 Начать фокус</span></div>
            <div class="task-item" style="margin:0; padding:10px; font-size:14px;"><span>📋 Мои задачи</span></div>
        </div>
    </div>
    <div id="voice-history" style="width:100%; max-width:500px; margin-top:24px;"></div>
</div>
</div>

<style>
@keyframes waveAnim{0%,100%{transform:scaleY(0.4)}50%{transform:scaleY(1)}}
</style>

</main>
</div>
<script>
const API='/api', MEMBER_ID=1;
let focusInterval=null, focusStart=null;
let cameraStreamIntervals = {};

function showPage(id){
  // Остановить обновление камер при смене страницы
for(let key in cameraStreamIntervals) {
  clearInterval(cameraStreamIntervals[key]);
  delete cameraStreamIntervals[key];
}
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  document.querySelectorAll('.nav').forEach(n=>n.classList.remove('active'));
  event.target.classList.add('active');
  if(id==='dashboard')loadDashboard();
  if(id==='myhome')loadMyHome();
  if(id==='lights')loadLights();
  if(id==='appliances')loadAppliances();
  if(id==='achievements')loadAchievements();
  if(id==='agreements')loadAgreements();
  if(id==='notifications')loadNotifications();
  if(id==='events')loadEvents();
  if(id==='evening')loadEvening();
  if(id==='cameras')loadCameras();
}

async function api(url){return(await fetch(API+url)).json()}
async function post(url,body){return(await fetch(API+url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})})).json()}

async function loadDashboard(){
  const d=await api(`/teen/dashboard/${MEMBER_ID}`);
  document.getElementById('dash-stats').innerHTML=`
    <div class="stat"><div class="icon">🏆</div><div class="value">${d.total_points}</div><div class="label">XP очков</div></div>
    <div class="stat"><div class="icon">📊</div><div class="value">${d.level_name}</div><div class="label">Уровень ${d.level}</div></div>
    <div class="stat"><div class="icon">🔥</div><div class="value">${d.streak_days}</div><div class="label">Дней подряд</div></div>
    <div class="stat"><div class="icon">🏠</div><div class="value">${d.home_status==='ready'?'✅':'⚠️'}</div><div class="label">Статус дома</div></div>`;
  const alerts=[];
  if(d.lights_on>0)alerts.push(`💡 ${d.lights_on} свет(а) включено`);
  if(d.appliances_on>0)alerts.push(`🔌 ${d.appliances_on} прибор(ов) работает`);
  document.getElementById('dash-alerts').innerHTML=alerts.length?alerts.map(a=>`<div class="alert-box"><span>${a}</span><button class="btn btn-d" onclick="showPage('myhome')">Проверить</button></div>`).join(''):'<p style="color:var(--success);margin-bottom:24px">✅ Всё в порядке!</p>';
}

async function loadMyHome(){
  const d=await api(`/teen/dashboard/${MEMBER_ID}`);
  document.getElementById('home-stats').innerHTML=`
    <div class="stat"><div class="value">${d.tasks_completed_today}/${d.tasks_today}</div><div class="label">Задач выполнено</div></div>
    <div class="stat"><div class="value">${d.focus_minutes_today}</div><div class="label">Минут фокуса</div></div>
    <div class="stat"><div class="value">${d.lights_on}</div><div class="label">Света включено</div></div>
    <div class="stat"><div class="value">${d.appliances_on}</div><div class="label">Приборов работает</div></div>`;
  const s=await api('/teen/home-status');
  document.getElementById('home-issues').innerHTML=s.issues.length?s.issues.map(i=>`<div class="alert-box"><span>${i.type==='light'?'💡':'🔌'} ${i.name} (${i.room})</span><button class="btn btn-d" onclick="toggleDevice(${i.id||0})">Выключить</button></div>`).join(''):'<p style="color:var(--success);margin-bottom:24px">✅ Все приборы выключены, двери закрыты</p>';
  const tasks=await api('/teen/tasks');
  const completions=await api(`/teen/tasks/completions/${MEMBER_ID}`);
  const todayDone=new Set(completions.filter(c=>new Date(c.completed_at).toDateString()===new Date().toDateString()).map(c=>c.task_id));
  document.getElementById('tasks-list').innerHTML=tasks.map(t=>`<div class="task-item"><div><div style="font-weight:600">${t.name}</div><div style="color:var(--text2);font-size:13px">${t.description}</div><span class="task-cat">${t.category}</span></div><div style="text-align:right"><div style="color:var(--accent);font-weight:600">+${t.points} XP</div>${todayDone.has(t.id)?'<span class="badge badge-s">✅</span>':`<button class="btn btn-s" onclick="completeTask(${t.id})">Выполнить</button>`}</div></div>`).join('');
}

async function completeTask(id){await post(`/teen/tasks/${id}/complete/${MEMBER_ID}`);loadMyHome()}

async function loadLights(){
  const lights=await api('/lights');
  document.getElementById('lights-devices').innerHTML='<div class="dgrid">'+lights.map(l=>`<div class="dcard ${l.is_on?'on':''}"><div class="dhead"><div><div class="dname">${l.name}</div><div class="droom">${l.room}</div></div><button class="tgl ${l.is_on?'on':''}" onclick="toggleDevice(${l.id})"></button></div><div class="slider"><label>Яркость: ${l.state?.brightness||50}%</label><input type="range" min="0" max="100" value="${l.state?.brightness||50}" onchange="updateLight(${l.id},this.value)"></div><div class="color-dots">${['warm','cool','white','red','blue','green'].map(c=>`<div class="color-dot ${l.state?.color===c?'active':''}" style="background:${c==='warm'?'#ff9800':c==='cool'?'#2196f3':c==='white'?'#fff':c}" onclick="setColor(${l.id},'${c}')"></div>`).join('')}</div></div>`).join('')+'</div>';
}

async function showLightTab(tab){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  event.target.classList.add('active');
  if(tab==='devices'){document.getElementById('lights-devices').style.display='';document.getElementById('lights-scenes').style.display='none';loadLights()}
  else{document.getElementById('lights-devices').style.display='none';document.getElementById('lights-scenes').style.display='';loadScenes()}
}

async function loadScenes(){
  const scenes=await api('/lights/scenes');
  document.getElementById('lights-scenes').innerHTML='<div class="dgrid">'+scenes.map(s=>`<div class="dcard" onclick="applyScene('${s.name}')"><div style="font-size:32px;margin-bottom:8px">${s.name==='Кино'?'🎬':s.name==='Утро'?'🌅':s.name==='Ночь'?'🌙':s.name==='Чтение'?'📖':s.name==='Вечеринка'?'🎉':'🌆'}</div><div class="dname">${s.name}</div><div class="droom">${s.brightness}% · ${s.color}</div></div>`).join('')+'</div>';
}

async function applyScene(name){await post(`/lights/scene/${encodeURIComponent(name)}`);loadLights();showLightTab('devices');document.querySelectorAll('.tab')[0].classList.add('active');document.querySelectorAll('.tab')[1].classList.remove('active')}

async function toggleDevice(id){await post(`/devices/${id}/toggle`);refreshCurrent()}
async function updateLight(id,val){await fetch(`${API}/devices/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:{brightness:+val}})})}
async function setColor(id,color){await fetch(`${API}/devices/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({state:{color}})})}

async function loadAppliances(){
  const apps=await api('/appliances');
  document.getElementById('appliances-list').innerHTML='<div class="dgrid">'+apps.map(a=>`<div class="dcard ${a.is_on?'on':''}"><div class="dhead"><div><div class="dname">${a.name}</div><div class="droom">${a.room}</div></div><button class="tgl ${a.is_on?'on':''}" onclick="toggleAppliance(${a.id})"></button></div><div style="color:var(--text2);font-size:13px">⚡ ${a.energy_today} кВт·ч сегодня</div></div>`).join('')+'</div>';
}

async function toggleAppliance(id){await post(`/appliances/${id}/toggle`);loadAppliances()}

async function loadAchievements(){
  const achievements=await api('/achievements');
  const memberAch=await api(`/achievements/member/${MEMBER_ID}`);
  const unlocked=memberAch.filter(m=>m.unlocked_at).length;
  document.getElementById('ach-stats').innerHTML=`
    <div class="stat"><div class="value">${unlocked}</div><div class="label">Разблокировано</div></div>
    <div class="stat"><div class="value">${achievements.length}</div><div class="label">Всего доступно</div></div>
    <div class="stat"><div class="value">${achievements.length-unlocked}</div><div class="label">В процессе</div></div>`;
  document.getElementById('ach-list').innerHTML=achievements.map(a=>{
    const ma=memberAch.find(m=>m.achievement_id===a.id);
    const prog=ma?ma.progress:0;
    const pct=Math.min(100,(prog/a.requirement_value)*100);
    const isUnlocked=ma&&ma.unlocked_at;
    return `<div class="ach-card ${isUnlocked?'unlocked':''}"><div class="ach-icon">${isUnlocked?a.icon:'🔒'}</div><div class="ach-name">${a.name}</div><div class="ach-desc">${a.description}</div><div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div><div style="color:var(--text2);font-size:13px">${prog}/${a.requirement_value}</div></div>`;
  }).join('');
}

async function checkAchievements(){await post(`/achievements/check/${MEMBER_ID}`);loadAchievements()}

async function loadAgreements(){
  const agreements=await api('/agreements');
  document.getElementById('agreements-list').innerHTML=agreements.map(a=>`<div class="agreement-card"><h3>${a.title}</h3><p>${a.description}</p><div style="display:grid;grid-template-columns:1fr 1fr;gap:24px"><div><h4 style="margin-bottom:8px">Правила</h4><ul class="agreement-rules">${a.rules.map(r=>`<li>✅ ${r.rule}</li>`).join('')}</ul></div><div><h4 style="margin-bottom:8px">Награды</h4><ul class="agreement-rewards">${a.rewards.map(r=>`<li>⭐ ${r.reward}</li>`).join('')}</ul></div></div><div style="margin-top:16px;color:var(--text2);font-size:13px">👥 Согласились: ${a.agreed_by.length} чел. ${a.agreed_by.includes(MEMBER_ID)?'· <span style="color:var(--success)">Вы согласны ✅</span>':`· <button class="btn btn-s" style="padding:4px 12px;font-size:12px" onclick="agreeAgreement(${a.id})">Согласиться</button>`}</div></div>`).join('')||'<p class="sub">Нет активных соглашений</p>';
}

async function agreeAgreement(id){await post(`/agreements/${id}/agree/${MEMBER_ID}`);loadAgreements()}

function showNotifForm(){const f=document.getElementById('notif-form');f.style.display=f.style.display==='none'?'':'none'}

async function createNotification(){
  const type=document.getElementById('notif-type').value;
  const channel=document.getElementById('notif-channel').value;
  const message=document.getElementById('notif-message').value;
  if(!message)return;
  await post('/telecom/notifications',{member_id:MEMBER_ID,notification_type:type,channel,message});
  document.getElementById('notif-message').value='';
  showNotifForm();
  loadNotifications();
}

async function loadNotifications(){
  const notifs=await api('/telecom/notifications');
  document.getElementById('notifications-list').innerHTML=notifs.map(n=>`<div class="notif-card ${n.notification_type==='alert'?'danger':n.notification_type==='success'?'success':''}"><div class="notif-header"><span class="badge ${n.is_sent?'badge-s':'badge-w'}">${n.is_sent?'✅ Отправлено':'⏳ Ожидает'}</span><span class="notif-time">${new Date(n.created_at).toLocaleString('ru-RU')}</span></div><div class="notif-msg">[${n.channel.toUpperCase()}] ${n.message}</div>${!n.is_sent?`<button class="btn btn-s" style="margin-top:8px;padding:4px 12px;font-size:12px" onclick="sendNotif(${n.id})">Отправить</button>`:''}</div>`).join('')||'<p class="sub">Нет уведомлений</p>';
}

async function sendNotif(id){await post(`/telecom/notifications/${id}/send`);loadNotifications()}

async function loadCameras(){
  const cameras=await api('/cameras');
  const online=cameras.filter(c=>c.is_online).length;
  const recording=cameras.filter(c=>c.is_recording).length;
  document.getElementById('cameras-stats').innerHTML=`
    <div class="stat"><div class="icon">📹</div><div class="value">${cameras.length}</div><div class="label">Всего камер</div></div>
    <div class="stat"><div class="icon">🟢</div><div class="value">${online}</div><div class="label">Онлайн</div></div>
    <div class="stat"><div class="icon">🔴</div><div class="value">${recording}</div><div class="label">Записывают</div></div>`;
  
  let camerasHtml = '';
  for(const c of cameras){
    // Очистить предыдущий интервал для этой камеры
    if(cameraStreamIntervals[c.id]) {
      clearInterval(cameraStreamIntervals[c.id]);
      delete cameraStreamIntervals[c.id];
    }
    
    const isOnline = c.is_online;
    const streamUrl = c.stream_url;
    
    let previewHtml = '';
    if(isOnline && streamUrl && streamUrl.trim() !== '') {
      previewHtml = `<img id="cam-img-${c.id}" src="${streamUrl}?t=${Date.now()}" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`;
      cameraStreamIntervals[c.id] = setInterval(() => {
        const img = document.getElementById(`cam-img-${c.id}`);
        if(img && document.getElementById(`camera-${c.id}`) && document.getElementById(`camera-${c.id}`).closest('.page.active')) {
          img.src = `${streamUrl}?t=${Date.now()}`;
        }
      }, 500);
    } else if(isOnline && (!streamUrl || streamUrl.trim() === '')) {
      previewHtml = `<div style="display:flex;flex-direction:column;align-items:center;gap:8px"><span style="font-size:48px">📹</span><span style="color:var(--text2)">${c.name}</span><span style="font-size:12px">Нет URL потока</span></div>`;
    } else {
      previewHtml = `<div style="display:flex;flex-direction:column;align-items:center;gap:8px"><span style="font-size:48px;opacity:0.3">📹</span><span style="color:var(--text2)">Оффлайн</span></div>`;
    }
    
    camerasHtml += `
      <div class="dcard ${c.is_online?'on':''}" style="padding:0;overflow:hidden" id="camera-${c.id}">
        <div style="position:relative;background:#0f1117;aspect-ratio:16/9;display:flex;align-items:center;justify-content:center">
          ${previewHtml}
          <div style="position:absolute;top:8px;left:8px;display:flex;gap:6px">
            ${c.is_recording?'<span class="badge badge-d" style="animation:pulse 1.5s infinite">● REC</span>':''}
            <span class="badge ${c.is_online?'badge-s':'badge-d'}">${c.is_online?'ONLINE':'OFFLINE'}</span>
          </div>
          <div style="position:absolute;bottom:8px;left:8px;color:#fff;font-size:13px;background:rgba(0,0,0,0.6);padding:4px 8px;border-radius:4px">📍 ${c.location}</div>
        </div>
        <div style="padding:16px;display:flex;justify-content:space-between;align-items:center">
          <div><div style="font-weight:700">${c.name}</div><div style="color:var(--text2);font-size:13px">${c.location}</div></div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-s" onclick="editCameraStream(${c.id}, '${c.stream_url || ''}')" style="padding:8px 16px;font-size:13px">⚙️ Настроить</button>
            <button class="btn ${c.is_recording?'btn-d':'btn-s'}" onclick="toggleRecording(${c.id})" style="padding:8px 16px;font-size:13px">${c.is_recording?'⏹ Стоп':'▶ Старт'}</button>
            <button class="btn btn-d" onclick="deleteCamera(${c.id}, '${c.name}')" style="padding:8px 16px;font-size:13px">🗑 Удалить</button>
          </div>
        </div>
      </div>`;
  }
  document.getElementById('cameras-grid').innerHTML = camerasHtml || '<p class="sub">Нет камер</p>';
}

async function toggleRecording(id){await post(`/cameras/${id}/toggle-recording`);loadCameras()}

async function editCameraStream(cameraId, currentStreamUrl) {
  const newUrl = prompt('Введите URL видеопотока (MJPEG или другое):', currentStreamUrl);
  if (newUrl !== null && newUrl !== currentStreamUrl) {
    try {
      await fetch(`${API}/cameras/${cameraId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_url: newUrl, is_online: true })
      });
      loadCameras();
    } catch(e) {
      alert('Ошибка сохранения URL: ' + e.message);
    }
  }
}

function showAddCameraForm(){document.getElementById('add-camera-form').style.display='block'}
function hideAddCameraForm(){document.getElementById('add-camera-form').style.display='none';document.getElementById('new-cam-name').value='';document.getElementById('new-cam-location').value='';document.getElementById('new-cam-url').value=''}

async function addCamera(){
  const name=document.getElementById('new-cam-name').value.trim();
  const location=document.getElementById('new-cam-location').value.trim();
  const streamUrl=document.getElementById('new-cam-url').value.trim();
  const isRecording=document.getElementById('new-cam-recording').checked;
  const isOnline=document.getElementById('new-cam-online').checked;
  if(!name){alert('Введите название камеры');return}
  if(!location){alert('Введите расположение камеры');return}
  try{
    await fetch(`${API}/cameras`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,location,stream_url:streamUrl,is_recording:isRecording,is_online:isOnline})
    });
    hideAddCameraForm();
    loadCameras();
  }catch(e){
    alert('Ошибка добавления камеры: '+e.message);
  }
}

async function deleteCamera(id,name){
  if(!confirm(`Удалить камеру "${name}"?`))return;
  try{
    await fetch(`${API}/cameras/${id}`,{method:'DELETE'});
    cameraStreamIntervals[id]&&clearInterval(cameraStreamIntervals[id]);
    delete cameraStreamIntervals[id];
    loadCameras();
  }catch(e){
    alert('Ошибка удаления камеры: '+e.message);
  }
}

async function loadEvents(){
  const events=await api('/events');
  document.getElementById('events-list').innerHTML=events.map(e=>`<div class="eitem"><div><div style="font-weight:500">${e.message}</div><div class="etime">${e.event_type}</div></div><div class="etime">${new Date(e.timestamp).toLocaleString('ru-RU')}</div></div>`).join('')||'<p class="sub">Нет событий</p>';
}

async function loadEvening(){
  const routines=await api(`/teen/evening-routine/${MEMBER_ID}`);
  if(!routines.length){document.getElementById('routine-steps').innerHTML='<p class="sub">Нет проверок</p>';return}
  const r=routines[0];
  document.getElementById('routine-status').innerHTML=`<div class="stat" style="margin-bottom:24px"><div class="label">${r.name}</div><div class="value">${r.completed_at?'✅ Завершён':r.is_active?`Шаг ${r.current_step+1}/${r.steps.length}`:'Не начат'}</div><div class="progress-bar" style="margin-top:12px"><div class="progress-fill" style="width:${r.steps.length?(r.current_step/r.steps.length)*100:0}%"></div></div></div>`;
  document.getElementById('routine-steps').innerHTML=r.steps.map((s,i)=>{
    const done=r.completed_at||(r.current_step>i);
    const current=r.is_active&&i===r.current_step&&!r.completed_at;
    return `<div class="task-item" style="${current?'border:2px solid var(--accent)':''}"><div style="display:flex;align-items:center;gap:12px"><span style="font-size:24px">${s.icon==='book'?'📚':s.icon==='lightbulb'?'💡':s.icon==='power'?'🔌':s.icon==='door'?'🚪':'🌙'}</span><div><div style="font-weight:600">${s.name}</div><div style="color:var(--text2);font-size:13px">${s.action}</div></div></div>${done?'<span class="badge badge-s">✅</span>':current?`<button class="btn btn-s" onclick="nextStep(${r.id})">Далее →</button>`:'<span style="color:var(--text2)">⏳</span>'}</div>`;
  }).join('');
  if(!r.is_active&&!r.completed_at){
    document.getElementById('routine-steps').innerHTML+=`<button class="btn btn-p" style="margin-top:16px" onclick="startRoutine(${r.id})">🌙 Начать проверку</button>`;
  }
}

async function startRoutine(id){await post(`/teen/evening-routine/${id}/start`);loadEvening()}
async function nextStep(id){await post(`/teen/evening-routine/${id}/next-step`);loadEvening()}

async function startFocus(){
  const subject=document.getElementById('focus-subject').value;
  const duration=+document.getElementById('focus-duration').value;
  await post('/teen/focus/start',{member_id:MEMBER_ID,planned_duration:duration,subject});
  document.getElementById('focus-active').style.display='block';
  document.getElementById('focus-subject-display').textContent=subject;
  focusStart=Date.now();
  const totalMs=duration*60*1000;
  focusInterval=setInterval(()=>{
    const elapsed=Date.now()-focusStart;
    const remaining=Math.max(0,totalMs-elapsed);
    const m=Math.floor(remaining/60000);
    const s=Math.floor((remaining%60000)/1000);
    document.getElementById('focus-timer').textContent=`${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
    if(remaining<=0){clearInterval(focusInterval);endFocus(true)}
  },1000);
}

async function endFocus(completed){
  clearInterval(focusInterval);
  const sessions=await api(`/teen/focus/${MEMBER_ID}`);
  if(sessions.length)await post(`/teen/focus/${sessions[0].id}/end?completed=${completed}`);
  document.getElementById('focus-active').style.display='none';
  loadFocusHistory();
}

async function loadFocusHistory(){
  const sessions=await api(`/teen/focus/${MEMBER_ID}`);
  const totalMin=sessions.reduce((a,s)=>a+s.actual_duration,0);
  document.getElementById('focus-history').innerHTML=`<div class="grid"><div class="stat"><div class="value">${sessions.length}</div><div class="label">Сессий</div></div><div class="stat"><div class="value">${totalMin}</div><div class="label">Минут всего</div></div></div>`;
}

function refreshCurrent(){
  const active=document.querySelector('.page.active');
  if(active){
    const id=active.id;
    if(id==='dashboard')loadDashboard();
    if(id==='myhome')loadMyHome();
    if(id==='lights')loadLights();
    if(id==='appliances')loadAppliances();
    if(id==='cameras')loadCameras();
  }
}

// Voice Assistant
let recognition=null, isListening=false, voiceHistory=[];
let devicesCache=null, appliancesCache=null;

function initVoice(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!SR){
    document.getElementById('voice-status').textContent='Голосовое распознавание не поддерживается в этом браузере';
    document.getElementById('voice-btn').style.opacity='0.5';
    document.getElementById('voice-btn').style.cursor='not-allowed';
    return;
  }
  recognition=new SR();
  recognition.lang='ru-RU';
  recognition.continuous=false;
  recognition.interimResults=true;
  recognition.onstart=()=>{
    isListening=true;
    document.getElementById('voice-status').textContent='Слушаю...';
    document.getElementById('voice-wave').style.display='block';
    document.getElementById('voice-btn').style.background='#ef5350';
    document.getElementById('voice-btn').style.boxShadow='0 4px 20px rgba(239,83,80,0.4)';
  };
  recognition.onresult=(e)=>{
    let interim='',final='';
    for(let i=e.resultIndex;i<e.results.length;i++){
      if(e.results[i].isFinal)final+=e.results[i][0].transcript;
      else interim+=e.results[i][0].transcript;
    }
    document.getElementById('voice-text').textContent=final||interim;
  };
  recognition.onend=()=>{
    isListening=false;
    document.getElementById('voice-wave').style.display='none';
    document.getElementById('voice-btn').style.background='#FF8820';
    document.getElementById('voice-btn').style.boxShadow='0 4px 20px rgba(255,136,32,0.4)';
    const text=document.getElementById('voice-text').textContent;
    if(text){
      document.getElementById('voice-status').textContent='Обрабатываю...';
      processVoiceCommand(text);
    }else{
      document.getElementById('voice-status').textContent='Не расслышала. Попробуйте ещё раз';
    }
  };
  recognition.onerror=(e)=>{
    isListening=false;
    document.getElementById('voice-wave').style.display='none';
    document.getElementById('voice-btn').style.background='#FF8820';
    document.getElementById('voice-btn').style.boxShadow='0 4px 20px rgba(255,136,32,0.4)';
    document.getElementById('voice-status').textContent='Ошибка: '+e.error;
  };
}

function toggleVoice(){
  if(!recognition){initVoice();if(!recognition)return}
  if(isListening){recognition.stop();return}
  document.getElementById('voice-text').textContent='';
  document.getElementById('voice-result').textContent='';
  recognition.start();
}

async function cacheDevices(){
  if(!devicesCache)devicesCache=await api('/devices');
  if(!appliancesCache)appliancesCache=await api('/appliances');
}

function findDeviceByName(text,devices){
  const t=text.toLowerCase();
  for(const d of devices){
    const name=d.name.toLowerCase();
    if(t.includes(name))return d;
    const words=name.split(' ');
    for(const w of words){
      if(w.length>3&&t.includes(w))return d;
    }
  }
  return null;
}

function speak(text){
  const u=new SpeechSynthesisUtterance(text);
  u.lang='ru-RU';
  u.rate=1;
  speechSynthesis.speak(u);
}

function addVoiceHistory(text,response,success){
  voiceHistory.unshift({text,response,success,time:new Date().toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'})});
  if(voiceHistory.length>10)voiceHistory.pop();
  const el=document.getElementById('voice-history');
  el.innerHTML=voiceHistory.map(h=>`<div class="notif-card ${h.success?'success':'danger'}" style="margin-bottom:8px"><div style="font-weight:600;font-size:14px">🎙 ${h.text}</div><div class="notif-msg">${h.response}</div><div class="notif-time">${h.time}</div></div>`).join('');
}

async function processVoiceCommand(text){
  const t=text.toLowerCase().trim();
  await cacheDevices();
  let response='',success=false;

  // Включить/выключить свет
  if(t.includes('включ')&&t.includes('свет')){
    const room=extractRoom(t);
    if(room){
      const dev=(devicesCache||[]).find(d=>d.device_type==='light'&&d.room.toLowerCase().includes(room));
      if(dev&&!dev.is_on){await post(`/devices/${dev.id}/toggle`);response=`Свет в ${dev.room} включён`;success=true}
      else if(dev){response=`Свет в ${dev.room} уже включён`;success=true}
      else{response=`Не нашла свет в комнате ${room}`}
    }else{
      const lights=(devicesCache||[]).filter(d=>d.device_type==='light'&&!d.is_on);
      for(const l of lights.slice(0,3))await post(`/devices/${l.id}/toggle`);
      response=`Включила ${lights.length>0?lights.length:'весь'} свет`;success=true;
    }
  }
  else if(t.includes('выключ')&&t.includes('свет')){
    const room=extractRoom(t);
    if(room){
      const dev=(devicesCache||[]).find(d=>d.device_type==='light'&&d.room.toLowerCase().includes(room));
      if(dev&&dev.is_on){await post(`/devices/${dev.id}/toggle`);response=`Свет в ${dev.room} выключен`;success=true}
      else if(dev){response=`Свет в ${dev.room} уже выключен`;success=true}
      else{response=`Не нашла свет в комнате ${room}`}
    }else{
      const lights=(devicesCache||[]).filter(d=>d.device_type==='light'&&d.is_on);
      for(const l of lights.slice(0,5))await post(`/devices/${l.id}/toggle`);
      response=`Выключила ${lights.length>0?lights.length:'весь'} свет`;success=true;
    }
  }
  // Сцены
  else if(t.includes('сцен')&&t.includes('кино')){
    await post('/lights/scene/Кино');response='Сцена "Кино" применена';success=true;
  }
  else if(t.includes('сцен')&&t.includes('вечер')){
    await post('/lights/scene/Вечер');response='Сцена "Вечер" применена';success=true;
  }
  else if(t.includes('сцен')&&t.includes('утр')){
    await post('/lights/scene/Утро');response='Сцена "Утро" применена';success=true;
  }
  else if(t.includes('сцен')&&t.includes('ночн')){
    await post('/lights/scene/Ночь');response='Сцена "Ночь" применена';success=true;
  }
  else if(t.includes('сцен')&&t.includes('чтен')){
    await post('/lights/scene/Чтение');response='Сцена "Чтение" применена';success=true;
  }
  // Ночной режим
  else if(t.includes('ночн')&&t.includes('режим')){
    await post('/lights/scene/Ночь');response='Ночной режим активирован';success=true;
  }
  // Включить/выключить технику
  else if(t.includes('включ')&&(t.includes('телеvisor')||t.includes('телевизор'))){
    const tv=(appliancesCache||[]).find(a=>a.appliance_type==='tv');
    if(tv){await post(`/appliances/${tv.id}/toggle`);response=`Телевизор включён`;success=true}
    else{response='Телевизор не найден'}
  }
  else if(t.includes('выключ')&&(t.includes('телеvisor')||t.includes('телевизор'))){
    const tv=(appliancesCache||[]).find(a=>a.appliance_type==='tv');
    if(tv){await post(`/appliances/${tv.id}/toggle`);response=`Телевизор выключен`;success=true}
    else{response='Телевизор не найден'}
  }
  else if(t.includes('выключ')&&t.includes('техник')){
    const apps=(appliancesCache||[]).filter(a=>a.is_on);
    for(const a of apps)await post(`/appliances/${a.id}/toggle`);
    response=`Выключила ${apps.length} прибор(ов)`;success=true;
  }
  else if(t.includes('включ')&&t.includes('техник')){
    const apps=(appliancesCache||[]).filter(a=>!a.is_on);
    for(const a of apps.slice(0,3))await post(`/appliances/${a.id}/toggle`);
    response=`Включила ${apps.length>0?apps.length:''} прибор(ов)`;success=true;
  }
  // Статус дома
  else if(t.includes('статус')&&t.includes('дом')){
    const s=await api('/teen/home-status');
    if(s.all_clear)response='Всё в порядке! Все приборы выключены, двери закрыты';
    else response=`Внимание: ${s.lights_on} свет(а) и ${s.appliances_on} прибор(ов) включено`;
    success=true;
  }
  // Камеры
  else if(t.includes('камер')){
    showPage('cameras');
    document.querySelectorAll('.nav').forEach(n=>{if(n.textContent.includes('Камеры'))n.classList.add('active')});
    response='Открываю камеры';success=true;
  }
  // Фокус
  else if(t.includes('начать')&&t.includes('фокус')){
    showPage('focus');
    document.querySelectorAll('.nav').forEach(n=>{if(n.textContent.includes('Фокус'))n.classList.add('active')});
    response='Открываю фокус-режим';success=true;
  }
  // Задачи
  else if(t.includes('задач')||t.includes('мои задач')){
    const tasks=await api('/teen/tasks');
    const completions=await api(`/teen/tasks/completions/${MEMBER_ID}`);
    const todayDone=completions.filter(c=>new Date(c.completed_at).toDateString()===new Date().toDateString()).length;
    response=`У тебя ${tasks.length} задач, сегодня выполнено ${todayDone}`;success=true;
  }
  else if(t.includes('привет')||t.includes('здравствуй')){
    response='Привет! Чем могу помочь?';success=true;
  }
  else if(t.includes('спасибо')){
    response='Всегда пожалуйста!';success=true;
  }
  else{
    response='Не поняла команду. Попробуйте: "включи свет", "статус дома", "ночной режим"';
  }

  document.getElementById('voice-status').textContent=success?'Выполнено!':'Готово';
  document.getElementById('voice-result').textContent=response;
  addVoiceHistory(text,response,success);
  if(success)speak(response);
  devicesCache=null;appliancesCache=null;
}

function extractRoom(text){
  const rooms=['гостиная','спальня','кухня','прихожая','детская','ванная','коридор'];
  const t=text.toLowerCase();
  for(const r of rooms){if(t.includes(r))return r}
  return null;
}

// Init
loadDashboard();
setInterval(()=>{const a=document.querySelector('.page.active');if(a&&a.id==='dashboard')loadDashboard()},30000);
initVoice();
</script>
</body>
</html>"""
