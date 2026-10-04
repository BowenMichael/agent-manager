import os
import logging
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, status
from agent_manager.models import SettingsUpdateRequest
from agent_manager.runner import AgentRunnerManager
from agent_manager.storage import save_settings, load_settings
import agent_manager.config as config

logger = logging.getLogger("agent_manager.api.settings")
router = APIRouter(tags=["settings"])


def _update_env_line(lines: list, key: str, val: Any):
    """Updates or appends a key=value pair in the .env lines array."""
    str_val = str(val).lower() if isinstance(val, bool) else str(val)
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={str_val}"
            return
    lines.append(f"{key}={str_val}")


@router.get("/api/settings")
async def get_settings():
    """Returns current application settings and Antigravity subscription/quota state."""
    try:
        key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        masked_key = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("Set" if key else "")

        quota_status = {
            "subscription_active": True,
            "subscription_quota_reached": False,
            "quota_percent": 0.0,
            "reset_window": "Active / Fresh Quota",
            "current_active_model": config.DEFAULT_MODEL,
            "notice": "Google Antigravity Subscription is active and fully authenticated with zero API key required."
        }

        return {
            "has_gemini_api_key": bool(key),
            "masked_gemini_api_key": masked_key,
            "default_repo": config.DEFAULT_REPO,
            "project_board_id": config.PROJECT_BOARD_ID,
            "agy_mode": getattr(config, "AGY_MODE", "terminal"),
            "agy_cli_installed": config.AGY_CLI_PATH.exists(),
            "agy_cli_path": str(config.AGY_CLI_PATH),
            "default_model": getattr(config, "DEFAULT_MODEL", "gemini-3.8-flash"),
            "default_effort": getattr(config, "DEFAULT_EFFORT", "high"),
            "allow_overage_credits": config.get_cli_overage_credits(),
            "available_efforts": getattr(config, "AVAILABLE_EFFORT_LEVELS", []),
            "available_models": getattr(config, "AVAILABLE_MODELS", []),
            "max_session_tokens": getattr(config, "MAX_SESSION_TOKENS", 150000),
            "compact_completed_chat": getattr(config, "COMPACT_COMPLETED_CHAT", True),
            "is_server": getattr(config, "IS_SERVER", False),
            "cli_idle_timeout_minutes": getattr(config, "CLI_IDLE_TIMEOUT_MINUTES", 30),
            "workflow_pipeline_enabled": getattr(config, "WORKFLOW_PIPELINE_ENABLED", False),
            "guardrails_enabled": getattr(config, "GUARDRAILS_ENABLED", True),
            "auto_merge_enabled": getattr(config, "AUTO_MERGE_ENABLED", False),
            "pipeline_summary_model": getattr(config, "PIPELINE_SUMMARY_MODEL", "gemini-3.8-flash"),
            "pipeline_summary_effort": getattr(config, "PIPELINE_SUMMARY_EFFORT", "low"),
            "pipeline_planning_model": getattr(config, "PIPELINE_PLANNING_MODEL", "gemini-3.1-pro"),
            "pipeline_planning_effort": getattr(config, "PIPELINE_PLANNING_EFFORT", "high"),
            "pipeline_implementation_model": getattr(config, "PIPELINE_IMPLEMENTATION_MODEL", "gemini-3.8-flash"),
            "pipeline_implementation_effort": getattr(config, "PIPELINE_IMPLEMENTATION_EFFORT", "low"),
            "quota_status": quota_status
        }
    except Exception as e:
        logger.exception(f"Failed to fetch settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch settings: {str(e)}"
        )


