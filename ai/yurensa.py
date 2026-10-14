#鱼人萨策略卡组
#
# ============================ 打法思路（文件注释原文，实现见下面各函数）========
# 卡组策略
# 优先铺场，尽量让自己场上生物较多
# 挑合适时机用法术嗜血，该法术可以给场上我方随从加3攻击，给敌方英雄造成较大损失，赢得对局
# 以下几个关键卡牌使用，要在评分函数里体现
# 闪电风暴：对所有敌方随从造成3点伤害，如果能消灭敌方较多随从，适合用这张法术牌
# 鱼人领军：给我方鱼人随从所有加2攻击，如果场上有自己较多随从，适合上这张牌，单独别上，以免被敌方消灭
# 嗜血：仅在本回合中，我方所有随从加3攻击，常常可以赢得战局
#
# ============================ 留牌思路 ======================================
# >= 3费全换
# 1费只留：啮齿绿鳍鱼人、水宝宝鱼人、鱼人招潮者、鱼人木乃伊
# 2费只留：鱼人猎潮者
#
# ============================ 评分框架（和 renwumu 一致）====================
# rankState(state, actions) = rankStaticState(state) + rankActions(state, actions)
#   * rankStaticState —— 只看场面：谁的场面值钱、谁的血多；
#   * rankActions     —— 只看"最新那个动作"带来的增量（actions[-1]）。
# 搜索里每次算分用的是"动作发生前的旧场面 + 新动作的增量"（见 search.aiSearch
# 的注释），所以这里的增量必须自己估算出动作的效果，别指望能从新场面读出来。
#
# 怎么认牌：一律用 card.name 和中文卡名比（见下面的 CARD_* 常量）。
# 好处：同一张卡有多个版本号（鱼人领军就有 EX1_507 / CORE_EX1_507 / VAN_EX1_507…），
# 认名字比认 card_id 稳，也好读。
from src.recommendation_models import ActionKind
from search.ai_action import AiAction
from search.ai_state import AiState

# 场面号位 -> 实体：动作里的 source/target 是 1 基"场面号位"（随从+地标按站位排），
# 口径与 search.getActions() 生成动作时用的 ordered_board() 完全一致。
from src.game_state.recommendation_adapter import ordered_board


