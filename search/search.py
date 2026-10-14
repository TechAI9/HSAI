"""Priority-queue search over simple minion attacks and minion plays.

本文件是搜索模块的唯一对外入口，内外两套数据结构在此分界：

    * 对外（执行层，如 src/flow/recommendation_flow.py）：
      Search.search(StrategyState, cost) -> (list[ProposedAction], score)
      参数与返回值仍是执行层的旧协议，调用方一行都不用改。
    * 对内（搜索过程）：aiSearch / getActions / doAction / rankState 全部只吃
      精简的 AiState / AiAction，搜索逻辑不再背 StrategyState / ProposedAction
      那些搜索用不到的字段（OCR 置信度、帧号、可选目标表、坟场……）。

也就是：StrategyState / ProposedAction 只出现在进出口两个地方——
AiState.from_strategy_state()（进）和 Search._to_proposed()（出），中间过程干净。
"""

import heapq
from itertools import count
from time import monotonic
from uuid import uuid4

from ai.deck_strategy import deck_strategy
from src.game_state.recommendation_adapter import ordered_board
from src.recommendation_models import ActionKind, ProposedAction, SlotRef
from strategy import StrategyState

from .ai_action import AiAction, AiSlot
from .ai_state import AiState

try:
    # 星舰识别依赖本地 cards.json；缺失时退回单卡硬编码判断（见 starship.py）。
    from src.game_state.starship import is_starship_card
except ImportError:  # pragma: no cover - 只有裁剪掉该模块时才会走到
    is_starship_card = None

# 节点"还没评过分"的哨兵：与旧版 search.py 的 UNRANKED 同值，定义收敛到 AiState。
UNRANKED = AiState.UNRANKED
MAX_SEARCH = 100


def rankState(state: AiState, actions: list[AiAction]) -> float:
    #关键函数，评估一个场面的得分，分数越高越好
    #目前版本较简单，未来要基于不同卡组，实现不同的rankState
    #参数里增加actions，是因为有些时候相同的场面，动作顺序是有讲究的，比如敌方有个防死的奥秘，那攻击的顺序应该优先打到正数最低的血量
    #可以通过actions的顺序，赋分体现顺序差异
    """Evaluate both boards, heroes, and hands using the documented weights."""
    # 交给"当前卡组策略"评分（网页「基础配置 → 策略选择」决定用哪一个）：
    #   renwumu -> ai/renwumu.py（任务牧）
    #   yurensa -> ai/yurensa.py（鱼人萨）
    # 每个卡组一个 py 文件，只实现 choose / rankState，搜索流程一行都不用改。
    # 传进去的是 AiState / AiAction，策略只读它们与 StrategyState 同名的字段
    # （my_minions / my_hero / my_total_mana / action.action / action.card.name …）。
    strategy = deck_strategy()
    if strategy is None:
        # 选的是"盒子AI"（本地搜索本不该被调用），或者策略文件缺失/配置里名字
        # 写错：这里不猜分数，返回 0，让搜索退化成 END_TURN 兜底，而不是把异常
        # 抛到主循环里。
        return 0.0
    return strategy.rankState(state, actions)


def _slot(kind, owner=None, index=None) -> AiSlot:
    """构造搜索用的位置引用（语义与 src.recommendation_models.SlotRef 一致）。"""
    return AiSlot(kind, owner, index)


def _minion_from_slot(state, side, index):
    """把 1 基场面号位换成随从实体。

    那一格是地标、号位越界、或 index 为空（英雄攻击没有场面号位）时返回 None。
    旧实现直接做 `board[index - 1]`，英雄攻击会因为 index=None 抛 TypeError 把
    整个搜索打断，这里统一收敛成 None，再由调用方决定怎么处理。
    """
    try:
        entry = ordered_board(state, side)[index - 1]
    except (IndexError, TypeError, ValueError):
        return None
    if entry.kind != "minion":
        return None
    return entry.entity


def _entity_for_slot(state, slot):
    if slot is None:
        return None
    if slot.kind == "hero":
        return getattr(state, "my_hero" if slot.owner == "friendly"
                       else "oppo_hero", None)
    if slot.kind == "hero_power":
        return getattr(state, "my_hero_power", None)
    if slot.kind == "hand":
        try:
            return state.my_hand_cards[slot.index - 1]
        except (IndexError, TypeError, AttributeError):
            return None
    if slot.kind == "board_slot":
        try:
            return ordered_board(state, slot.owner)[slot.index - 1].entity
        except (IndexError, TypeError, ValueError, AttributeError):
            return None
    return None


