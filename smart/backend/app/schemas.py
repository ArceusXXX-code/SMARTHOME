from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class DeviceResponse(BaseModel):
    id: int
    name: str
    device_type: str
    room: str
    is_on: bool
    state: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceUpdate(BaseModel):
    is_on: Optional[bool] = None
    state: Optional[Dict[str, Any]] = None


class SensorReadingResponse(BaseModel):
    id: int
    device_id: int
    sensor_type: str
    value: float
    unit: str
    timestamp: datetime

    class Config:
        from_attributes = True


class EventLogResponse(BaseModel):
    id: int
    event_type: str
    device_id: Optional[int]
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class FamilyMemberResponse(BaseModel):
    id: int
    name: str
    role: str
    avatar_color: str
    is_active: bool

    class Config:
        from_attributes = True


class ResponsibilityTaskResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    points: int
    is_recurring: bool
    is_active: bool

    class Config:
        from_attributes = True


class TaskCompletionResponse(BaseModel):
    id: int
    member_id: int
    task_id: int
    completed_at: datetime
    points_earned: int

    class Config:
        from_attributes = True


class FocusSessionCreate(BaseModel):
    member_id: int
    planned_duration: int = 25
    subject: str = ""


class FocusSessionResponse(BaseModel):
    id: int
    member_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    planned_duration: int
    actual_duration: int
    subject: str
    completed: bool

    class Config:
        from_attributes = True


class EveningRoutineResponse(BaseModel):
    id: int
    member_id: int
    name: str
    start_time: str
    steps: list
    is_active: bool
    current_step: int
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TeenDashboard(BaseModel):
    total_points: int
    level: int
    level_name: str
    points_to_next: int
    tasks_today: int
    tasks_completed_today: int
    streak_days: int
    focus_sessions_today: int
    focus_minutes_today: int
    home_status: str
    lights_on: int
    appliances_on: int


class AchievementResponse(BaseModel):
    id: int
    name: str
    description: str
    icon: str
    category: str
    requirement_type: str
    requirement_value: int

    class Config:
        from_attributes = True


class MemberAchievementResponse(BaseModel):
    id: int
    member_id: int
    achievement_id: int
    unlocked_at: Optional[datetime]
    progress: int
    achievement: AchievementResponse

    class Config:
        from_attributes = True


class FamilyAgreementResponse(BaseModel):
    id: int
    title: str
    description: str
    rules: List[Dict[str, Any]]
    rewards: List[Dict[str, Any]]
    created_by: int
    agreed_by: List[int]
    is_active: bool

    class Config:
        from_attributes = True


class TelecomNotificationCreate(BaseModel):
    member_id: Optional[int] = None
    notification_type: str
    channel: str = "push"
    message: str


class TelecomNotificationResponse(BaseModel):
    id: int
    member_id: Optional[int]
    notification_type: str
    channel: str
    message: str
    is_sent: bool
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApplianceResponse(BaseModel):
    id: int
    name: str
    appliance_type: str
    room: str
    is_on: bool
    state: Dict[str, Any]
    energy_today: float

    class Config:
        from_attributes = True


class LightScene(BaseModel):
    name: str
    brightness: int
    color: str


class HomeStatus(BaseModel):
    all_clear: bool
    lights_on: int
    appliances_on: int
    issues: List[Dict[str, str]]


class CameraCreate(BaseModel):
    name: str
    location: str
    stream_url: str = ""
    snapshot_url: str = ""
    is_recording: bool = True
    is_online: bool = True


class CameraResponse(BaseModel):
    id: int
    name: str
    location: str
    stream_url: str
    snapshot_url: str
    is_recording: bool
    is_online: bool
    created_at: datetime

    class Config:
        from_attributes = True