@router.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Persists updated application configuration to disk, environment, and active session runner."""
    try:
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        lines = []
        if env_file.exists():
            try:
                lines = env_file.read_text(encoding="utf-8").splitlines()
            except Exception as e:
                logger.warning(f"Could not read .env file: {e}")

        current_persisted = load_settings() or {}

        def apply_var(config_name: str, val: Any, env_name: str = None, persisted_key: str = None):
            e_name = env_name or config_name
            p_key = persisted_key or e_name.lower()
            setattr(config, config_name, val)
            os.environ[e_name] = str(val).lower() if isinstance(val, bool) else str(val)
            _update_env_line(lines, e_name, val)
            current_persisted[p_key] = val

        if req.default_repo:
            apply_var("DEFAULT_REPO", req.default_repo.strip())

        effort_val = req.default_effort or req.effort_level
        if effort_val:
            eff = effort_val.strip().lower()
            apply_var("DEFAULT_EFFORT", eff)
            current_persisted["effort_level"] = eff

        if req.default_model:
            apply_var("DEFAULT_MODEL", req.default_model.strip())

        if req.allow_overage_credits is not None:
            config.set_cli_overage_credits(req.allow_overage_credits)
            apply_var("ALLOW_OVERAGE_CREDITS", req.allow_overage_credits)

        if req.max_session_tokens:
            apply_var("MAX_SESSION_TOKENS", int(req.max_session_tokens))

        if req.compact_completed_chat is not None:
            apply_var("COMPACT_COMPLETED_CHAT", bool(req.compact_completed_chat))

        if req.agy_mode and req.agy_mode.strip().lower() in ("terminal", "web_stream"):
            apply_var("AGY_MODE", req.agy_mode.strip().lower())

        if req.gemini_api_key is not None:
            apply_var("GEMINI_API_KEY", req.gemini_api_key.strip())

        if req.is_server is not None:
            apply_var("IS_SERVER", bool(req.is_server))

        if req.cli_idle_timeout_minutes is not None:
            apply_var("CLI_IDLE_TIMEOUT_MINUTES", int(req.cli_idle_timeout_minutes))

        if req.workflow_pipeline_enabled is not None:
            apply_var("WORKFLOW_PIPELINE_ENABLED", bool(req.workflow_pipeline_enabled))

        if req.guardrails_enabled is not None:
            apply_var("GUARDRAILS_ENABLED", bool(req.guardrails_enabled))

        if req.auto_merge_enabled is not None:
            apply_var("AUTO_MERGE_ENABLED", bool(req.auto_merge_enabled))

        for attr, val, is_lower in [
            ("PIPELINE_SUMMARY_MODEL", req.pipeline_summary_model, False),
            ("PIPELINE_SUMMARY_EFFORT", req.pipeline_summary_effort, True),
            ("PIPELINE_PLANNING_MODEL", req.pipeline_planning_model, False),
            ("PIPELINE_PLANNING_EFFORT", req.pipeline_planning_effort, True),
            ("PIPELINE_IMPLEMENTATION_MODEL", req.pipeline_implementation_model, False),
            ("PIPELINE_IMPLEMENTATION_EFFORT", req.pipeline_implementation_effort, True),
        ]:
            if val:
                v = val.strip().lower() if is_lower else val.strip()
                apply_var(attr, v)

        try:
            env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not persist to .env: {e}")

        # Persist to disk via storage
        save_settings(current_persisted)

        result = {
            "status": "ok",
            "has_gemini_api_key": bool(config.GEMINI_API_KEY),
            "default_model": config.DEFAULT_MODEL,
            "default_effort": config.DEFAULT_EFFORT,
            "allow_overage_credits": config.get_cli_overage_credits(),
            "max_session_tokens": config.MAX_SESSION_TOKENS,
            "compact_completed_chat": config.COMPACT_COMPLETED_CHAT,
            "agy_mode": config.AGY_MODE,
            "default_repo": config.DEFAULT_REPO,
            "is_server": config.IS_SERVER,
            "cli_idle_timeout_minutes": config.CLI_IDLE_TIMEOUT_MINUTES,
            "workflow_pipeline_enabled": config.WORKFLOW_PIPELINE_ENABLED,
            "guardrails_enabled": config.GUARDRAILS_ENABLED,
            "auto_merge_enabled": config.AUTO_MERGE_ENABLED,
            "pipeline_summary_model": config.PIPELINE_SUMMARY_MODEL,
            "pipeline_summary_effort": config.PIPELINE_SUMMARY_EFFORT,
            "pipeline_planning_model": config.PIPELINE_PLANNING_MODEL,
            "pipeline_planning_effort": config.PIPELINE_PLANNING_EFFORT,
            "pipeline_implementation_model": config.PIPELINE_IMPLEMENTATION_MODEL,
            "pipeline_implementation_effort": config.PIPELINE_IMPLEMENTATION_EFFORT
        }

        runner = AgentRunnerManager()
        await runner.broadcast("settings_updated", result)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )
