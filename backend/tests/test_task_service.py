import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db.models import User, PlanTask
from app.services.task_service import TaskService
from app.repositories.task_repo import TaskRepository
from app.repositories.version_repo import VersionRepository


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def task_service(session):
    return TaskService(session)


@pytest.fixture
def test_user(session):
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_task(session, test_user):
    task = PlanTask(
        user_id=test_user.id,
        status="pending",
        progress=0,
        error_message=None,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


class TestTaskService:
    def test_get_status_success(self, task_service, test_user, test_task):
        result = task_service.get_status(test_task.id, test_user)
        assert result.id == test_task.id
        assert result.status == test_task.status

    def test_get_status_not_found(self, task_service, test_user):
        with pytest.raises(HTTPException) as exc_info:
            task_service.get_status(999, test_user)
        assert exc_info.value.status_code == 404

    def test_get_status_wrong_user(self, task_service, session, test_user):
        other_user = User(username="other", email="other@example.com", password_hash="hashed")
        session.add(other_user)
        session.commit()
        session.refresh(other_user)
        
        task = PlanTask(user_id=other_user.id, status="pending", progress=0)
        session.add(task)
        session.commit()
        
        with pytest.raises(HTTPException) as exc_info:
            task_service.get_status(task.id, test_user)
        assert exc_info.value.status_code == 404

    def test_get_logs_pending_status(self, task_service, test_user, test_task):
        test_task.status = "pending"
        result = task_service.get_logs(test_task.id, test_user)
        assert result.task_id == test_task.id
        assert result.status == "pending"
        assert len(result.logs) == 5
        # First step should be success, rest waiting
        assert result.logs[0].status == "success"
        assert result.logs[1].status == "running"
        assert all(log.status == "waiting" for log in result.logs[2:])

    def test_get_logs_running_early_stage(self, task_service, test_user, test_task):
        test_task.status = "running"
        test_task.progress = 5
        result = task_service.get_logs(test_task.id, test_user)
        assert result.logs[0].status == "success"
        assert result.logs[1].status == "running"
        assert all(log.status == "waiting" for log in result.logs[2:])

    def test_get_logs_running_mid_stage(self, task_service, test_user, test_task):
        test_task.status = "running"
        test_task.progress = 50
        result = task_service.get_logs(test_task.id, test_user)
        assert result.logs[0].status == "success"
        assert result.logs[1].status == "success"
        assert result.logs[2].status == "running"
        assert all(log.status == "waiting" for log in result.logs[3:])

    def test_get_logs_running_late_stage(self, task_service, test_user, test_task):
        test_task.status = "running"
        test_task.progress = 80
        result = task_service.get_logs(test_task.id, test_user)
        assert result.logs[0].status == "success"
        assert result.logs[1].status == "success"
        assert result.logs[2].status == "success"
        assert result.logs[3].status == "running"
        assert result.logs[4].status == "waiting"

    def test_get_logs_running_final_stage(self, task_service, test_user, test_task):
        test_task.status = "running"
        test_task.progress = 95
        result = task_service.get_logs(test_task.id, test_user)
        assert all(log.status == "success" for log in result.logs[:4])
        assert result.logs[4].status == "running"

    def test_get_logs_success_status(self, task_service, test_user, test_task):
        test_task.status = "success"
        test_task.progress = 100
        result = task_service.get_logs(test_task.id, test_user)
        assert all(log.status == "success" for log in result.logs)

    def test_get_logs_failed_status(self, task_service, test_user, test_task):
        test_task.status = "failed"
        test_task.error_message = "Something went wrong"
        result = task_service.get_logs(test_task.id, test_user)
        assert result.logs[0].status == "success"
        assert result.logs[1].status == "success"
        assert result.logs[2].status == "success"
        assert result.logs[3].status == "failed"
        assert result.logs[4].status == "failed"
        assert "Something went wrong" in result.logs[4].message

    def test_get_logs_not_found(self, task_service, test_user):
        with pytest.raises(HTTPException) as exc_info:
            task_service.get_logs(999, test_user)
        assert exc_info.value.status_code == 404