def action_identity_key(state, action):
    """Stable same-turn identity: action kind plus exact source/target entities."""
    source = _entity_for_slot(state, action.source)
    target = _entity_for_slot(state, action.target)
    source_id = getattr(source, "entity_id", None) or action.entity_id
    target_id = getattr(target, "entity_id", None) or action.target_entity_id
    source_key = (str(source_id) if source_id is not None else
                  _slot_identity(action.source))
    target_key = (str(target_id) if target_id is not None else
                  _slot_identity(action.target))
    return (action.action.value, source_key, target_key)


def _slot_identity(slot):
    if slot is None:
        return ""
    return f"{slot.kind}:{slot.owner or ''}:{slot.index or ''}"


def doAction(state: AiState, action: AiAction) -> AiState:
    """Return a simulated copy after a minion attack or minion play.

    模拟永远发生在 copy() 出来的新场面上，绝不改传进来的 state，因此搜索过程中
    真实战局（以及执行层手里那份 StrategyState）不会被污染。

    注意：目前只精确模拟 ATTACK 与 PLAY_CARD。其它动作（Trade / 英雄技能 /
    地标 / 星舰 / 发现）仍会作为候选动作参与评分，但模拟时场面不变——与旧版
    行为一致，后续需要在下面补上对应的场面模拟。
    """
    result = state.copy()
    result.rank = UNRANKED

    # ---------------------------------------------------------------- 攻击
    if action.action == ActionKind.ATTACK:
        if action.source is None or action.target is None:
            return result
        # 随从攻击：source 是己方场面号位。
        # TODO：英雄攻击（source.kind == "hero"）目前没有模拟——英雄没有场面
        # 号位，_minion_from_slot 会返回 None，于是原样返回未改动的场面。
        attacker = _minion_from_slot(result, "friendly", action.source.index)
        if attacker is None:
            return result
        attack = getattr(attacker, "attack", 0)
        attacker.exhausted = 1
        if hasattr(attacker, "attackable_by_rush"):
            attacker.attackable_by_rush = 0
        if action.target.kind == "hero":
            if result.oppo_hero is not None:
                result.oppo_hero.damage += attack
            return result

        defender = _minion_from_slot(result, "enemy", action.target.index)
        if defender is None:
            return result
        if getattr(defender, "divine_shield", 0):
            defender.divine_shield = 0
        else:
            defender.damage += attack
        if getattr(attacker, "divine_shield", 0):
            attacker.divine_shield = 0
        else:
            attacker.damage += getattr(defender, "attack", 0)
        # 我方随从被换死时先通知卡组上下文（任务牧：关键随从死亡标记），
        # 再把血量 <= 0 的从场面过滤掉。过滤是"抹掉"，通知必须放在前面。
        if result.deck_context is not None:
            for dead_minion in result.my_minions:
                if getattr(dead_minion, "health", 1) <= 0:
                    result.deck_context.on_minion_died(dead_minion)
        result.my_minions = [
            minion for minion in result.my_minions
            if getattr(minion, "health", 1) > 0]
        result.oppo_minions = [
            minion for minion in result.oppo_minions
            if getattr(minion, "health", 1) > 0]
        return result

    # ---------------------------------------------------------------- 出牌
    if action.action == ActionKind.PLAY_CARD:
        if action.source is None:
            return result
        hand_index = action.source.index - 1
        if not 0 <= hand_index < len(result.my_hand_cards):
            return result
        minion = result.my_hand_cards.pop(hand_index)
        minion.zone = "PLAY"
        minion.zone_pos = max(
            (getattr(entity, "zone_pos", 0)
             for entity in result.my_minions + result.my_locations),
            default=0) + 1
        if hasattr(minion, "exhausted"):
            minion.exhausted = 1
        # 出牌后通知卡组上下文（任务牧：按法术学派累计任务进度）。
        if result.deck_context is not None:
            result.deck_context.on_card_played(minion)
        # TODO：这里把打出的牌一律当成"站场随从"来模拟（旧实现同样如此）。
        # 法术/武器/英雄牌的实际效果没有建模，地标也应该进 my_locations，
        # 后续按 card_type 分流会更准确。
        result.my_minions.append(minion)
        result.my_minions.sort(key=lambda entity: entity.zone_pos)
        result.my_used_mana += action.cost
    elif action.action == ActionKind.CHOOSE_DISCOVER:
        # 发现只选择一个选项。旧模拟保留了选择面板，搜索会在同一状态里再
        # 选一次；第二次虽得分更高，返回路径的第一步仍是之前的低分选项。
        result.discover_choice_count = None
        result.general_choice_cards = {}
    elif action.action == ActionKind.TRADE_CARD and action.instruction.startswith("预备"):
        if action.source is None:
            return result
        hand_index = action.source.index - 1
        if not 0 <= hand_index < len(result.my_hand_cards):
            return result
        card = result.my_hand_cards[hand_index]
        remaining = max(0, result.my_last_mana)
        result.my_used_mana += remaining
        try:
            card.current_cost = max(0, int(card.current_cost) - remaining - 1)
        except (TypeError, ValueError, AttributeError):
            pass
        entity_id = getattr(card, "entity_id", None)
        if entity_id is not None:
            result.prepared_entity_ids.add(str(entity_id))
    return result


