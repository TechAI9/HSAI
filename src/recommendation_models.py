"""Immutable evidence and action protocol shared across pipeline layers."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ActionKind(str, Enum):
    MULLIGAN = "mulligan"
    PLAY_CARD = "play_card"
    TRADE_CARD = "trade_card"
    USE_HERO_POWER = "use_hero_power"
    ATTACK = "attack"
    USE_LOCATION = "use_location"
    LAUNCH_STARSHIP = "launch_starship"
    CHOOSE_DISCOVER = "choose_discover"
    END_TURN = "end_turn"
    TIMELINE_UNDO = "timeline_undo"
    TIMELINE_KEEP = "timeline_keep"


@dataclass(frozen=True)
class SlotRef:
    kind: str
    owner: Optional[str] = None
    index: Optional[int] = None


@dataclass(frozen=True)
class FrameEvidence:
    frame_id: str
    captured_at: float
    desktop_size: tuple[int, int]
    dpi: int
    window_handle: int
    foreground: bool
    recommendation_roi: tuple[int, int, int, int]
    exact_hash: str
    perceptual_hash: str
    panel_visible: bool
    pixels: Any = None


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    box: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class OcrEvidence:
    frame_id: str
    created_at: float
    lines: tuple[OcrLine, ...]
    normalized_text: str
    confidence: float
    backend: str
    preprocessing: str


@dataclass(frozen=True)
class ProposedAction:
    action_id: str
    frame_id: str
    created_at: float
    turn_number: int
    log_revision: int
    raw_instruction: str
    normalized_instruction: str
    action: ActionKind
    source: Optional[SlotRef] = None
    destination: Optional[SlotRef] = None
    target: Optional[SlotRef] = None
    mulligan_slots: tuple[int, ...] = ()
    card_type: Optional[str] = None
    ocr_confidence: float = 0.0
    semantic_confidence: float = 0.0
    choice_name: Optional[str] = None
    # 动作消耗的法力。盒子推荐面板不写费用（上游删掉了这个字段），但本地卡组
    # 策略搜索出来的动作要带上它——搜索用它做剩余法力剪枝，日志也靠它显示。
    # 默认 0，所以上游那套只读盒子的代码不受影响。
    cost: int = 0
    # 真实面板在目标行后面还会打印一行「目标卡名」（不带前缀，会被
    # normalize_action_text 过滤掉），单独留一份给「手牌/场面两可」的目标判定用。
    target_name: Optional[str] = None
    # Local search identities let execution avoid repeating an action that
    # failed twice, while keeping equal-card copies distinct by entity ID.
    entity_id: Optional[str] = None
    target_entity_id: Optional[str] = None


@dataclass(frozen=True)
class ValidationResult:
    accepted: bool
    code: str
    diagnostics: tuple[str, ...] = ()
    value: Any = None

    @classmethod
    def allow(cls, value: Any) -> "ValidationResult":
        return cls(True, "accepted", value=value)

    @classmethod
    def reject(cls, code: str, *diagnostics: str) -> "ValidationResult":
        return cls(False, code, diagnostics)
