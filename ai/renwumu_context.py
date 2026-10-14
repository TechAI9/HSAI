# 任务牧（renwumu）专属的卡组上下文：继承 search.ai_state.DeckContext。
#
# 记录搜索/评分需要的"场面之外"的对局进度（对应 ai/renwumu.py 文件头注释）：
#   * 任务「寻求平衡」进度：已施放几个神圣法术 / 几个暗影法术（各需 4 个）；
#   * 是否有过「预言师」（复生预言师）死亡；
#   * 是否有过「索利托斯，循环新生」（循环新生，两半身拼合后的奖励随从）死亡。
#
# 数据来源与口径：
#   * 真实对局：神圣/暗影法术进度从 StrategyState.my_graveyard 统计；关键
#     随从死亡从 LogState.my_dead_card_ids 统计，该集合只记录己方实体从 PLAY
#     进入 GRAVEYARD 的事件，复生后回场不会清掉死亡历史。
#     法术坟场仍可能包含弃牌/爆牌/被反制的法术，任务牧没有常规弃牌源。
#   * 搜索模拟：doAction() 的钩子（on_card_played / on_minion_died）在
#     copy() 出来的分支上下文上推进进度，各分支互不污染。
#
# 认牌一律用 card_id，卡名只用于日志/注释（与 yurensa 的"认名字"约定不同）：
# 按 card_id 查本文件人工维护的 type / school / text 属性。
from search.ai_state import DeckContext

# 任务「寻求平衡」(TLC_817)：施放 4 个神圣法术 -> 奖励生命之息(半身)；
# 施放 4 个暗影法术 -> 奖励死亡之触(半身)。两半身在手中拼合成循环新生。
QUEST_HOLY_REQUIRED = 4
QUEST_SHADOW_REQUIRED = 4

# 任务牧关键随从 card_id。
CARD_ID_PROPHET = "JAIL_912"       # 预言师（复生预言师）
CARD_ID_SOULTRONUS = "TLC_817t5"   # 索利托斯，循环新生
CARD_ID_UNDEATH = "JAIL_940"       # 不死徒刑

# 任务牧会用到的牌由卡组策略维护属性，避免搜索/评分依赖 cards.json 的
# 文本和学派字段。text 只保留目标推断和关键字判断需要的人工规则信息。
CARD_ATTRIBUTES = {
    "TLC_817": {"name": "寻求平衡", "type": "SPELL", "school": None,
                "text": "任务 神圣 暗影"},
    "CORE_CS2_004": {"name": "真言术：盾", "type": "SPELL", "school": "HOLY",
                      "text": "使一个随从获得+2生命值。抽一张牌。", "targeted": True},
    "CATA_302": {"name": "愈合", "type": "SPELL", "school": "HOLY",
                 "text": "为一个随从恢复所有生命值。抽一张牌。", "targeted": True},
    "JAIL_940": {"name": "不死徒刑", "type": "SPELL", "school": "SHADOW",
                 "text": "随机触发本局中死亡的一个友方随从的亡语。"},
    "DINO_426": {"name": "生命仪式", "type": "SPELL", "school": "HOLY",
                 "text": "发现一张3费随从牌，召唤一个它的2/3复制。"},
    "JAIL_941": {"name": "神圣之拥", "type": "SPELL", "school": "HOLY",
                 "text": "恢复4点生命值。获得黑暗之拥。", "targeted": True},
    "JAIL_941t": {"name": "黑暗之拥", "type": "SPELL", "school": "SHADOW",
                  "text": "造成4点伤害。", "targeted": True},
    "CAP_801": {"name": "幽魂不散", "type": "SPELL", "school": "SHADOW",
                "text": "使一个随从攻击+2/生命值+3，复生和嘲讽。", "targeted": True},
    "CAP_804": {"name": "捉鬼专家", "type": "MINION", "school": None,
                "text": "战吼：使一个友方随从获得复生。", "targeted": True},
    "BAR_311": {"name": "噬灵疫病", "type": "SPELL", "school": "SHADOW",
                "text": "造成4点伤害，随机分配到所有敌方随从身上。"},
    "TLC_816": {"name": "墓晨太阳花", "type": "SPELL", "school": "HOLY",
                 "text": "抽两张牌。"},
    "JAIL_912": {"name": "预言师", "type": "MINION", "school": None,
                 "text": "预备。亡语：为你的英雄恢复6点生命值，然后召唤一个费用为6的随机随从。"},
    "TLC_817t5": {"name": "索利托斯，循环新生", "type": "MINION",
                   "school": None, "text": "复生。嘲讽。战吼：召唤一个本随从的复制。"},
    "TLC_817t3": {"name": "索利托斯，生命之息", "type": "MINION",
                   "school": None, "text": "嘲讽。战吼：召唤一个本随从的复制。"},
    "TLC_817t4": {"name": "索利托斯，死亡之触", "type": "MINION",
                   "school": None, "text": "复生。亡语：随机对一个敌方角色造成5点伤害。"},
    "CAP_806": {"name": "雷斯·范盖斯特", "type": "MINION", "school": None,
                "text": "战吼：复活本局对战中复生过的友方随从，并使其获得复生。"},
    "CATA_308": {"name": "麦迪文的胜利", "type": "SPELL", "school": "HOLY",
                 "text": "对所有随从造成4点伤害。"},
    "CORE_EX1_197": {"name": "暗言术：毁", "type": "SPELL", "school": "SHADOW",
                     "text": "消灭所有攻击力大于或等于5的随从。"},
    "CS2_004": {"name": "真言术：盾", "type": "SPELL", "school": "HOLY",
                "text": "使一个随从获得+2生命值。抽一张牌。", "targeted": True},
    "EX1_197": {"name": "暗言术：毁", "type": "SPELL", "school": "SHADOW",
                "text": "消灭所有攻击力大于或等于5的随从。"},
}


