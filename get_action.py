# 基于当前场面，得到所有潜在的可行单一动作list

from src.game_state.recommendation_adapter import ordered_board
from src.recommendation_models import ActionKind, ProposedAction, SlotRef
from strategy import StrategyState
from itertools import count
from time import monotonic
from uuid import uuid4

def _make_action(state, action, instruction, source=None, target=None, cost=0,
                 card_type=None, log_revision=None):
    #构造一个脚本可执行动作:ProposedAction
    if log_revision is None:
        log_revision = getattr(state, "log_revision", 0)
    return ProposedAction(
        action_id=str(uuid4()),
        frame_id=f"search:{state.game_num_turns_in_play}:{log_revision}",
        created_at=monotonic(),
        turn_number=state.game_num_turns_in_play,
        log_revision=log_revision,
        raw_instruction=instruction,
        normalized_instruction=instruction,
        action=action,
        source=source,
        target=target,
        card_type=card_type,
        ocr_confidence=1.0,
        semantic_confidence=1.0,
        cost=cost,
    )

def getActions(state: StrategyState) -> list[ProposedAction]:
    """
    根据当前 StrategyState 生成候选动作。

    当前支持：
        1. 随从攻击随从
        2. 随从攻击英雄
        3. 英雄攻击随从
        4. 英雄攻击英雄
        5. 打出随从
        6. 打出法术
        7. 打出武器
        8. 打出地标
        9. Trade
        10. 使用英雄技能
        11. 使用地标
        12. 发射 Starship
        13. Discover / Choice
        14. 没有动作时结束回合

    注意：
        当前版本的 doAction() 主要能够模拟：
            ATTACK
            PLAY_CARD

        因此其它 ActionKind 会先作为候选动作生成，
        后续需要在 doAction() 中补充对应的场面模拟。
    """

    actions = []

    try:
        friendly_board = ordered_board(state, "friendly")
        enemy_board = ordered_board(state, "enemy")
    except (ValueError, TypeError):
        return actions

    # ================================================================
    # 基础数据
    # ================================================================

    available_mana = max(
        0,
        getattr(
            state,
            "my_last_mana",
            getattr(state, "my_mana", 0)
        )
    )

    enemy_minions = [
        entry
        for entry in enemy_board
        if entry.kind == "minion"
    ]

    friendly_minions = [
        entry
        for entry in friendly_board
        if entry.kind == "minion"
    ]

    enemy_taunts = [
        entry
        for entry in enemy_minions
        if getattr(entry.entity, "taunt", 0)
        and getattr(entry.entity, "can_be_attacked", True)
    ]

    def board_slot(board, target_entry):
        """把 BoardEntry 转成 1-based board slot。"""
        for slot, entry in enumerate(board, 1):
            if entry is target_entry:
                return slot
        return None

    def card_cost(card):
        try:
            return int(getattr(card, "current_cost", 0))
        except (TypeError, ValueError, AttributeError):
            return -1

    def add_play_card(
        hand_slot,
        card,
        target=None,
        instruction=None,
    ):
        """
        通过现有 _make_action() 创建 PLAY_CARD。

        注意：
        当前 _make_action() 不支持 destination，
        所以这里不传 destination。
        """

        cost = card_cost(card)

        actions.append(
            _make_action(
                state,
                ActionKind.PLAY_CARD,
                instruction or f"打出手牌{hand_slot}号卡牌",
                source=SlotRef(
                    "hand",
                    "friendly",
                    hand_slot,
                ),
                target=target,
                card_type=getattr(card, "cardtype", None),
                cost=cost,
            )
        )

    # ================================================================
    # 1. 随从攻击
    # ================================================================

    for source_slot, entry in enumerate(friendly_board, 1):

        if entry.kind != "minion":
            continue

        minion = entry.entity

        if not getattr(minion, "can_attack_minion", False):
            continue

        # ------------------------------------------------------------
        # 有嘲讽：只能攻击嘲讽
        # ------------------------------------------------------------

        if enemy_taunts:
            targets = enemy_taunts
        else:
            targets = [
                enemy
                for enemy in enemy_minions
                if getattr(
                    enemy.entity,
                    "can_be_attacked",
                    True
                )
            ]

        for target_entry in targets:

            target_slot = board_slot(
                enemy_board,
                target_entry
            )

            if target_slot is None:
                continue

            actions.append(
                _make_action(
                    state,
                    ActionKind.ATTACK,
                    f"我方{source_slot}号随从攻击敌方{target_slot}号随从",
                    source=SlotRef(
                        "board_slot",
                        "friendly",
                        source_slot,
                    ),
                    target=SlotRef(
                        "board_slot",
                        "enemy",
                        target_slot,
                    ),
                )
            )

        # ------------------------------------------------------------
        # 没有嘲讽，可以攻击英雄
        # ------------------------------------------------------------

        if (
            not enemy_taunts
            and getattr(minion, "can_beat_face", False)
            and getattr(state, "oppo_hero", None) is not None
        ):
            actions.append(
                _make_action(
                    state,
                    ActionKind.ATTACK,
                    f"我方{source_slot}号随从攻击敌方英雄",
                    source=SlotRef(
                        "board_slot",
                        "friendly",
                        source_slot,
                    ),
                    target=SlotRef(
                        "hero",
                        "enemy",
                    ),
                )
            )

    # ================================================================
    # 2. 英雄攻击
    # ================================================================

    my_hero = getattr(state, "my_hero", None)

    if my_hero is not None and getattr(
        my_hero,
        "can_attack",
        False
    ):

        # 有嘲讽，只能攻击嘲讽
        if enemy_taunts:
            hero_targets = enemy_taunts
        else:
            hero_targets = [
                enemy
                for enemy in enemy_minions
                if getattr(
                    enemy.entity,
                    "can_be_attacked",
                    True
                )
            ]

        for target_entry in hero_targets:

            target_slot = board_slot(
                enemy_board,
                target_entry
            )

            if target_slot is None:
                continue

            actions.append(
                _make_action(
                    state,
                    ActionKind.ATTACK,
                    "我方英雄攻击敌方随从",
                    source=SlotRef(
                        "hero",
                        "friendly",
                    ),
                    target=SlotRef(
                        "board_slot",
                        "enemy",
                        target_slot,
                    ),
                )
            )

        # 没有嘲讽，可以打脸
        if (
            not enemy_taunts
            and getattr(state, "oppo_hero", None) is not None
        ):
            actions.append(
                _make_action(
                    state,
                    ActionKind.ATTACK,
                    "我方英雄攻击敌方英雄",
                    source=SlotRef(
                        "hero",
                        "friendly",
                    ),
                    target=SlotRef(
                        "hero",
                        "enemy",
                    ),
                )
            )

    # ================================================================
    # 3. 手牌 PLAY_CARD
    # ================================================================

    hand_cards = getattr(
        state,
        "my_hand_cards",
        []
    )

    board_count = len(friendly_board)

    for hand_slot, card in enumerate(hand_cards, 1):

        card_type = getattr(
            card,
            "cardtype",
            None
        )

        cost = card_cost(card)

        if cost < 0:
            continue

        if cost > available_mana:
            continue

        # ------------------------------------------------------------
        # 3.1 随从
        # ------------------------------------------------------------

        if card_type == "MINION":

            # 炉石场面最多 7 个实体
            if board_count >= 7:
                continue

            add_play_card(
                hand_slot,
                card,
                instruction=f"打出手牌{hand_slot}号随从",
            )

        # ------------------------------------------------------------
        # 3.2 法术
        # ------------------------------------------------------------

        elif card_type == "SPELL":

            # 先生成无目标版本。
            #
            # 后续 carddefs.xml 接入后，再根据 card definition
            # 判断该法术到底是否需要目标。
            add_play_card(
                hand_slot,
                card,
                instruction=f"打出手牌{hand_slot}号法术",
            )

            # 如果当前 card 对象本身已经提供 possible_targets，
            # 则额外生成目标版本。
            possible_targets = getattr(
                card,
                "possible_targets",
                None
            )

            if possible_targets:

                for target in possible_targets:

                    if not isinstance(target, SlotRef):
                        continue

                    add_play_card(
                        hand_slot,
                        card,
                        target=target,
                        instruction=(
                            f"打出手牌{hand_slot}号法术并指定目标"
                        ),
                    )

        # ------------------------------------------------------------
        # 3.3 武器
        # ------------------------------------------------------------

        elif card_type == "WEAPON":

            add_play_card(
                hand_slot,
                card,
                instruction=f"打出手牌{hand_slot}号武器",
            )

        # ------------------------------------------------------------
        # 3.4 地标
        # ------------------------------------------------------------

        elif card_type == "LOCATION":

            if board_count >= 7:
                continue

            add_play_card(
                hand_slot,
                card,
                instruction=f"打出手牌{hand_slot}号地标",
            )

        # ------------------------------------------------------------
        # 3.5 英雄牌
        # ------------------------------------------------------------

        elif card_type == "HERO":

            add_play_card(
                hand_slot,
                card,
                instruction=f"打出手牌{hand_slot}号英雄牌",
            )

    # ================================================================
    # 4. Trade
    # ================================================================

    for hand_slot, card in enumerate(hand_cards, 1):

        tradeable = getattr(
            card,
            "tradeable",
            getattr(
                card,
                "is_tradeable",
                False
            )
        )

        if not tradeable:
            continue

        actions.append(
            _make_action(
                state,
                ActionKind.TRADE_CARD,
                f"交易手牌{hand_slot}号卡牌",
                source=SlotRef(
                    "hand",
                    "friendly",
                    hand_slot,
                ),
                card_type=getattr(
                    card,
                    "cardtype",
                    None
                ),
            )
        )

    # ================================================================
    # 5. 使用英雄技能
    # ================================================================

    hero_power = getattr(
        state,
        "my_hero_power",
        None
    )

    if hero_power is not None:

        power_cost = card_cost(hero_power)

        power_exhausted = getattr(
            hero_power,
            "exhausted",
            0
        )

        if (
            power_cost >= 0
            and power_cost <= available_mana
            and not power_exhausted
        ):

            actions.append(
                _make_action(
                    state,
                    ActionKind.USE_HERO_POWER,
                    "使用英雄技能",
                    source=SlotRef(
                        "hero_power",
                        "friendly",
                    ),
                    cost=power_cost,
                )
            )

            # 如果以后 carddefs.xml / StrategyEntity 提供
            # possible_targets，这里自动支持目标型英雄技能。
            possible_targets = getattr(
                hero_power,
                "possible_targets",
                None
            )

            if possible_targets:

                for target in possible_targets:

                    if not isinstance(target, SlotRef):
                        continue

                    actions.append(
                        _make_action(
                            state,
                            ActionKind.USE_HERO_POWER,
                            "使用英雄技能并指定目标",
                            source=SlotRef(
                                "hero_power",
                                "friendly",
                            ),
                            target=target,
                            cost=power_cost,
                        )
                    )

    # ================================================================
    # 6. 使用场上地标
    # ================================================================

    for board_slot_number, entry in enumerate(
        friendly_board,
        1
    ):

        if entry.kind != "location":
            continue

        location = entry.entity

        # 当前项目中的 StrategyEntity 如果没有 can_activate，
        # 不强行猜测，默认允许生成动作。
        can_activate = getattr(
            location,
            "can_activate",
            True
        )

        if not can_activate:
            continue

        actions.append(
            _make_action(
                state,
                ActionKind.USE_LOCATION,
                f"使用我方{board_slot_number}号地标",
                source=SlotRef(
                    "board_slot",
                    "friendly",
                    board_slot_number,
                ),
            )
        )

        possible_targets = getattr(
            location,
            "possible_targets",
            None
        )

        if possible_targets:

            for target in possible_targets:

                if not isinstance(target, SlotRef):
                    continue

                actions.append(
                    _make_action(
                        state,
                        ActionKind.USE_LOCATION,
                        f"使用我方{board_slot_number}号地标并指定目标",
                        source=SlotRef(
                            "board_slot",
                            "friendly",
                            board_slot_number,
                        ),
                        target=target,
                    )
                )

    # ================================================================
    # 7. Starship
    # ================================================================

    try:
        from src.game_state.starship import is_starship_card
    except ImportError:
        is_starship_card = None

    if is_starship_card is not None:

        for board_slot_number, entry in enumerate(
            friendly_board,
            1
        ):

            if entry.kind != "minion":
                continue

            card_id = getattr(
                entry.entity,
                "card_id",
                None
            )

            try:
                is_starship = is_starship_card(card_id)
            except Exception:
                is_starship = False

            if not is_starship:
                continue

            actions.append(
                _make_action(
                    state,
                    ActionKind.LAUNCH_STARSHIP,
                    f"发射我方{board_slot_number}号位星舰",
                    source=SlotRef(
                        "board_slot",
                        "friendly",
                        board_slot_number,
                    ),
                )
            )

    # ================================================================
    # 8. Discover / Choice
    # ================================================================

    choice_count = getattr(
        state,
        "discover_choice_count",
        None
    )

    if choice_count in (1, 2, 3, 4):

        for choice_index in range(
            1,
            choice_count + 1
        ):

            actions.append(
                _make_action(
                    state,
                    ActionKind.CHOOSE_DISCOVER,
                    f"选择我方{choice_index}号位卡牌",
                    source=SlotRef(
                        "discover_slot",
                        "friendly",
                        choice_index,
                    ),
                )
            )

    # ================================================================
    # 9. 当前没有任何动作 -> END_TURN
    # ================================================================

    if not actions:

        actions.append(
            _make_action(
                state,
                ActionKind.END_TURN,
                "结束回合",
            )
        )

    return actions
