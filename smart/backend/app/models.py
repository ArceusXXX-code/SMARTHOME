from app.database import Base
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    JSON,
)
from datetime import datetime


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    device_type = Column(String)
    room = Column(String)
    is_on = Column(Boolean, default=False)
    state = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    sensor_type = Column(String)
    value = Column(Float)
    unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class FamilyMember(Base):
    __tablename__ = "family_members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    role = Column(String, default="teen")
    avatar_color = Column(String, default="#4fc3f7")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResponsibilityTask(Base):
    __tablename__ = "responsibility_tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, default="")
    category = Column(String, default="general")
    points = Column(Integer, default=10)
    is_recurring = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family_members.id"))
    task_id = Column(Integer, ForeignKey("responsibility_tasks.id"))
    completed_at = Column(DateTime, default=datetime.utcnow)
    points_earned = Column(Integer, default=0)


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family_members.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    planned_duration = Column(Integer, default=25)
    actual_duration = Column(Integer, default=0)
    subject = Column(String, default="")
    completed = Column(Boolean, default=False)


class EveningRoutine(Base):
    __tablename__ = "evening_routines"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family_members.id"))
    name = Column(String, default="Вечерний ритуал")
    start_time = Column(String, default="21:00")
    steps = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    current_step = Column(Integer, default=0)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, default="")
    icon = Column(String, default="🏆")
    category = Column(String, default="general")
    requirement_type = Column(String)
    requirement_value = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MemberAchievement(Base):
    __tablename__ = "member_achievements"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family_members.id"))
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    unlocked_at = Column(DateTime, nullable=True)
    progress = Column(Integer, default=0)


class FamilyAgreement(Base):
    __tablename__ = "family_agreements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String, default="")
    rules = Column(JSON, default=list)
    rewards = Column(JSON, default=list)
    created_by = Column(Integer, ForeignKey("family_members.id"))
    agreed_by = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class TelecomNotification(Base):
    __tablename__ = "telecom_notifications"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family_members.id"), nullable=True)
    notification_type = Column(String)
    channel = Column(String, default="push")
    message = Column(String)
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Appliance(Base):
    __tablename__ = "appliances"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    appliance_type = Column(String)
    room = Column(String)
    is_on = Column(Boolean, default=False)
    state = Column(JSON, default=dict)
    energy_today = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    stream_url = Column(String, default="")
    snapshot_url = Column(String, default="")
    is_recording = Column(Boolean, default=True)
    is_online = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