def _possible_targets(entity, state=None) -> tuple[AiSlot, ...]:
    """返回手牌/英雄技能的候选目标号位（搜索用 AiSlot，号位 1 基）。

    优先读实体自带的可选目标表（SlotRef 或同类对象，目前一般没有）；没有时
    按卡面文本推断（_inferred_targets）——执行层选完牌还要点一下目标，卡面
    注明「有目标」的牌必须把每个合法目标各生成一个候选动作，否则执行那一步
    点不出目标、整手牌卡死。
    目标合法性（用户确认）：伤害可打脸（敌方英雄+敌方随从），恢复可奶英雄
    （己方英雄+己方随从）；buff 类（真言术：盾/愈合/幽魂不散/捉鬼专家）
    只指己方随从。
    """
    targets = getattr(entity, "possible_targets", None)
    if targets:
        slots = []
        for target in targets:
            if isinstance(target, AiSlot):
                slots.append(target)
            elif isinstance(target, SlotRef):
                slots.append(_slot(target.kind, target.owner, target.index))
        return tuple(slots)
    if state is None:
        return ()
    return _inferred_targets(entity, state)


def _requires_target(entity) -> bool:
    """按卡面文本判断这张牌是否需要指定目标。

    随从只认「战吼：」后的文本（预言师亡语的恢复、索利托斯战吼「一个本随从」
    都不会被误判）；排除「随机/所有」的群体效果（不死徒刑/噬灵疫病/麦迪文的
    胜利/暗言术：毁/雷斯的战吼）。已对任务牧全套卡牌核对无误判。
    """
    card_id = getattr(entity, "card_id", None)
    strategy = deck_strategy()
    policy = getattr(strategy, "requires_target", None)
    if callable(policy):
        result = policy(entity)
        if result is not None:
            return bool(result)
    text = _card_text(card_id)
    if not text:
        return False
    if getattr(entity, "cardtype", None) == "MINION":
        head = text.find("战吼")
        if head < 0:
            return False
        text = text[head:]
    if "恢复" in text and "生命值" in text:
        return True
    if ("造成" in text and "点伤害" in text
            and "随机" not in text and "所有" not in text):
        return True
    if "随机" not in text and ("友方随从" in text or "一个随从" in text):
        return True
    return False


def _inferred_targets(entity, state) -> tuple[AiSlot, ...]:
    """按卡面文本推断候选目标：每个合法目标一个号位（1 基，与攻击/执行一致）。"""
    if not _requires_target(entity):
        return ()
    text = _card_text(getattr(entity, "card_id", None))
    if getattr(entity, "cardtype", None) == "MINION":
        # _requires_target 为真时战吼一定存在。
        text = text[text.find("战吼"):]
    try:
        friendly = ordered_board(state, "friendly")
        enemy = ordered_board(state, "enemy")
    except (TypeError, ValueError):
        return ()

    def minion_slots(side, entries):
        return [_slot("board_slot", side, position)
                for position, entry in enumerate(entries, 1)
                if entry.kind == "minion"]

    if "恢复" in text and "生命值" in text:
        if "一个随从" in text or "友方随从" in text:
            return tuple(minion_slots("friendly", friendly))
        return (*minion_slots("friendly", friendly), _slot("hero", "friendly"))
    if ("造成" in text and "点伤害" in text
            and "随机" not in text and "所有" not in text):
        return (*minion_slots("enemy", enemy), _slot("hero", "enemy"))
    return tuple(minion_slots("friendly", friendly))


