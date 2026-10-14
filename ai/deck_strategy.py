# 卡组策略注册表：网页「基础配置 → 策略选择」里选的名字 -> 具体策略类。
#
# 网页上三个选项（定义在 config.STRATEGY_CHOICES）：
#   hsbox   盒子AI —— OCR 读盒子推荐面板，不用本地策略类（这里没有对应项）
#   renwumu 任务牧 —— ai/renwumu.py
#   yurensa 鱼人萨 —— ai/yurensa.py
#
# 新增一个卡组要动三处：
#   1. ai/ 下新建策略文件，实现 choose(state) 与 rankState(state, actions)；
#   2. config.STRATEGY_CHOICES 里加一行 key -> 中文名（网页下拉框会自动多一项）；
#   3. 下面 DECK_STRATEGIES 里加一行 key -> 策略类。
#
# 每个策略类都只读 AiState / AiAction 上与 StrategyState / ProposedAction 同名的
# 字段，所以搜索流程（search.py）和留牌流程（mulligan_flow.py）都不用改。
import config

from ai.renwumu import Renwumu
from ai.yurensa import Yurensa

# key -> 策略类。key 用字符串（不是类名），这样网页上传什么就是什么，
# 也方便以后把策略做成可配置的外部文件。
DECK_STRATEGIES = {
    "renwumu": Renwumu,
    "yurensa": Yurensa,
}

# 策略实例缓存：策略类现在都是纯静态方法（无状态），缓存一次反复用；
# 以后某个卡组要在实例里记东西（比如"这张牌已经打过了"）也能直接生效。
_INSTANCES: dict = {}


def deck_strategy_key(key: str = None):
    """返回有效的卡组策略 key；选的是盒子AI/未知名字时返回 None。"""
    if key is None:
        key = config.strategy_setting()
    return key if key in DECK_STRATEGIES else None


def deck_strategy(key: str = None):
    """取当前（或指定）卡组策略的实例；盒子AI/未知 key 返回 None。"""
    key = deck_strategy_key(key)
    if key is None:
        return None
    cls = DECK_STRATEGIES[key]
    instance = _INSTANCES.get(key)
    if not isinstance(instance, cls):
        instance = cls()
        _INSTANCES[key] = instance
    return instance


def strategy_class(key: str = None):
    """取当前（或指定）卡组策略的类（测试/自检用）；没有则返回 None。"""
    key = deck_strategy_key(key)
    return DECK_STRATEGIES[key] if key is not None else None