def card_item(card_id):
    """card_id -> 策略人工维护的属性；认不出返回空 dict。"""
    return CARD_ATTRIBUTES.get(card_id, {})


def spell_school(card_id):
    """card_id -> 法术学派（HOLY / SHADOW…）；不是法术或认不出返回 None。"""
    return card_item(card_id).get("school")


def card_text(card_id):
    """card_id -> 卡牌描述文本（发现评分用关键字匹配）；认不出返回空串。"""
    return card_item(card_id).get("text") or ""


class RenwumuDeckContext(DeckContext):
    """任务牧上下文：任务进度 + 关键随从死亡标记。"""

    def __init__(self, holy_spells_cast=0, shadow_spells_cast=0,
                 prophet_died=False, soultronus_died=False):
        self.holy_spells_cast = int(holy_spells_cast or 0)
        self.shadow_spells_cast = int(shadow_spells_cast or 0)
        self.prophet_died = bool(prophet_died)
        self.soultronus_died = bool(soultronus_died)

    # ---------------------------------------------------------------- 构造
    @classmethod
    def from_graveyard(cls, graveyard, dead_card_ids=None):
        """从坟场与 Power.log 死亡历史重建上下文。

        `dead_card_ids` 来自己方随从 PLAY -> GRAVEYARD 的实际转换；有该记录时
        用它判定随从死亡，避免把弃置等仅进入坟场的情况当作死亡。
        """
        context = cls()
        dead_card_ids = (None if dead_card_ids is None
                         else set(dead_card_ids))
        for entity in graveyard or ():
            card_id = getattr(entity, "card_id", None)
            if not card_id:
                continue
            item = card_item(card_id)
            card_type = item.get("type")
            if card_type == "SPELL":
                school = item.get("school")
                if school == "HOLY":
                    context.holy_spells_cast += 1
                elif school == "SHADOW":
                    context.shadow_spells_cast += 1
        # Power.log 的区间死亡记录是权威来源；兼容没有此字段的旧调用方时，
        # 才以坟场实体兜底。
        if dead_card_ids is None:
            dead_card_ids = {
                getattr(entity, "card_id", None) for entity in (graveyard or ())}
        context.prophet_died = CARD_ID_PROPHET in dead_card_ids
        context.soultronus_died = CARD_ID_SOULTRONUS in dead_card_ids
        return context

    # ---------------------------------------------------------------- 模拟钩子
    def on_card_played(self, card):
        """doAction 模拟出牌回调：法术按学派累计任务进度。"""
        item = card_item(getattr(card, "card_id", None))
        if item.get("type") != "SPELL":
            return
        school = item.get("school")
        if school == "HOLY":
            self.holy_spells_cast += 1
        elif school == "SHADOW":
            self.shadow_spells_cast += 1

    def on_minion_died(self, minion):
        """doAction 模拟中我方随从死亡回调：关键随从死亡置位。"""
        card_id = getattr(minion, "card_id", None)
        if card_id == CARD_ID_PROPHET:
            self.prophet_died = True
        elif card_id == CARD_ID_SOULTRONUS:
            self.soultronus_died = True

    # ---------------------------------------------------------------- 查询
    def holy_left(self):
        """神圣法术任务还差几个。"""
        return max(0, QUEST_HOLY_REQUIRED - self.holy_spells_cast)

    def shadow_left(self):
        """暗影法术任务还差几个。"""
        return max(0, QUEST_SHADOW_REQUIRED - self.shadow_spells_cast)

    def holy_quest_open(self):
        return self.holy_left() > 0

    def shadow_quest_open(self):
        return self.shadow_left() > 0

    def quest_complete(self):
        """两个任务（4神圣+4暗影）是否都完成，两个奖励都到手。"""
        return not self.holy_quest_open() and not self.shadow_quest_open()

    def reborn_death_count(self):
        """死过的"复活价值随从"数量（预言师 / 循环新生），雷斯·范盖斯特评分用。"""
        return int(self.prophet_died) + int(self.soultronus_died)

    def summary(self):
        return (f"神圣{self.holy_spells_cast}/{QUEST_HOLY_REQUIRED} "
                f"暗影{self.shadow_spells_cast}/{QUEST_SHADOW_REQUIRED} "
                f"预言师死亡={self.prophet_died} "
                f"循环新生死亡={self.soultronus_died}")

    def __repr__(self):
        return f"RenwumuDeckContext({self.summary()})"