def _card_text(card_id) -> str:
    """card_id -> 当前卡组策略人工属性；其它卡牌回退到通用卡牌库。

    预备在日志实体上没有像 tradeable 那样的专属字段，只能靠 cards.json 的
    卡面文本认。src.game_state.choose_one.card_text 是现成的通用查询
    （lru_cache 缓存整张卡表，失败一律返回空串，不会把搜索打断）。
    """
    strategy = deck_strategy()
    text_provider = getattr(strategy, "card_text", None)
    deck_text = text_provider(card_id) if callable(text_provider) else ""
    if deck_text:
        return deck_text
    try:
        from src.game_state.choose_one import card_text
        return card_text(card_id) or ""
    except Exception:  # pragma: no cover - 卡表缺失时退化为"不生成预备动作"
        return ""


def getActions(state: AiState) -> list[AiAction]:
    """根据当前 AiState 生成所有候选动作（AIAction 版 getActions）。

        1. 随从攻击随从 / 随从攻击英雄
        2. 英雄攻击随从 / 英雄攻击英雄
        3~7. 打出手牌：随从 / 法术 / 武器 / 地标 / 英雄牌
        8. 交易（Trade）
        9. 使用英雄技能
        10. 使用场上地标
        11. 发射星舰
        12. 发现 / 选择
        13. 一个动作都没有 -> 结束回合
    与 doAction() 的分工：这里只负责"列出所有可做的动作"，具体模拟见 doAction()。
    目前只有 ATTACK / PLAY_CARD 有精确模拟，其余动作先作为候选参与评分。
    """
    actions: list[AiAction] = []

    # 发现界面是阻塞式选择：先选一张，选择完成后再重新搜索本回合动作。
    # 避免把出牌/攻击和发现候选混在同一棵路径里，导致选项评分被后续动作覆盖。
    choice_count = getattr(state, "discover_choice_count", None)
    if choice_count in (1, 2, 3, 4):
        actions = [AiAction(
            action=ActionKind.CHOOSE_DISCOVER,
            instruction=f"选择我方{choice_index}号位卡牌",
            source=_slot("discover_slot", "friendly", choice_index),
        ) for choice_index in range(1, choice_count + 1)]
        blocked = getattr(state, "blocked_action_keys", set())
        if blocked:
            actions = [action for action in actions
                       if action_identity_key(state, action) not in blocked]
        return actions or [AiAction.end_turn()]

    try:
        friendly_board = ordered_board(state, "friendly")
        enemy_board = ordered_board(state, "enemy")
    except (TypeError, ValueError):
        # 场面号位未知（zone_pos 缺失或重复）：给不出可执行动作，返回空表，
        # 由 aiSearch 的兜底逻辑结束回合。
        return actions

    available_mana = max(0, getattr(state, "my_last_mana", 0) or 0)

    enemy_minions = [entry for entry in enemy_board
                     if entry.kind == "minion"]
    enemy_taunts = [
        entry for entry in enemy_minions
        if getattr(entry.entity, "taunt", 0)
        and getattr(entry.entity, "can_be_attacked", True)
    ]

    def board_slot_number(board, target_entry):
        """把 BoardEntry 转成 1 基场面号位。"""
        for slot, entry in enumerate(board, 1):
            if entry is target_entry:
                return slot
        return None

    def card_cost(card):
        try:
            return int(getattr(card, "current_cost", 0))
        except (TypeError, ValueError, AttributeError):
            return -1

    def card_label(card):
        """卡牌中文名，拼进指令里（本地搜索的日志才知道到底出的是哪张牌）。"""
        name = getattr(card, "name", "") or ""
        return f"（{name}）" if name else ""

    def add_play_card(hand_slot, card, target=None, instruction=None):
        """生成一个 PLAY_CARD 候选（source 是手牌号位）。"""
        actions.append(AiAction(
            action=ActionKind.PLAY_CARD,
            instruction=instruction or f"打出手牌{hand_slot}号卡牌{card_label(card)}",
            source=_slot("hand", "friendly", hand_slot),
            target=target,
            cost=card_cost(card),
            card_type=getattr(card, "cardtype", None),
            card_id=getattr(card, "card_id", None),
            entity_id=getattr(card, "entity_id", None),
            # card 让卡组策略直接 action.card.name 认关键牌（嗜血/鱼人领军…）
            card=card,
        ))

    # ================================================================
    # 1. 随从攻击
    # ================================================================
    for source_slot, entry in enumerate(friendly_board, 1):
        if entry.kind != "minion":
            continue
        minion = entry.entity
        if not getattr(minion, "can_attack_minion", False):
            continue

        # 有嘲讽：只能攻击嘲讽；没有嘲讽：可以打任意可被攻击的随从。
        if enemy_taunts:
            targets = enemy_taunts
        else:
            targets = [enemy for enemy in enemy_minions
                       if getattr(enemy.entity, "can_be_attacked", True)]

        for target_entry in targets:
            target_slot = board_slot_number(enemy_board, target_entry)
            if target_slot is None:
                continue
            actions.append(AiAction(
                action=ActionKind.ATTACK,
                instruction=(f"我方{source_slot}号随从{card_label(minion)}"
                             f"攻击敌方{target_slot}号随从"
                             f"{card_label(target_entry.entity)}"),
                source=_slot("board_slot", "friendly", source_slot),
                target=_slot("board_slot", "enemy", target_slot),
                card=minion,
                card_id=getattr(minion, "card_id", None),
                entity_id=getattr(minion, "entity_id", None),
            ))

        # 没有嘲讽才能打脸。
        if (not enemy_taunts
                and getattr(minion, "can_beat_face", False)
                and getattr(state, "oppo_hero", None) is not None):
            actions.append(AiAction(
                action=ActionKind.ATTACK,
                instruction=(f"我方{source_slot}号随从{card_label(minion)}"
                             "攻击敌方英雄"),
                source=_slot("board_slot", "friendly", source_slot),
                target=_slot("hero", "enemy"),
                card=minion,
                card_id=getattr(minion, "card_id", None),
                entity_id=getattr(minion, "entity_id", None),
            ))

    # ================================================================
    # 2. 英雄攻击
    # ================================================================
    my_hero = getattr(state, "my_hero", None)
    if my_hero is not None and getattr(my_hero, "can_attack", False):
        if enemy_taunts:
            hero_targets = enemy_taunts
        else:
            hero_targets = [enemy for enemy in enemy_minions
                            if getattr(enemy.entity, "can_be_attacked", True)]

        for target_entry in hero_targets:
            target_slot = board_slot_number(enemy_board, target_entry)
            if target_slot is None:
                continue
            actions.append(AiAction(
                action=ActionKind.ATTACK,
                instruction=(f"我方英雄攻击敌方{target_slot}号随从"
                             f"{card_label(target_entry.entity)}"),
                source=_slot("hero", "friendly"),
                target=_slot("board_slot", "enemy", target_slot),
                card=my_hero,
                card_id=getattr(my_hero, "card_id", None),
                entity_id=getattr(my_hero, "entity_id", None),
            ))

        if (not enemy_taunts
                and getattr(state, "oppo_hero", None) is not None):
            actions.append(AiAction(
                action=ActionKind.ATTACK,
                instruction="我方英雄攻击敌方英雄",
                source=_slot("hero", "friendly"),
                target=_slot("hero", "enemy"),
                card=my_hero,
                card_id=getattr(my_hero, "card_id", None),
                entity_id=getattr(my_hero, "entity_id", None),
            ))

    # ================================================================
    # 3. 手牌 PLAY_CARD
    # ================================================================
    hand_cards = getattr(state, "my_hand_cards", [])
    board_count = len(friendly_board)

    strategy = deck_strategy()
    for hand_slot, card in enumerate(hand_cards, 1):
        if str(getattr(card, "entity_id", "")) in state.prepared_entity_ids:
            continue
        can_play_card = getattr(strategy, "can_play_card", None)
        if callable(can_play_card) and not can_play_card(state, card):
            continue
        card_type = getattr(card, "cardtype", None)
        cost = card_cost(card)
        if cost < 0 or cost > available_mana:
            continue

        # 3.1 随从（场面最多 7 个实体）：战吼需要目标的（捉鬼专家这类），
        #     只生成带目标版本——执行层选完牌还要点一下目标；场上没有可点
        #     目标就等价于这张牌本回合上不了场。
        if card_type == "MINION":
            if board_count >= 7:
                continue
            targets = _possible_targets(card, state)
            if targets:
                for target in targets:
                    add_play_card(
                        hand_slot, card, target=target,
                        instruction=(f"打出手牌{hand_slot}号随从"
                                     f"{card_label(card)}并指定目标"))
            else:
                add_play_card(
                    hand_slot, card,
                    instruction=f"打出手牌{hand_slot}号随从{card_label(card)}")

        # 3.2 法术：卡面注明「有目标」的（恢复/单体伤害/使一个随从…）只生成
        #     带目标版本，没有合法目标 = 本回合打不出；其余先生成无目标版本，
        #     实体自带可选目标时再补目标版本。
        elif card_type == "SPELL":
            targets = _possible_targets(card, state)
            if targets:
                for target in targets:
                    add_play_card(
                        hand_slot, card, target=target,
                        instruction=(f"打出手牌{hand_slot}号法术"
                                     f"{card_label(card)}并指定目标"))
            elif not _requires_target(card):
                add_play_card(
                    hand_slot, card,
                    instruction=f"打出手牌{hand_slot}号法术{card_label(card)}")

        # 3.3 武器
        elif card_type == "WEAPON":
            add_play_card(hand_slot, card,
                          instruction=f"打出手牌{hand_slot}号武器{card_label(card)}")

        # 3.4 地标（也占场面格）
        elif card_type == "LOCATION":
            if board_count >= 7:
                continue
            add_play_card(hand_slot, card,
                          instruction=f"打出手牌{hand_slot}号地标{card_label(card)}")

        # 3.5 英雄牌
        elif card_type == "HERO":
            add_play_card(hand_slot, card,
                          instruction=f"打出手牌{hand_slot}号英雄牌{card_label(card)}")

    # ================================================================
    # 4. 交易 / 预备 Trade & Tempt
    # ================================================================
    # 预备（把卡牌拖到牌库：消耗全部剩余法力，费用额外 -1，卡牌回到手牌）
    # 没有独立日志字段，靠卡面文本里的「预备」认出来。执行层（适配器 + 拖拽）
    # 对交易/锻造/预备是同一条路径，因此复用 TRADE_CARD 动作，只是指令文案
    # 区分开（文案只进日志，解析与执行都只认动作类型和手牌号位）。
    for hand_slot, card in enumerate(hand_cards, 1):
        tradeable = getattr(card, "tradeable",
                            getattr(card, "is_tradeable", False))
        temptable = not tradeable and "预备" in _card_text(
            getattr(card, "card_id", None))
        if not (tradeable or temptable):
            continue
        actions.append(AiAction(
            action=ActionKind.TRADE_CARD,
            instruction=(f"预备手牌{hand_slot}号卡牌{card_label(card)}"
                         if temptable else
                         f"交易手牌{hand_slot}号卡牌{card_label(card)}"),
            source=_slot("hand", "friendly", hand_slot),
            card_type=getattr(card, "cardtype", None),
            card_id=getattr(card, "card_id", None),
            entity_id=getattr(card, "entity_id", None),
            card=card,
        ))

    # ================================================================
    # 5. 使用英雄技能
    # ================================================================
    hero_power = getattr(state, "my_hero_power", None)
    if hero_power is not None:
        power_cost = card_cost(hero_power)
        power_exhausted = getattr(hero_power, "exhausted", 0)
        if 0 <= power_cost <= available_mana and not power_exhausted:
            power_targets = _possible_targets(hero_power, state)
            if power_targets:
                # 指向性英雄技能（牧师恢复类）：必须点目标，只生成带目标版本。
                for target in power_targets:
                    actions.append(AiAction(
                        action=ActionKind.USE_HERO_POWER,
                        instruction=(f"使用英雄技能{card_label(hero_power)}"
                                     "并指定目标"),
                        source=_slot("hero_power", "friendly"),
                        target=target,
                        cost=power_cost,
                        card=hero_power,
                        card_id=getattr(hero_power, "card_id", None),
                        entity_id=getattr(hero_power, "entity_id", None),
                    ))
            elif not _requires_target(hero_power):
                actions.append(AiAction(
                    action=ActionKind.USE_HERO_POWER,
                    instruction=f"使用英雄技能{card_label(hero_power)}",
                    source=_slot("hero_power", "friendly"),
                    cost=power_cost,
                    card=hero_power,
                    card_id=getattr(hero_power, "card_id", None),
                    entity_id=getattr(hero_power, "entity_id", None),
                ))

    # ================================================================
    # 6. 使用场上地标
    # ================================================================
    for slot_number, entry in enumerate(friendly_board, 1):
        if entry.kind != "location":
            continue
        location = entry.entity
        # 没有 can_activate 的实体不强行猜测，默认允许生成动作。
        if not getattr(location, "can_activate", True):
            continue
        actions.append(AiAction(
            action=ActionKind.USE_LOCATION,
            instruction=f"使用我方{slot_number}号地标{card_label(location)}",
            source=_slot("board_slot", "friendly", slot_number),
            card_id=getattr(location, "card_id", None),
            entity_id=getattr(location, "entity_id", None),
            card=location,
        ))
        for target in _possible_targets(location):
            actions.append(AiAction(
                action=ActionKind.USE_LOCATION,
                instruction=(f"使用我方{slot_number}号地标"
                             f"{card_label(location)}并指定目标"),
                source=_slot("board_slot", "friendly", slot_number),
                target=target,
                card_id=getattr(location, "card_id", None),
                entity_id=getattr(location, "entity_id", None),
                card=location,
            ))

    # ================================================================
    # 7. 发射星舰
    # ================================================================
    if is_starship_card is not None:
        for slot_number, entry in enumerate(friendly_board, 1):
            if entry.kind != "minion":
                continue
            card_id = getattr(entry.entity, "card_id", None)
            try:
                is_starship = is_starship_card(card_id)
            except Exception:
                is_starship = False
            if not is_starship:
                continue
            actions.append(AiAction(
                action=ActionKind.LAUNCH_STARSHIP,
                instruction=(f"发射我方{slot_number}号位星舰"
                             f"{card_label(entry.entity)}"),
                source=_slot("board_slot", "friendly", slot_number),
                card_id=card_id,
                entity_id=getattr(entry.entity, "entity_id", None),
                card=entry.entity,
            ))

    # ================================================================
    # 8. 发现 / 选择
    # ================================================================
    # ================================================================
    # 9. 当前没有任何动作 -> END_TURN
    # ================================================================
    blocked = getattr(state, "blocked_action_keys", set())
    if blocked:
        actions = [action for action in actions
                   if action_identity_key(state, action) not in blocked]
    if not actions:
        actions.append(AiAction.end_turn())

    return actions