class Yurensa:
    # ================================================================ 参数区
    # 想调打法，改这里的数字就行；每个参数后面都写了它是干什么的。
    # ---------------------------------------------------------------- 留牌
    # 费用 >= 这个值的起手牌一律换掉（"3费以上全换"）。
    MULLIGAN_REPLACE_MIN_COST = 3
    # 1 费只留这些（其余 1 费换掉）。
    MULLIGAN_KEEP_ONE_COST = (
        "啮齿绿鳍鱼人",
        "水宝宝鱼人",
        "鱼人招潮者",
        "鱼人木乃伊",
    )
    # 2 费只留这些（其余 2 费换掉）。
    MULLIGAN_KEEP_TWO_COST = (
        "鱼人猎潮者",
    )

    # ---------------------------------------------------------------- 关键牌名
    CARD_LIGHTNING_STORM = "闪电风暴"     # 3费法术：对所有敌方随从造成3点伤害
    CARD_MURLOC_WARLEADER = "鱼人领军"    # 3费随从：你的其他鱼人+2攻击力
    CARD_BLOODLUST = "嗜血"               # 5费法术：本回合我方所有随从+3攻击力
    # 判"是不是鱼人"用的关键字（中文卡名里所有真鱼人都带"鱼人"）。
    MURLOC_KEYWORD = "鱼人"

    # ---------------------------------------------------------------- 场面评分权重
    ATTACK_WEIGHT = 2        # 1 点攻击 = 2 分（攻击力能换血、能打脸，比血值钱）
    HEALTH_WEIGHT = 1        # 1 点血 = 1 分
    MY_HERO_WEIGHT = 1       # 我方英雄 1 点血 = 1 分
    ENEMY_HERO_WEIGHT = 1    # 敌方英雄 1 点血 = 1 分（打脸加分就靠它）
    BOARD_PRESENCE_SCORE = 3  # 铺场优先：我方场上每多一个随从 +3 分
    MURLOC_BOARD_SCORE = 2    # 我方场上每多一个鱼人 +2 分（鱼人互相加成的载体）
    LETHAL_BONUS = 1000.0     # 能直接打死对手时给的天价分，压过其它一切考虑

    # ---------------------------------------------------------------- 关键牌评分
    LIGHTNING_STORM_DAMAGE = 3   # 闪电风暴的伤害（用来算能打死几个）
    # 闪电风暴一次清掉 2 个以上随从才给的额外分（清场节奏）。
    # 只杀一个随从时没有这分，收益会低于"老实下一个随从"，避免为一张小随从交清场。
    LIGHTNING_STORM_MULTI_KILL_BONUS = 10.0
    LIGHTNING_STORM_MULTI_KILL_MIN = 2
    MURLOC_WARLEADER_BUFF = 2    # 鱼人领军给"其他鱼人"的+攻击力
    # 场上没有别的鱼人时硬上领军的倒扣分（文件注释："单独别上，以免被敌方消灭"）。
    MURLOC_WARLEADER_ALONE_PENALTY = 20.0
    BLOODLUST_BUFF = 3           # 嗜血给我方随从的+攻击力

    # ================================================================ 留牌
    @staticmethod
    def choose(state: AiState) -> list[int]:
        """起手留牌：返回需要【换掉】的手牌下标（0 基）。

        调用方：src/flow/mulligan_flow.py 的 MulliganFlow.run_local ——
        网页「策略选择」选了鱼人萨时，换牌阶段就用本函数决定怎么换。

        留牌规则（文件注释原文）：
            * >= 3 费全换；
            * 1 费只留 啮齿绿鳍鱼人 / 水宝宝鱼人 / 鱼人招潮者 / 鱼人木乃伊；
            * 2 费只留 鱼人猎潮者；
            * 其余（含 0 费幸运币）保留。

        约定：这里是 0 基下标；幸运币不可替换、点不到的位置由 MulliganFlow
        统一过滤，策略不用管点击坐标。
        """
        hand = list(getattr(state, "my_hand_cards", ()) or ())
        replace = []
        for index, card in enumerate(hand):
            cost = getattr(card, "current_cost", 0) or 0
            name = getattr(card, "name", "") or ""
            if cost >= Yurensa.MULLIGAN_REPLACE_MIN_COST:
                replace.append(index)                     # 3费及以上：换
            elif cost == 1 and name not in Yurensa.MULLIGAN_KEEP_ONE_COST:
                replace.append(index)                     # 1费非留牌名单：换
            elif cost == 2 and name not in Yurensa.MULLIGAN_KEEP_TWO_COST:
                replace.append(index)                     # 2费非鱼人猎潮者：换
        names = [getattr(hand[index], "name", "?") for index in replace]
        print(f"[鱼人萨留牌] 起手 {len(hand)} 张，换掉 {len(replace)} 张：{names}")
        return replace

    # ================================================================ 工具
    @staticmethod
    def is_murloc(card) -> bool:
        # 随从是否是鱼人，目前都是，如果卡组将来引入非鱼人，再修改
        return True    

    @staticmethod
    def _minion_value(minion, mine: bool) -> float:
        """一个随从在场面上的价值。

        mine=True（我方）：攻击*权重 + 血量 + 铺场分 + 鱼人分
        mine=False（敌方）：攻击*权重 + 血量（对面铺得宽不加我们的分）
        """
        value = (getattr(minion, "attack", 0) * Yurensa.ATTACK_WEIGHT
                 + getattr(minion, "health", 0) * Yurensa.HEALTH_WEIGHT)
        if mine:
            value += Yurensa.BOARD_PRESENCE_SCORE
            if Yurensa.is_murloc(minion):
                value += Yurensa.MURLOC_BOARD_SCORE
        return value

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

    # ================================================================ 场面评分
    @staticmethod
    def rankStaticState(state: AiState) -> float:
        """和场面有关的评分，和动作无关。"""
        res = 0.0
        # 我方场面：越宽越好（铺场），鱼人越多越好
        for minion in getattr(state, "my_minions", []):
            res += Yurensa._minion_value(minion, mine=True)
        # 敌方场面：同样的价值，扣分
        for minion in getattr(state, "oppo_minions", []):
            res -= Yurensa._minion_value(minion, mine=False)
        # 血量：自己活着值分，对手掉血值分（打脸加分就是这里来的）
        my_hero = getattr(state, "my_hero", None)
        oppo_hero = getattr(state, "oppo_hero", None)
        res += getattr(my_hero, "health", 0) * Yurensa.MY_HERO_WEIGHT
        res -= getattr(oppo_hero, "health", 0) * Yurensa.ENEMY_HERO_WEIGHT
        return res

    # ================================================================ 动作评分
    @staticmethod
    def rankActions(state: AiState, actions: list[AiAction]) -> float:
        """和动作有关的评分：只算"最新那个动作"（列表最后一个）的增量。"""
        if not actions:
            return 0.0
        action = actions[-1]
        if action.action == ActionKind.ATTACK:
            return Yurensa._attack_gain(state, action)
        if action.action == ActionKind.PLAY_CARD:
            return Yurensa._play_gain(state, action)
        # 交易/技能/地标/星舰/发现：暂时不给增量分（会被上面的正向动作比下去）
        return 0.0

    @staticmethod
    def rankState(state: AiState, actions: list[AiAction]) -> float:
        """关键函数：一个场面的总分 = 场面分 + 最新动作的增量分。"""
        return (Yurensa.rankStaticState(state)
                + Yurensa.rankActions(state, actions))

    # ---------------------------------------------------------------- 攻击
    @staticmethod
    def _attack_gain(state: AiState, action: AiAction) -> float:
        """一次攻击值多少分：打脸按伤害算，随从交换按"双方场面价值的变化"算。

        简化：不考虑圣盾/剧毒/风怒/亡语，也不考虑溢出伤害。
        """
        attacker = action.card
        target = action.target
        if attacker is None or target is None:
            return 0.0
        attack = getattr(attacker, "attack", 0)

        # ---- 打脸
        if target.kind == "hero":
            hero = getattr(state, "oppo_hero", None)
            health = getattr(hero, "health", 0)
            if hero is not None and health > 0 and attack >= health:
                return Yurensa.LETHAL_BONUS          # 这一下就打死了
            return attack * Yurensa.ENEMY_HERO_WEIGHT

        # ---- 随从交换
        defender = Yurensa._board_minion(state, "enemy", target.index)
        if defender is None:
            return 0.0
        attacker_health = getattr(attacker, "health", 0)
        defender_health = getattr(defender, "health", 0)
        defender_attack = getattr(defender, "attack", 0)
        if defender_health <= 0 or attacker_health <= 0:
            return 0.0

        gain = 0.0
        # 敌方随从掉血（或被打死：再补上它剩下的价值）
        dealt = min(attack, defender_health)
        gain += dealt * Yurensa.HEALTH_WEIGHT
        if dealt >= defender_health:
            gain += (Yurensa._minion_value(defender, mine=False)
                     - defender_health * Yurensa.HEALTH_WEIGHT)
        # 我方随从挨的反伤（或被换掉：扣掉它整个价值）
        taken = min(defender_attack, attacker_health)
        gain -= taken * Yurensa.HEALTH_WEIGHT
        if taken >= attacker_health:
            gain -= (Yurensa._minion_value(attacker, mine=True)
                     - attacker_health * Yurensa.HEALTH_WEIGHT)
        return gain

    # ---------------------------------------------------------------- 出牌
    @staticmethod
    def _play_gain(state: AiState, action: AiAction) -> float:
        """出一张牌值多少分：关键牌按文件注释里的用法单独算，其余按下场价值算。"""
        name = action.card_name
        if name == Yurensa.CARD_LIGHTNING_STORM:
            return Yurensa._lightning_storm_gain(state)
        if name == Yurensa.CARD_MURLOC_WARLEADER:
            return Yurensa._murloc_warleader_gain(state, action.card)
        if name == Yurensa.CARD_BLOODLUST:
            return Yurensa._bloodlust_gain(state)
        # 普通随从：上场带来的场面价值（攻击/血量 + 铺场分 + 鱼人分），
        # 与 rankStaticState 的口径一致，这样"出随从"和"场面分"不会打架。
        if action.card_type == "MINION" and action.card is not None:
            return Yurensa._minion_value(action.card, mine=True)
        # 其它法术/武器/英雄牌：效果没建模，不给分（不会主动打出去）
        return 0.0

    @staticmethod
    def _lightning_storm_gain(state: AiState) -> float:
        """闪电风暴：能打死越多敌方随从越值（掉血也算，但"赚"在清场）。

        文件注释："如果能消灭敌方较多随从，适合用这张法术牌"——
        所以打死 >= LIGHTNING_STORM_MULTI_KILL_MIN 个才给清场节奏分；
        只打死一个时收益刻意压得比"下一个随从"低，别为一张小牌交清场。
        简化：只按 3 点伤害算，不算过载(1)。
        """
        damage = Yurensa.LIGHTNING_STORM_DAMAGE
        gain = 0.0
        kills = 0
        for minion in getattr(state, "oppo_minions", []):
            health = getattr(minion, "health", 0)
            if health <= 0:
                continue
            dealt = min(damage, health)
            gain += dealt * Yurensa.HEALTH_WEIGHT
            if dealt >= health:               # 直接消灭：剩下的攻击力也一起清掉
                kills += 1
                gain += (Yurensa._minion_value(minion, mine=False)
                         - health * Yurensa.HEALTH_WEIGHT)
        if kills >= Yurensa.LIGHTNING_STORM_MULTI_KILL_MIN:
            gain += Yurensa.LIGHTNING_STORM_MULTI_KILL_BONUS
        return gain

    @staticmethod
    def _murloc_warleader_gain(state: AiState, card) -> float:
        """鱼人领军：给我方"其他鱼人"+2攻击力，鱼人越多越值；单独上倒扣分。

        注意搜索的记分方式是"动作发生前的旧场面 + 新动作增量"（见 search.aiSearch），
        所以这里的倒扣分只在**同一层**比较时起作用：手里还有别的牌可出时不会选它。
        如果它是唯一能出的牌，搜索仍会在下一层用"旧场面"看到领军的站场价值，
        （想彻底禁止光杆领军，得在 rankStaticState 里给"场上只有领军"扣分，
        那是另一种取舍，先不做。）
        """
        others = [minion for minion in getattr(state, "my_minions", [])
                  if Yurensa.is_murloc(minion)]
        if not others:
            # 场上没有别的鱼人就别上（文件注释："单独别上，以免被敌方消灭"）。
            return -Yurensa.MURLOC_WARLEADER_ALONE_PENALTY
        gain = (len(others) * Yurensa.MURLOC_WARLEADER_BUFF
                * Yurensa.ATTACK_WEIGHT)
        if card is not None:                  # 自己也是个 3 费随从，站场价值照算
            gain += Yurensa._minion_value(card, mine=True)
        return gain

    @staticmethod
    def _bloodlust_gain(state: AiState) -> float:
        """嗜血：本回合我方随从+3攻击力，只对"这回合还能打"的随从有意义。

        能凑够打脸伤害就是斩杀（给天价分）；否则按"这回合多打出来的伤害"计分，
        所以有牌可出时（比如下场鱼人）通常轮不到它——文件注释："挑合适时机"。
        简化：不考虑嘲讽挡路，也不考虑对面护甲。
        """
        ready = [minion for minion in getattr(state, "my_minions", [])
                 if getattr(minion, "can_beat_face", False)]
        if not ready:
            return 0.0                        # 场上没随从能打，别浪费嗜血
        extra_damage = Yurensa.BLOODLUST_BUFF * len(ready)
        total = sum(getattr(minion, "attack", 0) for minion in ready)
        total += extra_damage
        hero = getattr(state, "oppo_hero", None)
        health = getattr(hero, "health", 0)
        if hero is not None and health > 0 and total >= health:
            return Yurensa.LETHAL_BONUS       # 文件注释："常常可以赢得战局"
        return extra_damage * Yurensa.ENEMY_HERO_WEIGHT
