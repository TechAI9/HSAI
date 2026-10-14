"""
留牌意见有两个来源（由网页「基础配置 → 策略选择」决定），执行与校验完全共用：
  * run()       —— 盒子AI：OCR 左侧「替换N号位卡牌」建议；
  * run_local() —— 任务牧/鱼人萨：对应卡组策略的 choose()。
"""

from dataclasses import dataclass
from enum import Enum
import time


class MulliganStatus(str, Enum):
    CONFIRMED = "confirmed"
    CONCEDE = "concede"


@dataclass(frozen=True)
class MulliganResult:
    status: MulliganStatus
    selected_zero_based_slots: tuple[int, ...] = ()
    diagnostics: str = ""


# 换牌界面可点击的起手位：手牌数 -> 可替换张数。
# 先手 3 张（3 个位置都能换）；后手 4 张 + 幸运币 = 5 张，幸运币在最右侧、
# 不可替换，所以只有前 4 个位置点得到（与 click.STARTING_CARD_X 坐标表对应）。
CLICKABLE_STARTING_CARDS = {3: 3, 5: 4}


class MulliganFlow:
    def __init__(self, executor, action_supplier, state_supplier,
                 action_context=None, stopped=lambda: False,
                 sleep=time.sleep, pre_action_delay=0.0,
                 first_delay=None, retry_delay=None, confirm_ready=None,
                 post_action_pause=None, local_chooser=None):
        self.executor = executor
        self.action_supplier = action_supplier
        self.state_supplier = state_supplier
        self.stopped = stopped
        self.sleep = sleep
        self.first_delay = first_delay if first_delay is not None else pre_action_delay
        self.retry_delay = retry_delay if retry_delay is not None else pre_action_delay
        # 换牌面板“确认”按钮是否就绪的检测回调（None = 不启用前置检测）。
        # 用于“先确认面板在再执行换牌”：按钮不在场就不点击，避免面板未
        # 就绪时盲点。典型实现见 FSM_action.confirm_button_present()。
        self.confirm_ready = confirm_ready
        # 「活人感」（可选）：盒子留牌意见执行完之后的随机延时 + 手牌悬停。
        self.post_action_pause = post_action_pause
        # 本地卡组策略留牌（网页选任务牧/鱼人萨时走 run_local）：各卡组策略的
        # choose(state)，返回需要换掉的 0 基手牌下标。None = 没有可用策略，
        # 此时按“全部保留”提交（见 _local_selection）。
        self.local_chooser = local_chooser
        self._delay_done = False
        if action_context is None:
            from contextlib import nullcontext
            action_context = nullcontext
        self.action_context = action_context

    def run(self):
        try:
            initial = self.state_supplier()
            action = self.action_supplier()
            current_action = self.action_supplier()
            fresh = self.state_supplier()
            if self.stopped():
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="stopped")
            if self._identity(initial) != self._identity(fresh):
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="hand_changed")
            # 换牌阶段 Power.log 会持续写入新行，log_revision 必然漂移；
            # 若要求 initial==fresh 的 revision 完全一致，会在“识别到点击”
            # 之前就频繁返回 revision_changed，导致换牌卡住。这里只要求
            # 手牌指纹与对局阶段稳定，不再要求日志版本号一致。
            if (getattr(fresh, "is_end", False)
                    or getattr(fresh, "game_num_turns_in_play", 0) != 0):
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="mulligan_stage_changed")
            if (current_action.normalized_instruction
                    != action.normalized_instruction
                    or current_action.mulligan_slots != action.mulligan_slots):
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="recommendation_changed")
            count = len(fresh.my_hand_cards)
            selected = tuple(sorted({slot - 1 for slot in action.mulligan_slots}))
            clickable_count = CLICKABLE_STARTING_CARDS.get(count, 0)
            if count not in (3, 5) or any(
                    index < 0 or index >= clickable_count
                    for index in selected):
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="mulligan_slot_invalid")
            failure = self._execute_selection(selected, count)
            if failure is not None:
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics=failure)
            return MulliganResult(MulliganStatus.CONFIRMED, selected)
        except Exception as exc:
            try:
                self.executor.cancel_click()
            except Exception:
                pass
            return MulliganResult(
                MulliganStatus.CONCEDE,
                diagnostics=f"{type(exc).__name__}:{exc}")

    def run_local(self, chooser=None):
        # deepseek ai新增的这个函数和前面代码重叠度比较高，区别只是local_chooser。
        # Todo:未来可以考虑把两者合并，或者把run_local的逻辑放到run里，使用chooser参数来决定使用哪个策略。
        """本地卡组策略留牌：用当前卡组策略的 choose() 决定换哪几张。

        网页「策略选择」选了任务牧/鱼人萨时由 FSM_action 调用，
        代替 run()（读盒子面板 OCR）。两条路径只有“留牌意见从哪来”不同：

          * run()       —— OCR 盒子面板 → 解析出的 `mulligan_slots`（1 基）；
          * run_local() —— `chooser(state)`，各卡组策略的 choose()（0 基）。

        其余完全一致：手牌与对局阶段稳定 → 下标合法 → 确认按钮在场 → 逐个
        点击替换 + 提交确认 → 「活人感」延时。返回的 selected_zero_based_slots
        语义也相同（0 基下标，直接对应点击位）。chooser 缺省用构造时传入的
        self.local_chooser；两者都没有时按“全部保留”提交。
        """
        try:
            chooser = chooser if chooser is not None else self.local_chooser
            initial = self.state_supplier()
            fresh = self.state_supplier()
            if self.stopped():
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="stopped")
            # 换了牌/手牌还在变时先不点：等下一轮拿到稳定手牌再决策，
            # 否则按旧手牌算出来的下标可能指向别的牌。
            if self._identity(initial) != self._identity(fresh):
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="hand_changed")
            if (getattr(fresh, "is_end", False)
                    or getattr(fresh, "game_num_turns_in_play", 0) != 0):
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="mulligan_stage_changed")
            count = len(fresh.my_hand_cards)
            if count not in (3, 5):
                # 起手布局不是 3/5 张时点位的含义未知，不猜（下一轮再看）。
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics="mulligan_slot_invalid")
            selected = self._local_selection(chooser, fresh)
            failure = self._execute_selection(selected, count)
            if failure is not None:
                return MulliganResult(MulliganStatus.CONCEDE,
                                      diagnostics=failure)
            return MulliganResult(MulliganStatus.CONFIRMED, selected)
        except Exception as exc:
            try:
                self.executor.cancel_click()
            except Exception:
                pass
            return MulliganResult(
                MulliganStatus.CONCEDE,
                diagnostics=f"{type(exc).__name__}:{exc}")

    def _execute_selection(self, selected, count):
        """确认按钮门禁 + 延时 + 逐个替换 + 提交确认（两条留牌路径共用）。

        返回 None 表示已执行；返回字符串表示未执行的原因（交给上层重试）。
        """
        # 前置门：确认按钮在场才执行换牌。按钮不在 → 说明面板未就绪
        # 或已提交，交给外层继续轮询，不盲目点击。
        if self.confirm_ready is not None and not self.confirm_ready():
            return MulliganResult(
                MulliganStatus.CONCEDE,
                diagnostics="confirm_button_absent")
        delay = self.retry_delay if self._delay_done else self.first_delay
        if delay > 0:
            print(f"换牌方案已确定（换掉 {len(selected)} 张），"
                f"等待 {delay:.0f}s 后执行……")
            self.sleep(delay)
        self._delay_done = True
        with self.action_context():
            for index in selected:
                self.executor.replace_starting_card(index, count)
            self.executor.commit_choose_card()
    # 留牌意见已执行：交给「活人感」（若开启）做随机延时 + 手牌悬停。
        if self.post_action_pause is not None:
            try:
                self.post_action_pause()
            except Exception:
                pass
        return None

    @staticmethod
    def _local_selection(chooser, state):
        """把卡组策略 choose() 的返回值收敛成可点击的 0 基下标元组。

        choose() 只回答“想换哪几张”，能不能点到由执行层负责：幸运币不可替换，
        超出本局起手布局（3/5 张）的位置也点不到。非法/越界的下标一律丢掉并
        打一行日志——宁可少换一张，也不能按错位置换错牌。
        """
        clickable = CLICKABLE_STARTING_CARDS.get(len(state.my_hand_cards), 0)
        if chooser is None:
            print("[本地留牌] 没有可用的卡组策略 choose()，本局全部保留。")
            return ()
        try:
            chosen = chooser(state) or ()
        except Exception as exc:
            # 策略抛异常不能把整局卡在换牌界面：退化为“全部保留”，下轮再试。
            print(f"[本地留牌] 卡组策略 choose() 执行失败，本局全部保留：{exc}")
            return ()
        selected = set()
        dropped = []
        for index in chosen:
            if (not isinstance(index, int)
                    or not 0 <= index < clickable
                    or getattr(state.my_hand_cards[index], "is_coin", False)):
                dropped.append(index)
                continue
            selected.add(index)
        if dropped:
            print(f"[本地留牌] 忽略不可替换的位置（幸运币/越界）：{dropped}")
        return tuple(sorted(selected))

    def reset_delay(self):
        """每局换牌开始时调用：首次用 ready_delay，重试用 retry_delay。"""
        self._delay_done = False

    @staticmethod
    def _identity(state):
        return tuple((card.card_id, getattr(card, "entity_id", None))
                     for card in state.my_hand_cards)