class Search:
    @staticmethod
    def pri(state: AiState, cost: int) -> float:
        # 暂时没用，将来如果修改搜索节点优先级使用
        best_actions: list[AiAction] = []
        if state.rank <= UNRANKED:
            state.rank = rankState(state, best_actions)
        return state.rank

    def aiSearch(self, state: AiState, cost: int) -> tuple[list[AiAction], float]:
        # 关键搜索代码（内部实现）：输入输出都是精简的 AiState / AiAction。
        # 基于优先级队列，优先展开当前评分最高的场面，直到展开 MAX_SEARCH 个
        # 场面为止，返回最优的动作序列和分数。
        best_actions: list[AiAction] = []
        if state.rank <= UNRANKED:
            state.rank = rankState(state, best_actions)
        initial_score = state.rank
        best_score = initial_score
        rank_calls = 1
        serial = count()
        heap = [(-initial_score, next(serial), max(0, int(cost)), state, [])]

        while heap and rank_calls < MAX_SEARCH:
            neg_score, _, remaining_cost, current_state, current_actions = (
                heapq.heappop(heap))
            actions = getActions(current_state)
            for action in actions:
                if rank_calls >= MAX_SEARCH:
                    break
                if action.cost > remaining_cost:
                    continue

                new_actions = current_actions + [action]
                new_score = rankState(current_state, new_actions)
                rank_calls += 1
                # 注意这个修改，更符合人出牌的感觉，每次得分是 出牌前的旧场面 + 新动作后的总评分，而不是新场面+新动作
                # 因为一些动作带来的敌方死亡，写分数函数更麻烦，这样也方便平移silverfish中算法，和sf保持一致。
                # Todo：这引入一个潜在问题，相同的场面，不同action到达，可能得分不同哦，暂不处理
                new_state = doAction(current_state, action) #模拟操作下，得到新场面
                new_state.rank = new_score

                if new_score > best_score:
                    best_score = new_score
                    best_actions = new_actions
                # 发现选项在真实对局中是一次独立的 UI 操作。若继续展开选择
                # 之后的动作，后续动作的分数会覆盖各选项之间的差异，路径首步
                # 就会退化为候选列表里的第一个选项。
                if action.action == ActionKind.CHOOSE_DISCOVER:
                    continue
                heapq.heappush(
                    heap,
                    (-new_score, next(serial), remaining_cost - action.cost,
                     new_state, new_actions))

        if not best_actions:
            best_actions = [AiAction.end_turn()]
        return best_actions, best_score

    def search(self, state: StrategyState, cost: int) -> tuple[list[ProposedAction], float]:
        #public 本文件唯一被外部调用函数，所以用了外部数据结构StrategyState和ProposedAction
        #关键搜索代码，基于优先级队列，优先搜索当前最优的场面，直到搜索到MAX_SEARCH个场面，返回最优的动作序列和分数
        #实现过程：基于输入的state，构造出AiState对象，调用aiSearch函数得到 Aiaction后，再构造出ProposedAction列表，并返回
        #
        # 这里是"搜索模块对外"的唯一进出口：
        #   进：StrategyState --AiState.from_strategy_state()--> AiState
        #   出：list[AiAction] --Search._to_proposed()-----------> list[ProposedAction]
        # 中间全程只用 AiState / AiAction，不碰两边的旧协议。
        ai_state = AiState.from_strategy_state(state)
        # 卡组上下文（任务进度等"场面之外"的信息）：StrategyState 没有该属性，
        # from_strategy_state 读到 None，这里交给当前策略从真实战局补种
        # （任务牧从 my_graveyard 重建；鱼人萨没有 build_deck_context，跳过）。
        strategy = deck_strategy()
        if strategy is not None and ai_state.deck_context is None:
            builder = getattr(strategy, "build_deck_context", None)
            if callable(builder):
                ai_state.deck_context = builder(state)
        ai_state.prepared_entity_ids = set(
            getattr(state, "prepared_entity_ids", ()) or ())
        ai_state.blocked_action_keys = set(
            getattr(state, "blocked_action_keys", ()) or ())
        ai_actions, best_score = self.aiSearch(ai_state, cost)
        log_result = getattr(strategy, "log_search_result", None)
        if callable(log_result):
            log_result(ai_state, ai_actions)
        proposed = [self._to_proposed(state, action) for action in ai_actions]
        return proposed, best_score

    # ------------------------------------------------------------------ 出：转换
    @staticmethod
    def _to_slot_ref(slot: AiSlot | None) -> SlotRef | None:
        """AiSlot -> SlotRef（字段一一对应；None 原样返回）。"""
        if slot is None:
            return None
        return SlotRef(slot.kind, slot.owner, slot.index)

    @classmethod
    def _to_proposed(cls, state: StrategyState,
                     action: AiAction) -> ProposedAction:
        """把搜索内部动作还原成执行层动作协议 ProposedAction。

        字段语义与旧 get_action._make_action() 完全一致（同样的 turn_number /
        log_revision / frame_id / 置信度 / 指令文本），因此执行层（adapt_action）
        拿到的东西和改造前没有区别，不需要跟着改。
        """
        log_revision = getattr(state, "log_revision", 0)
        turn_number = getattr(state, "game_num_turns_in_play", 0)
        source_entity = _entity_for_slot(state, action.source)
        target_entity = _entity_for_slot(state, action.target)
        return ProposedAction(
            action_id=str(uuid4()),
            frame_id=f"search:{turn_number}:{log_revision}",
            created_at=monotonic(),
            turn_number=turn_number,
            log_revision=log_revision,
            raw_instruction=action.instruction,
            normalized_instruction=action.instruction,
            action=action.action,
            source=cls._to_slot_ref(action.source),
            destination=cls._to_slot_ref(action.destination),
            target=cls._to_slot_ref(action.target),
            entity_id=(getattr(source_entity, "entity_id", None)
                       or action.entity_id),
            target_entity_id=(getattr(target_entity, "entity_id", None)
                              or action.target_entity_id),
            card_type=action.card_type,
            ocr_confidence=1.0,
            semantic_confidence=1.0,
            cost=action.cost,
        )
