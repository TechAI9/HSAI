# AI文件夹里面一个文件 代表一个卡组策略
# 不同卡组策略，只是rankState 场面评价函数不同，搜索等其他流程保持不变，这样就实现了卡组变化和项目主架构解耦合
# 卡组代码：注意不通卡组，要修改下面代码，确保评价函数认识自己卡组的所有卡牌。
# 更常见任务牧要加上暮光祭礼，下面代码要更新
"""
### 任务牧
# 职业：牧师
# 模式：标准模式
# 甲虫年
#
# 2x (1) 不死徒刑
# 1x (1) 寻求平衡
# 2x (1) 愈合
# 2x (1) 真言术：盾
# 1x (2) 月翼信使
# 2x (2) 生命仪式
# 2x (2) 神圣之拥
# 2x (3) 噬灵疫病
# 2x (3) 幽魂不散
# 2x (3) 捉鬼专家
# 2x (4) 墓晨太阳花
# 2x (4) 暗言术：毁
# 1x (4) 梦魇之王萨维斯
# 2x (4) 灵质处决
# 2x (5) 麦迪文的胜利
# 1x (7) 雷斯·范盖斯特
# 2x (7) 预言师
# 
AAECAcGABgSg+wbDgweolgfc4AcN8J8ExZQH5J4H0q8Hm78HssUHr8kHk98HsN8H1eAH2eAH9OAHlvwHAAA=
# 
"""


#留牌策略
#必留：1费寻求平衡 7费预言师 2费生命仪式 4费梦魇之王萨维斯
#打法思路：
#早期靠预言师，尽量确保预言师上场时对方解不掉，方便当回合或者下回合贴复生组件，得到复生预言师
#中期靠完成寻求平衡的任务，得到任务奖励，注意一定要2个任务都完成，2个奖励生命之息和死亡之触都得到后，才出它两合并后的奖励随从：循环新生
#最后一波靠7费 雷斯·范盖斯特 复活本局复生过的随从，带来一波大场面赢下
#卡牌使用：
#真言术：盾   神圣法术，有目标，使一个随从获得+2生命值，抽一张牌。
#愈合：神圣法术，有目标，为一个随从恢复所有生命值。抽一张牌
#不死徒刑：暗影法术，随机触发本局中死亡的一个友方随从的亡语。  用于预言师或者循环新生死亡过，才使用。
#寻求平衡：第一回合只上这个任务牌。任务是出4个神圣法术和4个暗影法术，所以AiState类中加入基类deckContext，每个卡组继承这个类，记录特有的卡组上下文信息
#以任务牧为例：特有信息是 要记录，已经用了几个神圣法术和几个暗影法术，是否有过复生预言师死亡，是否有过循环新生死亡
#生命仪式：神圣法术，发现一张3费随从，召唤一个它的2/3复制。 打出生命仪式，就要涉及发现，要编写发现策略，优先发现复生随从，其次是战吼和嘲讽随从，不选择亡语随从，避免污染不死徒刑的随机触发亡语。
#神圣之拥：神圣法术，有目标，恢复4点生命值。获得2费黑暗之拥：造成4点伤害。
#黑暗之拥：暗影法术，有目标，2费造成4点伤害。
#幽魂不散：暗影法术，有目标，使一个随从攻击+2/生命值+3，复生和嘲讽。优先贴给预言师。
#捉鬼专家：有目标，使一个友方随从获得复生，如果其已经复生，召唤一个它的复制。优先贴给预言师和循环新生。注意：如果捉鬼专家和幽魂不散同一个回合对同一个随从打出，要先用幽魂不散，再用捉鬼专家，这样可以得到一个它的复制。
#噬灵疫病：暗影法术，造成4点伤害，随机分配到所有敌方随从身上。
#墓晨太阳花：神圣法术，抽两张牌
#灵质处决：暗影法术，消灭所有随从，每个玩家各获取一张3费法术牌，该牌召唤被消灭的随从。 灵质处决 优先用于自己场上有循环新生，每有一个循环新生死亡，会触发其亡语，给敌方英雄造成5点伤害。己方场上没有循环新生时使用要扣分。
#梦魇之王萨维斯：从牌库中发现一张随从牌。触发发现动作，需要写发现函数，优先发现预言师，如果没有预言师，自己已经完成寻求平衡任务或者将要完成，则选择雷斯·范盖斯特。
#麦迪文的胜利：对所有随从造成4点伤害。
#雷斯·范盖斯特： 复活本局复生过的随从，带来一波大场面赢下。要计算自己有的复生随从数量，最好是既有过复生预言师死亡，又有过循环新生。多多益善。上场时也要注意场上己方随从数量，避免空格子不够，能上的随从很少，炉石限定每方最多7个随从。
#暗言术：毁：消灭场上所有≥5攻的随从，暗影法术。用于解场。
#预言师：注意是预备随从，优先本回合预备，下回合的费用足够能打出预言师 再加上3费的复生组件，比如3费捉鬼专家或者3费幽魂不散。
#预备随从的意思是：将带有“预备”关键词的卡牌拖至牌库上方时，会消耗剩余法力值，使该卡牌的法力值消耗减少等量点数并额外减1点，随后卡牌回到手牌留待后续回合使用。
#硬币：后手硬币，不要白白出硬币，最后剩1费没事做。
#
# ============================================================================
# 实现说明（评分函数如何落实上面的注释）
# ============================================================================
# 评分框架：rankState = rankStaticState(场面) + rankActions(最新动作增量)。
# 搜索里每个节点的分数 = 当前场面分 + 最新动作的增量分（见 search.aiSearch），
# 所以 rankActions 只看 actions[-1]，和 ai/yurensa.py 的口径一致。
#
# 卡组上下文：ai/renwumu_context.py 的 RenwumuDeckContext（继承
# search.ai_state.DeckContext），记录：
#   * 已施放的神圣/暗影法术数（任务进度，各需 4 个）；
#   * 是否有过「预言师」死亡 / 「索利托斯，循环新生」死亡。
# 真实对局里 Search.search() 用 Renwumu.build_deck_context(StrategyState)
# 从我方坟场重建；搜索模拟里 doAction() 通过上下文钩子在分支上推进，
# 每个模拟分支各带一份，互不污染。
#
# 认牌约定：随从/关键牌用 action.card.name 和中文卡名比；任务牧的法术学派、
# 目标规则和预备标记由 ai/renwumu_context.py 按 card_id 人工维护。
#
# 目标打分：卡面注明「有目标」的牌（真言术：盾/愈合/神圣之拥/黑暗之拥/
# 幽魂不散/捉鬼专家），搜索侧 getActions 会按卡面文本给每个合法目标各生成
# 一个候选动作（_inferred_targets），rankActions 按 action.target 指到的
# 实体逐目标估值（_heal_gain / _target_damage_gain / _buff_gain …）。
#
# 硬币与预备：
#   * _coin_gain —— 硬币只有能让后续卡牌恰好用完增加的 1 点法力时才加分，
#     无法花完就扣分，避免硬币成为本回合最后动作；
#   * _tempt_gain —— 预备复用 TRADE_CARD 动作（search.getActions 会为卡面
#     含「预备」的手牌生成候选，执行层与交易共用拖到牌库的链路），只建模
#     预言师：优先预备后下回合能「预言师+3费复生组件」，其次下回合能直接
#     打出；折后费 = current_cost - 剩余法力 - 1。
from src.recommendation_models import ActionKind
from search.ai_action import AiAction, AiSlot
from search.ai_state import AiState
from src.game_state.recommendation_adapter import ordered_board

from ai.renwumu_context import (
    RenwumuDeckContext,
    card_item,
    card_text,
    spell_school,
    CARD_ID_PROPHET,
    CARD_ID_SOULTRONUS,
    CARD_ID_UNDEATH,
)
from json_op import query_json_item

# 雷斯·范盖斯特 card_id（萨维斯发现池里认它用）。
CARD_ID_RAGS = "CAP_806"
CARD_ID_GHOSTHUNTER = "CAP_804"
CARD_ID_INFUSED_HERO_POWER = "EDR_449p"  # 月亮的祝福：当回合取得一张减费牌


class Renwumu:
    # ================================================================ 参数区
    # ---------------------------------------------------------------- 留牌
    # 文件头注释「必留」清单，不在名单里的起手牌一律换掉。
    MULLIGAN_KEEP_NAMES = (
        "寻求平衡",         # 1费任务
        "预言师",           # 7费核心随从（复生预言师）
        "生命仪式",         # 2费神圣法术：发现3费随从+召唤2/3复制
        "梦魇之王萨维斯",   # 4费：发现牌库随从
    )

    # ---------------------------------------------------------------- 关键牌名
    CARD_QUEST = "寻求平衡"
    CARD_SHIELD = "真言术：盾"
    CARD_MEND = "愈合"
    CARD_UNDEATH = "不死徒刑"
    CARD_RITE = "生命仪式"
    CARD_HOLY_EMBRACE = "神圣之拥"
    CARD_DARK_EMBRACE = "黑暗之拥"
    CARD_GHOST_GRIP = "幽魂不散"
    CARD_GHOSTHUNTER = "捉鬼专家"
    CARD_PLAGUE = "噬灵疫病"
    CARD_SUNFLOWER = "墓晨太阳花"
    CARD_EXECUTE = "灵质处决"
    CARD_SACHVIER = "梦魇之王萨维斯"
    CARD_VICTORY = "麦迪文的胜利"
    CARD_RAGS = "雷斯·范盖斯特"
    CARD_RUIN = "暗言术：毁"
    CARD_PROPHET = "预言师"
    CARD_COIN = "幸运币"
    # 索利托斯：任务奖励半身 x2，拼合后 = 循环新生。
    CARD_SOULTRONUS = "索利托斯，循环新生"
    CARD_SOULTRONUS_LIFE = "索利托斯，生命之息"
    CARD_SOULTRONUS_DEATH = "索利托斯，死亡之触"

    # ---------------------------------------------------------------- 场面评分权重
    ATTACK_WEIGHT = 2        # 1 点攻击 = 2 分
    HEALTH_WEIGHT = 1        # 1 点血 = 1 分
    MY_HERO_WEIGHT = 1       # 我方英雄 1 点血 = 1 分
    ENEMY_HERO_WEIGHT = 1    # 敌方英雄 1 点血 = 1 分
    BOARD_PRESENCE_SCORE = 3  # 出一个随从的铺场分（场面静态分不含，避免和出牌分重复）
    LETHAL_BONUS = 1000.0    # 能直接打死对手的天价分

    # ---------------------------------------------------------------- 任务/关键牌评分
    QUEST_FIRST_TURN_BONUS = 100.0  # 第一回合必出任务（压过一切）
    QUEST_PLAY_BONUS = 8.0          # 错过第一回合后，补拍任务也值分
    QUEST_CAST_BONUS = 6.0          # 对应学派任务没完成时，施放一做法术的进度分
    HOLY_EMBRACE_FUEL_BONUS = 2.0   # 神圣之拥送的黑暗之拥 = 后续暗影进度燃料
    PROPHET_PLAY_BONUS = 8.0        # 上预言师（核心组件）
    PROPHET_ON_BOARD_BONUS = 6.0    # 静态：预言师站场（保它 = 保复生组件的靶子）
    SOULTRONUS_PLAY_BONUS = 50.0    # 上场循环新生
    SOULTRONUS_ON_BOARD_BONUS = 8.0  # 静态：循环新生站场
    SOULTRONUS_HALF_PENALTY = 50   # 两个任务没都完成就单出半身（浪费奖励） 原AI值6太小了，还是会单独打出

    KEY_TARGET_BONUS = 3.0          # 幽魂不散/捉鬼专家 优先贴给预言师/循环新生
    GHOSTHUNTER_PROPHET_BONUS = 100.0
    GHOSTHUNTER_ALREADY_REBORN_PROPHET_BONUS = 200.0
    GHOSTHUNTER_SOULTRONUS_COPY_BONUS = 200.0
    GHOST_GRIP_UNREBORN_PROPHET_BONUS = 200.0
    COPY_COMBO_BONUS = 6.0          # 先幽魂不散再捉鬼专家 = 战吼召唤复制
    COPY_COMBO_WASTE_PENALTY = 50  # 先捉鬼专家再幽魂不散 = 复生白给
    UNDEATH_PROPHET_VALUE = 8.0     # 不死徒刑触发预言师亡语（奶6+随机6费）
    UNDEATH_SOULTRONUS_VALUE = 5.0  # 不死徒刑触发循环新生亡语（5点伤害）
    UNDEATH_WASTE_PENALTY = 1000     # 没有死亡目标打不死徒刑（注释：死亡过才用）
    EXECUTE_NO_SOULTRONUS_PENALTY = 25.0  # 场上没有循环新生就放灵质处决（白清场）
    VICTORY_SMALL_CLEAR_BASE_PENALTY = 7.0  # 小规模清场惩罚，低攻击力击杀扣得更多
    RAGS_PER_REBORN = 4.0           # 雷斯·范盖斯特每复活一个复生随从的价值
    RAGS_FULL_POOL_BONUS = 50.0      # 预言师+循环新生都死亡过（最好情况）
    RAGS_NO_POOL_PENALTY = 200      # 没有复生死亡/场面满格，别上雷斯 原AI值5太小了，还是会上场，惩罚多一点
    ZERO_ATTACK_NON_TAUNT_KILL_PENALTY = 6.0
    GHOSTHUNTER_NO_TARGET_PENALTY = 50.0
    DISCOVER_DOMINATE_BASE = 10000.0  # 发现进行中必须先选，且留出选项间评分差距
    DISCOVER_PROPHET_BONUS = 100.0  # 发现池有预言师时绝对优先
    DISCOVER_RAGS_BONUS = 30.0      # 预言师没有时优先选雷斯
    DISCOVER_GHOSTHUNTER_BONUS = 20.0  # 前两者没有时选捉鬼专家
    DISCOVER_RAGS_FALLBACK = 3.0    # 任务没影时雷斯只是个7费白板
    DISCOVER_REBORN_BONUS = 8.0     # 生命仪式发现：优先复生随从
    DISCOVER_BATTLECRY_TAUNT_BONUS = 4.0  # 其次战吼/嘲讽
    DISCOVER_DEATHRATTLE_PENALTY = 8.0    # 不选亡语（避免污染不死徒刑目标池）
    DISCOVER_BASE = 2.0
    HERO_POWER_UNUSED_PENALTY = 20.0  # 普通2费治疗技能目前不主动使用
    INFUSED_POWER_BONUS = 6.0         # 灌注技能能当回合补一张减费牌
    INFUSED_MINION_BONUS = 12.0       # 空场或明显落后时优先补随从
    INFUSED_SPELL_BONUS = 20.0        # 任务仍缺神圣/暗影法术时优先补法术

    # ---------------------------------------------------------------- 硬币/预备
    COIN_ENABLER_BONUS = 2.0        # 硬币后能用牌恰好花完法力时才考虑
    COIN_WASTE_PENALTY = 50.0        # 硬币后无法花完法力：扣分，避免硬币收尾
    # 预备两级优先（文件头注释）。参照系：现在裸上预言师 = PROPHET_PLAY_BONUS 8
    # + 预言师站场价值约 21（6/6+铺场分）= 29 分；同回合「预言师+复生组件」
    # 约 32~43 分。预备组合分要压过裸上、又不能压过同回合保护。
    TEMPT_COMBO_BONUS = 31.0        # 预备后下回合能「预言师+3费复生组件」
    TEMPT_PLAY_BONUS = 12.0         # 预备后下回合能直接打出预言师（其次）
    TEMPT_USELESS_PENALTY = 5.0     # 没剩余法力/打不出/已够便宜：别预备
    TEMPT_COIN_WINDOW_BONUS = 10.0  # 有硬币剩2费预备预言师
    TEMPT_NO_COIN_WINDOW_BONUS = 10.0  # 无硬币剩3费预备预言师

    # ================================================================ 上下文
    @staticmethod
    def build_deck_context(state):
        """Search.search() 调用：从真实战局（StrategyState）构建任务牧上下文。

        从我方坟场统计已施放的神圣/暗影法术数、预言师与循环新生是否死亡过。
        """
        return RenwumuDeckContext.from_graveyard(
            getattr(state, "my_graveyard", None),
            getattr(state, "my_dead_card_ids", None))

    @staticmethod
    def can_play_card(state: AiState, card) -> bool:
        """Deck-specific play gate for cards whose prerequisites are strategic."""
        context = Renwumu._context(state)
        card_id = getattr(card, "card_id", None)
        if card_id == CARD_ID_UNDEATH:
            return context.prophet_died or context.soultronus_died
        if card_id == CARD_ID_RAGS:
            # 雷斯必须等两只核心复生随从至少一个死过，而且场上能容纳全部复活物，
            # 否则战吼价值不够，不作为候选动作。
            return (context.prophet_died or context.soultronus_died
                    and max(0, 7 - state.my_board_slot_num)
                    >= context.reborn_death_count())   # 待更新 能复生若干个也行，未必要全部都有各自
        return True

    @staticmethod
    def card_text(card_id):
        """Expose this deck's manually curated card text to generic target inference."""
        return card_text(card_id)

    @staticmethod
    def requires_target(entity):
        """Return the deck's explicit targeting rule, or None for generic fallback."""
        item = card_item(getattr(entity, "card_id", None))
        if not item:
            return None
        return bool(item.get("targeted", False))

    @staticmethod
    def log_search_result(state: AiState, actions: list[AiAction]):
        """Keep Renwumu-only diagnostics beside its deck rules."""
        if (actions and actions[0].card_id == CARD_ID_RAGS
                and state.deck_context is not None
                and hasattr(state.deck_context, "summary")):
            print("[Renwumu] 雷斯·范盖斯特上场前死亡记录："
                  f"{state.deck_context.summary()}；"
                  f"可用场格={max(0, 7 - state.my_board_slot_num)}")
        if state.discover_choice_count not in (1, 2, 3, 4):
            return
        choice_scores = []
        chosen_index = None
        if actions and actions[-1].action == ActionKind.CHOOSE_DISCOVER:
            chosen_index = getattr(actions[-1].source, "index", None)
        for index in range(1, state.discover_choice_count + 1):
            option_action = AiAction(
                ActionKind.CHOOSE_DISCOVER,
                source=AiSlot("discover_slot", "friendly", index))
            score = Renwumu.rankActions(state, [option_action])
            options = state.general_choice_cards or {}
            zero_based = 0 in options or "0" in options
            key = index - 1 if zero_based else index
            card_id = options.get(key, options.get(str(key)))
            choice_scores.append(
                f"{index}号={Renwumu._card_name(card_id)}({score:g})")
        chosen = (Renwumu._card_name(
            Renwumu._choice_card_id(state, chosen_index))
                  if chosen_index is not None else "未选择")
        print("[Renwumu] 发现候选牌及评分：" + "，".join(choice_scores)
              + f"；最终选择：{chosen}")

    @staticmethod
    def _card_name(card_id):
        if not card_id:
            return "未知"
        item = query_json_item(card_id)
        return (item or {}).get("name") or card_id

    @staticmethod
    def _choice_card_id(state: AiState, index):
        options = getattr(state, "general_choice_cards", None) or {}
        if index is None:
            return None
        zero_based = 0 in options or "0" in options
        key = index - 1 if zero_based else index
        return options.get(key, options.get(str(key)))

    @staticmethod
    def _context(state) -> RenwumuDeckContext:
        """取当前分支的卡组上下文；没有（异常/旧调用方）时用零进度兜底。"""
        context = getattr(state, "deck_context", None)
        if isinstance(context, RenwumuDeckContext):
            return context
        return RenwumuDeckContext()

    # ================================================================ 留牌
    @staticmethod
    def choose(state: AiState) -> list[int]:
        #每个卡组都有自己的choose策略，决定留牌时，如何选择
        """起手留牌（Mulligan）决策：返回需要【换掉】的手牌下标（0 基）。

        调用方：src/flow/mulligan_flow.py 的 MulliganFlow.run_local ——
        网页「策略选择」选到任务牧时，换牌阶段不再读盒子
        面板，而是用本函数代替盒子 AI 的留牌意见。

        约定：
          * 返回值是 `state.my_hand_cards` 的 0 基下标列表；返回空列表 =
            全部保留（仍然会点“确认”把起手交上去）。
          * 这里只表达“想换哪几张”；幸运币不可替换、超出起手布局的位置点不到，
            这些由执行层（MulliganFlow）统一过滤，卡组策略不必关心点击坐标。
          * 不修改 state，可安全重复调用（MulliganFlow 每次重试都会重新调用）。

        当前策略（文件头注释「必留」）：不在 MULLIGAN_KEEP_NAMES 里的牌全换。
        """
        hand = list(getattr(state, "my_hand_cards", ()) or ())
        replace = [
            index for index, card in enumerate(hand)
            if (getattr(card, "name", "") or "") not in Renwumu.MULLIGAN_KEEP_NAMES
        ]
        names = [getattr(hand[index], "name", "?") for index in replace]
        print(f"[本地留牌] 起手 {len(hand)} 张，换掉 {len(replace)} 张"
              f"（必留：{', '.join(Renwumu.MULLIGAN_KEEP_NAMES)}）：{names}")
        return replace

    # ================================================================ 场面评分
    @staticmethod
    def rankStaticState(state: AiState) -> float:
        #和场面有关的评分，和动作无关 private函数
        """场面分：随从攻血 + 嘲讽 + 关键随从站场奖励 + 双方英雄血量。"""
        res = 0.0
        for minion in getattr(state, "my_minions", []):
            attack = getattr(minion, "attack", 0)
            res += (attack * Renwumu.ATTACK_WEIGHT
                    + (getattr(minion, "health", 0) * Renwumu.HEALTH_WEIGHT
                       if attack > 0 else 0))
            if getattr(minion, "taunt", 0):
                res += 1
            name = getattr(minion, "name", "") or ""
            if name == Renwumu.CARD_PROPHET:
                res += Renwumu.PROPHET_ON_BOARD_BONUS
            elif name == Renwumu.CARD_SOULTRONUS:
                res += Renwumu.SOULTRONUS_ON_BOARD_BONUS
        for minion in getattr(state, "oppo_minions", []):
            attack = getattr(minion, "attack", 0)
            res -= (attack * Renwumu.ATTACK_WEIGHT
                    + (getattr(minion, "health", 0) * Renwumu.HEALTH_WEIGHT
                       if attack > 0 else 0))
        my_hero = getattr(state, "my_hero", None)
        oppo_hero = getattr(state, "oppo_hero", None)
        res += getattr(my_hero, "health", 0) * Renwumu.MY_HERO_WEIGHT
        res -= getattr(oppo_hero, "health", 0) * Renwumu.ENEMY_HERO_WEIGHT
        return res

    # ================================================================ 动作评分
    @staticmethod
    def rankActions(state: AiState, actions: list[AiAction]) -> float:
        #和动作顺序有关的评分，注意最新动作是列表最后一个 private函数
        """动作增量分：只评"最新那个动作"（列表最后一个），增量随路径累加。"""
        if not actions:
            return 0.0
        action = actions[-1]
        if action.action == ActionKind.PLAY_CARD:
            return Renwumu._play_gain(state, action, actions)
        if action.action == ActionKind.ATTACK:
            return Renwumu._attack_gain(state, action)
        if action.action == ActionKind.CHOOSE_DISCOVER:
            return Renwumu._discover_gain(state, action)
        if action.action == ActionKind.USE_HERO_POWER:
            return Renwumu._hero_power_gain(state, action)
        if action.action == ActionKind.TRADE_CARD:
            # 预备（预言师）复用 TRADE_CARD 动作；真交易不建模保持中性。
            return Renwumu._tempt_gain(state, action)
        # 地标/星舰：暂不给增量分
        return 0.0

    @staticmethod
    def _hero_power_gain(state: AiState, action: AiAction) -> float:
        """普通英雄技能只恢复2点生命，目前不主动用；灌注技能可补临时牌。"""
        hero_power = getattr(state, "my_hero_power", None)
        if getattr(hero_power, "card_id", None) != CARD_ID_INFUSED_HERO_POWER:
            return -Renwumu.HERO_POWER_UNUSED_PENALTY
        return Renwumu.INFUSED_POWER_BONUS

    @staticmethod
    def rankState(state: AiState, actions: list[AiAction]) -> float:
        #关键函数，评估一个场面的得分，分数越高越好
        res = 0.0
        # 先评价场面
        res += Renwumu.rankStaticState(state)
        #再评价动作
        res += Renwumu.rankActions(state, actions) # 有一些卡组可以不评价动作
        return res

    # ---------------------------------------------------------------- 出牌
    @staticmethod
    def _play_gain(state: AiState, action: AiAction,
                   actions: list[AiAction]) -> float:
        """打出一张牌的增量分：法术/随从分流。"""
        name = action.card_name
        context = Renwumu._context(state)
        if action.card_type == "SPELL":
            return Renwumu._spell_gain(state, action, name, context, actions)
        if action.card_type == "MINION":
            return Renwumu._minion_gain(state, action, name, context, actions)
        return 0.0

    @staticmethod
    def _spell_gain(state: AiState, action: AiAction, name: str,
                    context: RenwumuDeckContext, actions: list[AiAction]) -> float:
        """法术分 = 学派任务进度分 + 各牌效果分（按文件头注释逐一落实）。"""
        gain = 0.0
        # 任务进度：对应学派没满 4 个时，施放一做法术就推进任务
        school = spell_school(action.card_id)
        if school == "HOLY" and context.holy_quest_open():
            gain += Renwumu.QUEST_CAST_BONUS
        elif school == "SHADOW" and context.shadow_quest_open():
            gain += Renwumu.QUEST_CAST_BONUS

        if name == Renwumu.CARD_QUEST:
            # "第一回合只上这个任务牌"：第一回合给压倒性分；错过再补拍也值分。
            gain += (Renwumu.QUEST_FIRST_TURN_BONUS
                     if state.my_total_mana == 1
                     else Renwumu.QUEST_PLAY_BONUS)
        elif name == Renwumu.CARD_SHIELD:
            # +2生命 + 抽一张：贴谁按目标算（关键随从优先）；没有可贴目标的
            # 动作根本不会生成（search 侧过滤），这里只是兜底口径。
            gain += 2.0 + Renwumu._buff_gain(state, action)
        elif name == Renwumu.CARD_MEND:
            # 满疗一个随从 + 抽一张：目标缺血越多越值。
            gain += 2.0 + Renwumu._heal_gain(state, action, amount=None)
        elif name == Renwumu.CARD_RITE:
            # 发现3费随从 + 召唤2/3复制（发现选择见 _discover_gain）。
            gain += 4.0
        elif name == Renwumu.CARD_HOLY_EMBRACE:
            # 恢复4点（可奶英雄）+ 获取黑暗之拥：黑暗之拥是暗影法术 = 燃料。
            gain += 3.0 + Renwumu._heal_gain(state, action, amount=4)
            if context.shadow_quest_open():
                gain += Renwumu.HOLY_EMBRACE_FUEL_BONUS
        elif name == Renwumu.CARD_DARK_EMBRACE:
            # 2费造成4点伤害（可打脸）：按目标算——斩杀/杀随从/烧血。
            gain += Renwumu._target_damage_gain(state, action, 4)
        elif name == Renwumu.CARD_GHOST_GRIP:
            # 幽魂不散：+2/+3复生嘲讽，贴谁按目标算；同回合顺序见组合判定。
            gain += Renwumu._ghost_grip_gain(state, action, actions)
        elif name == Renwumu.CARD_UNDEATH:
            # 不死徒刑：复生预言师或循环新生死亡过才用（文件头注释）。
            gain += Renwumu._undead_gain(context)
        elif name == Renwumu.CARD_PLAGUE:
            # 噬灵疫病：4点伤害随机分配到敌方随从，按最优分配估杀伤。
            gain += Renwumu._split_damage_gain(state, 4)
        elif name == Renwumu.CARD_SUNFLOWER:
            # 墓晨太阳花：抽两张牌。
            gain += 4.0
        elif name == Renwumu.CARD_EXECUTE:
            # 灵质处决：优先场上有循环新生时清场（每个+5点英雄伤害）。
            gain += Renwumu._execute_gain(state)
        elif name == Renwumu.CARD_VICTORY:
            # 麦迪文的胜利：对所有随从4点伤害，敌我一起算净收益。
            gain += Renwumu._aoe_damage_gain(state, 4)
        elif name == Renwumu.CARD_RUIN:
            # 暗言术：毁：消灭所有>=5攻随从，只解场，别误伤自己大随从。
            gain += Renwumu._ruin_gain(state)
        elif name == Renwumu.CARD_COIN:
            # 硬币：有后续牌能恰好花完增加的1费才加分，否则扣分。
            gain += Renwumu._coin_gain(state, context)
        else:
            # 未建模法术：只吃学派进度分，保底一点点。
            gain += 0.5
        return gain

    @staticmethod
    def _minion_gain(state: AiState, action: AiAction, name: str,
                     context: RenwumuDeckContext,
                     actions: list[AiAction]) -> float:
        """随从分 = 站场价值 + 关键随从按注释的额外价值。"""
        gain = 0.0
        if action.card is not None:
            gain += Renwumu._minion_value(action.card, mine=True)

        if name == Renwumu.CARD_PROPHET:
            # 核心组件：站住才有复生预言师。
            gain += Renwumu.PROPHET_PLAY_BONUS
        elif name == Renwumu.CARD_GHOSTHUNTER:
            # 捉鬼专家：贴谁按目标算，优先预言师/循环新生；先幽魂不散后捉鬼
            # 专家（同一个目标）= 战吼召唤复制。
            gain += 2.0
            target_entity = Renwumu._target_entity(state, action)
            if target_entity is None:
                gain -= Renwumu.GHOSTHUNTER_NO_TARGET_PENALTY
            elif target_entity.name == Renwumu.CARD_PROPHET:
                gain += Renwumu.GHOSTHUNTER_PROPHET_BONUS
                if Renwumu._target_has_reborn(
                        target_entity, action, actions):
                    gain += Renwumu.GHOSTHUNTER_ALREADY_REBORN_PROPHET_BONUS
            elif (target_entity.name == Renwumu.CARD_SOULTRONUS
                  and Renwumu._free_slots_before_play(state, actions) >= 2):
                # 两个空格分别供捉鬼专家上场和战吼生成循环新生复制。
                gain += Renwumu.GHOSTHUNTER_SOULTRONUS_COPY_BONUS
            if (len(actions) >= 2
                    and actions[-2].card_name == Renwumu.CARD_GHOST_GRIP
                    and Renwumu._same_target(actions[-2], action)):
                gain += Renwumu.COPY_COMBO_BONUS
        elif name == Renwumu.CARD_SACHVIER:
            # 梦魇之王萨维斯：发现牌库随从（预言师优先，见 _discover_gain）。
            gain += 3.0
        elif name == Renwumu.CARD_RAGS:
            # 雷斯·范盖斯特：复活本局复生过的随从，多多益善 + 注意空格。
            gain += Renwumu._rags_gain(state, context)
        elif name == Renwumu.CARD_SOULTRONUS:
            # 循环新生本体：两个任务都完成后的奖励随从。
            gain += Renwumu.SOULTRONUS_PLAY_BONUS
        elif name in (Renwumu.CARD_SOULTRONUS_LIFE, Renwumu.CARD_SOULTRONUS_DEATH):
            # 半身：任务没全完成就单出 = 浪费奖励（文件头注释：都完成才出）。
            gain += (Renwumu.SOULTRONUS_PLAY_BONUS
                     if context.quest_complete()
                     else -Renwumu.SOULTRONUS_HALF_PENALTY)
        return gain

    # ---------------------------------------------------------------- 目标相关
    @staticmethod
    def _target_entity(state: AiState, action: AiAction):
        """动作目标号位 -> 实体（英雄或随从）；没指定目标/号位无效返回 None。"""
        target = action.target
        if target is None:
            return None
        if target.kind == "hero":
            if target.owner == "enemy":
                return getattr(state, "oppo_hero", None)
            if target.owner == "friendly":
                return getattr(state, "my_hero", None)
            return None
        return Renwumu._board_minion(
            state, target.owner or "enemy", target.index)

    @staticmethod
    def _is_key_minion(entity) -> bool:
        """预言师 / 循环新生：复生组件的优先目标。"""
        return (getattr(entity, "name", "") or "") in (
            Renwumu.CARD_PROPHET, Renwumu.CARD_SOULTRONUS)

    @staticmethod
    def _same_target(a: AiAction, b: AiAction) -> bool:
        """两个动作的目标是否同一个号位（幽魂不散/捉鬼专家的组合牌序判定）。"""
        ta, tb = a.target, b.target
        if ta is None or tb is None:
            return False
        return (ta.kind, ta.owner, ta.index) == (tb.kind, tb.owner, tb.index)

    @staticmethod
    def _target_has_reborn(entity, action: AiAction,
                           actions: list[AiAction]) -> bool:
        """Current reborn tag plus reborn applied earlier in this search path."""
        if getattr(entity, "reborn", False):
            return True
        return any(
            previous.card_name in (Renwumu.CARD_GHOST_GRIP,
                                   Renwumu.CARD_GHOSTHUNTER)
            and Renwumu._same_target(previous, action)
            for previous in actions[:-1]
        )

    @staticmethod
    def _free_slots_before_play(state: AiState,
                                actions: list[AiAction]) -> int:
        """Correct for non-minion plays that generic simulation models as bodies."""
        simulated_nonminions = sum(
            1 for previous in actions
            if previous.action == ActionKind.PLAY_CARD
            and previous.card_type != "MINION")
        return max(0, 7 - state.my_board_slot_num + simulated_nonminions)

    @staticmethod
    def _buff_gain(state: AiState, action: AiAction) -> float:
        """+2 生命值类 buff（真言术：盾）按目标算：关键随从优先。"""
        entity = Renwumu._target_entity(state, action)
        if entity is None:
            return 0.0
        gain = 2 * Renwumu.HEALTH_WEIGHT
        if Renwumu._is_key_minion(entity):
            gain += Renwumu.KEY_TARGET_BONUS
        return gain

    @staticmethod
    def _heal_gain(state: AiState, action: AiAction, amount) -> float:
        """恢复类法术按目标算：缺血越多越值，满血目标 = 白给（小惩罚）。

        amount=None 表示「恢复所有生命值」（愈合）。随从/英雄的缺口都直接
        读 damage 字段（随从 health = max_health - damage；英雄还叠护甲，
        damage 同样是已掉的量）。
        """
        target = action.target
        entity = Renwumu._target_entity(state, action)
        if entity is None:
            return 0.0
        missing = getattr(entity, "damage", 0) or 0
        if missing <= 0:
            return -1.0                        # 满血奶：白给
        healed = missing if amount is None else min(amount, missing)
        weight = (Renwumu.MY_HERO_WEIGHT
                  if target is not None and target.kind == "hero"
                  else Renwumu.HEALTH_WEIGHT)
        return healed * weight

    @staticmethod
    def _target_damage_gain(state: AiState, action: AiAction,
                            damage: int) -> float:
        """单体伤害按目标算：斩杀天价 > 打死随从拿价值 > 打脸烧血。"""
        target = action.target
        if target is None:
            return damage * Renwumu.ENEMY_HERO_WEIGHT   # 兜底：按打脸估
        if target.kind == "hero":
            if target.owner != "enemy":
                return 0.0
            hero = getattr(state, "oppo_hero", None)
            health = getattr(hero, "health", 0)
            if 0 < health <= damage:
                return Renwumu.LETHAL_BONUS             # 这一下就打死了
            return damage * Renwumu.ENEMY_HERO_WEIGHT
        minion = Renwumu._board_minion(
            state, target.owner or "enemy", target.index)
        if minion is None:
            return 0.0
        health = getattr(minion, "health", 0)
        if health <= 0:
            return 0.0
        dealt = min(damage, health)
        gain = dealt * Renwumu.HEALTH_WEIGHT
        if dealt >= health:
            gain += (Renwumu._enemy_kill_value(minion)
                     - health * Renwumu.HEALTH_WEIGHT)
        return gain

    @staticmethod
    def _ghost_grip_gain(state: AiState, action: AiAction,
                         actions: list[AiAction]) -> float:
        """幽魂不散：贴谁按目标算，优先预言师/循环新生；同回合捉鬼专家已经
        给同一个随从贴过复生就白给了。"""
        entity = Renwumu._target_entity(state, action)
        if entity is None:
            return -2.0                        # 没有可贴目标（防御性兜底）
        gain = 2.0                             # +2/+3 嘲讽复生的基础价值
        if (entity.name == Renwumu.CARD_PROPHET
                and not Renwumu._target_has_reborn(entity, action, actions)):
            gain += Renwumu.GHOST_GRIP_UNREBORN_PROPHET_BONUS
        if (len(actions) >= 2
                and actions[-2].card_name == Renwumu.CARD_GHOSTHUNTER
                and Renwumu._same_target(actions[-2], action)):
            gain -= Renwumu.COPY_COMBO_WASTE_PENALTY
        return gain

    @staticmethod
    def _undead_gain(context: RenwumuDeckContext) -> float:
        """不死徒刑：随机触发死亡友方随从亡语，死亡标记越多越值。"""
        if not (context.prophet_died or context.soultronus_died):
            return -Renwumu.UNDEATH_WASTE_PENALTY
        best = 0.0
        if context.prophet_died:
            best = max(best, Renwumu.UNDEATH_PROPHET_VALUE)
        if context.soultronus_died:
            best = max(best, Renwumu.UNDEATH_SOULTRONUS_VALUE)
        return best

    @staticmethod
    def _rags_gain(state: AiState, context: RenwumuDeckContext) -> float:
        """雷斯·范盖斯特：复活复生过的随从；预言师+循环新生都死过最理想。

        注意场面空格（炉石每方最多 7 随从）：满格复活不了几个，别上。
        """
        pool = context.reborn_death_count()
        free_slots = max(0, 7 - state.my_board_slot_num)
        if (not context.prophet_died or not context.soultronus_died
                or free_slots < pool):
            return -Renwumu.RAGS_NO_POOL_PENALTY
        gain = min(pool, free_slots) * Renwumu.RAGS_PER_REBORN
        if pool >= 2:
            gain += Renwumu.RAGS_FULL_POOL_BONUS
        return gain

    @staticmethod
    def _coin_gain(state: AiState, context: RenwumuDeckContext) -> float:
        """硬币只在后续能把增加的 1 费恰好花完时加分，否则扣分。

        模拟里硬币的 +1 临时法力不结算（doAction 只累计 my_used_mana），
        因此在真实出牌后由下一轮搜索继续推荐后续动作。这里先确保手里存在
        一张费用恰好等于当前剩余法力+1的可用牌，避免硬币成为本回合最后动作
        或导致法力浪费。
        """
        if state.my_last_mana <= 0:
            return -Renwumu.COIN_WASTE_PENALTY
        want = state.my_last_mana + 1
        for card in getattr(state, "my_hand_cards", ()):
            name = getattr(card, "name", "") or ""
            if name == Renwumu.CARD_COIN:
                continue
            try:
                cost = int(getattr(card, "current_cost", 0))
            except (TypeError, ValueError):
                continue
            if cost != want:
                continue
            # 半身在任务没全完成时打了也是白打，别为它白出硬币。
            if (name in (Renwumu.CARD_SOULTRONUS_LIFE,
                         Renwumu.CARD_SOULTRONUS_DEATH)
                    and not context.quest_complete()):
                continue
            return Renwumu.COIN_ENABLER_BONUS
        return -Renwumu.COIN_WASTE_PENALTY

    @staticmethod
    def _tempt_gain(state: AiState, action: AiAction) -> float:
        """预备（复用 TRADE_CARD 动作，只建模预言师）：本回合预备，下回合成型。

        预备把卡牌拖到牌库：消耗全部剩余法力，费用额外 -1，卡牌回到手牌，
        所以折后费 = current_cost - 剩余法力 - 1。两级优先（文件头注释）：
          1. 预备后下回合费用足够「预言师 + 复生组件（捉鬼专家/幽魂不散）」；
          2. 其次预备后下回合能直接打出预言师。
        没有剩余法力、预言师已经够便宜、或下回合也打不出：别预备（白拖一
        回合）。本回合就能「预言师+组件」一起打时也别预备——同回合上场带
        保护严格更好（用户注释：预言师上场当回合或下回合贴复生组件）。
        预备动作不做场面模拟（doAction 原样返回），同分路径搜索会自动保留
        最短的那条，不会反复预备。
        """
        if (getattr(action, "card_name", "") or "") != Renwumu.CARD_PROPHET:
            return 0.0                    # 真交易/其它卡：不建模，保持中性
        try:
            cost = int(getattr(action.card, "current_cost", 0))
        except (TypeError, ValueError, AttributeError):
            return 0.0
        remaining = state.my_last_mana
        next_mana = state.my_total_mana + 1   # 下回合法力（近似：+1 水晶）
        if remaining <= 0 or cost <= 1:
            # 没法力可消耗（防重复预备）/已经便宜到随时能打。
            return -Renwumu.TEMPT_USELESS_PENALTY
        new_cost = max(0, cost - remaining - 1)
        if new_cost > next_mana:
            return -Renwumu.TEMPT_USELESS_PENALTY
        # 本回合能「预言师+复生组件」一起打：别预备，直接上。
        if (cost <= remaining
                and Renwumu._reborn_component_fits(state, remaining - cost)):
            return -Renwumu.TEMPT_USELESS_PENALTY
        if Renwumu._reborn_component_fits(state, next_mana - new_cost):
            gain = Renwumu.TEMPT_COMBO_BONUS
        else:
            gain = Renwumu.TEMPT_PLAY_BONUS

        has_coin = any(
            (getattr(card, "name", "") or "") == Renwumu.CARD_COIN
            for card in getattr(state, "my_hand_cards", ()))
        if has_coin and remaining == 2:
            gain += Renwumu.TEMPT_COIN_WINDOW_BONUS
        elif not has_coin and remaining == 3:
            gain += Renwumu.TEMPT_NO_COIN_WINDOW_BONUS
        return gain

    @staticmethod
    def _reborn_component_fits(state: AiState, budget: int) -> bool:
        """手牌里有没有一笔 budget 费内打得出的复生组件（捉鬼专家/幽魂不散）。"""
        for card in getattr(state, "my_hand_cards", ()):
            if (getattr(card, "name", "") or "") not in (
                    Renwumu.CARD_GHOSTHUNTER, Renwumu.CARD_GHOST_GRIP):
                continue
            try:
                cost = int(getattr(card, "current_cost", 0))
            except (TypeError, ValueError):
                continue
            if 0 <= cost <= budget:
                return True
        return False

    # ---------------------------------------------------------------- 伤害类
    @staticmethod
    def _split_damage_gain(state: AiState, damage: int) -> float:
        """伤害随机分配到敌方随从：按"先杀血最少的"贪心估最优分配。"""
        minions = sorted(
            (m for m in getattr(state, "oppo_minions", [])
             if getattr(m, "health", 0) > 0),
            key=lambda m: getattr(m, "health", 0))
        gain = 0.0
        budget = damage
        for minion in minions:
            if budget <= 0:
                break
            health = getattr(minion, "health", 0)
            if health <= budget:
                budget -= health
                gain += Renwumu._enemy_kill_value(minion)
            else:
                gain += budget * Renwumu.HEALTH_WEIGHT
                budget = 0
        return gain

    @staticmethod
    def _aoe_damage_gain(state: AiState, damage: int) -> float:
        """AOE伤害净值；麦迪文之胜的小规模清场按击杀攻击力额外扣分。"""
        gain = 0.0
        killed_enemy_attack = 0
        killed_enemy_count = 0
        for minion in getattr(state, "oppo_minions", []):
            health = getattr(minion, "health", 0)
            if health <= 0:
                continue
            dealt = min(damage, health)
            gain += dealt * Renwumu.HEALTH_WEIGHT
            if dealt >= health:
                killed_enemy_attack += max(0, getattr(minion, "attack", 0))
                killed_enemy_count += 1
                gain += (Renwumu._enemy_kill_value(minion)
                         - health * Renwumu.HEALTH_WEIGHT)
        for minion in getattr(state, "my_minions", []):
            health = getattr(minion, "health", 0)
            if health <= 0:
                continue
            dealt = min(damage, health)
            gain -= dealt * Renwumu.HEALTH_WEIGHT
            if dealt >= health:
                gain -= (Renwumu._minion_value(minion, mine=True)
                         - health * Renwumu.HEALTH_WEIGHT)
        if (killed_enemy_attack <= 6 or killed_enemy_count <= 2):
            gain -= 4 * (
                Renwumu.VICTORY_SMALL_CLEAR_BASE_PENALTY
                - killed_enemy_attack)
            
        return gain

    @staticmethod
    def _execute_gain(state: AiState) -> float:
        """灵质处决：清全场。优先己方场上有循环新生（清场后它死亡，亡语
        就送敌方英雄几发 5 点）；没有循环新生时白清自己的场，先扣分。"""
        soultronus_num = sum(
            1 for minion in getattr(state, "my_minions", [])
            if (getattr(minion, "name", "") or "") == Renwumu.CARD_SOULTRONUS)
        if soultronus_num == 0:
            return -Renwumu.EXECUTE_NO_SOULTRONUS_PENALTY
        enemy_value = sum(
            Renwumu._enemy_kill_value(minion)
            for minion in getattr(state, "oppo_minions", []))
        my_value = sum(
            Renwumu._minion_value(minion, mine=True)
            for minion in getattr(state, "my_minions", []))
        return (enemy_value - my_value
                + soultronus_num * 5.0 * Renwumu.ENEMY_HERO_WEIGHT)

    @staticmethod
    def _ruin_gain(state: AiState) -> float:
        """暗言术：毁：消灭所有>=5攻随从。没有敌方目标就别空放。"""
        enemy_targets = [
            minion for minion in getattr(state, "oppo_minions", [])
            if getattr(minion, "attack", 0) >= 5]
        if not enemy_targets:
            return -100.0
        gain = sum(Renwumu._minion_value(minion, mine=False)
                   for minion in enemy_targets)
        gain -= 1.5 * sum(
            Renwumu._minion_value(minion, mine=True)
            for minion in getattr(state, "my_minions", [])
            if getattr(minion, "attack", 0) >= 5)
        return gain

    # ---------------------------------------------------------------- 攻击
    @staticmethod
    def _board_minion(state: AiState, side: str, slot):
        """1 基场面号位 -> 随从实体；越界或那一格是地标时返回 None。"""
        if not slot:
            return None
        try:
            entries = ordered_board(state, side)
        except Exception:
            return None
        if not 1 <= slot <= len(entries):
            return None
        entry = entries[slot - 1]
        return entry.entity if entry.kind == "minion" else None

    @staticmethod
    def _attack_gain(state: AiState, action: AiAction) -> float:
        """一次攻击值多少分：打脸按伤害算（能斩杀给天价），随从交换按换血算。

        简化：不考虑圣盾/剧毒/风怒/亡语，也不考虑溢出伤害。
        """
        attacker = action.card
        target = action.target
        if attacker is None or target is None:
            return 0.0
        attack = getattr(attacker, "attack", 0)
        if attack <= 0:
            return 0.0

        # ---- 打脸
        if target.kind == "hero":
            hero = getattr(state, "oppo_hero", None)
            health = getattr(hero, "health", 0)
            if hero is not None and 0 < health <= attack:
                return Renwumu.LETHAL_BONUS          # 这一下就打死了
            return attack * Renwumu.ENEMY_HERO_WEIGHT

        # ---- 随从交换
        defender = Renwumu._board_minion(state, "enemy", target.index)
        if defender is None:
            return 0.0
        attacker_health = getattr(attacker, "health", 0)
        defender_health = getattr(defender, "health", 0)
        defender_attack = getattr(defender, "attack", 0)
        if defender_health <= 0 or attacker_health <= 0:
            return 0.0

        gain = 0.0
        # 敌方随从掉血（或被打死：补上它剩下的价值）
        dealt = min(attack, defender_health)
        gain += dealt * Renwumu.HEALTH_WEIGHT
        if dealt >= defender_health:
            gain += (Renwumu._enemy_kill_value(defender)
                     - defender_health * Renwumu.HEALTH_WEIGHT)
        # 我方随从挨的反伤（或被换掉：扣掉它整个价值）
        taken = min(defender_attack, attacker_health)
        gain -= taken * Renwumu.HEALTH_WEIGHT
        if taken >= attacker_health:
            gain -= (Renwumu._minion_value(attacker, mine=True)
                     - attacker_health * Renwumu.HEALTH_WEIGHT)
        return gain

    # ---------------------------------------------------------------- 发现
    @staticmethod
    def _discover_gain(state: AiState, action: AiAction) -> float:
        """发现/选择：按选项认牌打分。

        * 萨维斯发现池固定优先预言师，其次雷斯，再次捉鬼专家。
        * 生命仪式等发现 3 费随从：优先复生，其次战吼/嘲讽，不选亡语
          （避免污染不死徒刑的随机触发亡语目标池）。
        * 发现界面里"选一个"要压过其它动作，否则搜索会推荐幻象出牌。
        """
        index = getattr(action.source, "index", None)
        # general_choice_cards 的键是日志里的 0 基序号，而 CHOOSE_DISCOVER 的
        # 号位是 1 基（搜索与执行都按「第 N 个选项」数）；之前直接拿 1 基去查
        # 0 基的表，打分与点击错位一格——「选左边第一张」其实按第二张打的分。
        card_id = Renwumu._choice_card_id(state, index)
        if not card_id:
            return Renwumu.DISCOVER_DOMINATE_BASE

        # 萨维斯的随从发现固定优先级：预言师 > 7费雷斯 > 捉鬼专家。
        # 用候选池内相对分数表达优先级，不再根据任务是否将完成而降级雷斯。
        if card_id == CARD_ID_PROPHET:
            return Renwumu.DISCOVER_DOMINATE_BASE + Renwumu.DISCOVER_PROPHET_BONUS
        if card_id == CARD_ID_RAGS:
            return Renwumu.DISCOVER_DOMINATE_BASE + Renwumu.DISCOVER_RAGS_BONUS
        if card_id == CARD_ID_GHOSTHUNTER:
            return (Renwumu.DISCOVER_DOMINATE_BASE
                    + Renwumu.DISCOVER_GHOSTHUNTER_BONUS)

        # 灌注后的英雄技能给当回合可用的临时牌。任务仍缺法术时先选法术；
        # 否则空场或场面明显落后时补随从。其它候选按卡牌类型给简单基础分。
        hero_power = getattr(state, "my_hero_power", None)
        if (getattr(hero_power, "card_id", None)
                == CARD_ID_INFUSED_HERO_POWER):
            item = query_json_item(card_id) or {}
            card_type = item.get("type")
            context = Renwumu._context(state)
            has_spell_task = context.holy_quest_open() or context.shadow_quest_open()
            if card_type == "SPELL" and has_spell_task:
                return Renwumu.DISCOVER_DOMINATE_BASE + Renwumu.INFUSED_SPELL_BONUS
            if card_type == "MINION" and Renwumu._board_needs_minion(state):
                return Renwumu.DISCOVER_DOMINATE_BASE + Renwumu.INFUSED_MINION_BONUS
            if card_type == "MINION":
                return Renwumu.DISCOVER_DOMINATE_BASE + 4.0
            if card_type == "SPELL":
                return Renwumu.DISCOVER_DOMINATE_BASE + 3.0
        score = Renwumu.DISCOVER_BASE
        text = card_text(card_id)
        if "复生" in text:
            score += Renwumu.DISCOVER_REBORN_BONUS
        if "战吼" in text or "嘲讽" in text:
            score += Renwumu.DISCOVER_BATTLECRY_TAUNT_BONUS
        if "亡语" in text:
            score -= Renwumu.DISCOVER_DEATHRATTLE_PENALTY
        return Renwumu.DISCOVER_DOMINATE_BASE + score

    @staticmethod
    def _board_needs_minion(state: AiState) -> bool:
        """空场或场面随从价值显著落后时，灌注选牌优先补随从。"""
        my_value = sum(Renwumu._minion_value(minion, mine=True)
                       for minion in getattr(state, "my_minions", ()))
        enemy_value = sum(Renwumu._minion_value(minion, mine=False)
                          for minion in getattr(state, "oppo_minions", ()))
        return not getattr(state, "my_minions", ()) or my_value < enemy_value * 0.7

    # ---------------------------------------------------------------- 工具
    @staticmethod
    def _minion_value(minion, mine: bool) -> float:
        """一个随从的价值：攻*2 + 血（+ 我方铺场分 + 嘲讽分）。"""
        attack = getattr(minion, "attack", 0)
        value = (attack * Renwumu.ATTACK_WEIGHT
                 + (getattr(minion, "health", 0) * Renwumu.HEALTH_WEIGHT
                    if attack > 0 else 0))
        if mine:
            value += Renwumu.BOARD_PRESENCE_SCORE
            if getattr(minion, "taunt", 0):
                value += 1
        return value

    @staticmethod
    def _enemy_kill_value(minion) -> float:
        """Kill value for an enemy minion, including the requested 0-attack cost."""
        penalty = (Renwumu.ZERO_ATTACK_NON_TAUNT_KILL_PENALTY
                   if (getattr(minion, "attack", 0) == 0
                       and not getattr(minion, "taunt", 0)) else 0.0)
        return Renwumu._minion_value(minion, mine=False) - penalty
