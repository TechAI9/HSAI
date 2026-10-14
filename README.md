1、模型抽象



炉石对战每个回合出牌，可以抽象为以下问题：

在一定总费用cost的限制下，基于当前局面state，在生成各种可能的出牌动作序列actions数组中，找到最优打法best\_actions。

对应search函数

def search(self, state: StrategyState, cost: int) -> tuple\[list\[ProposedAction], float]:



2、如何求解？



优先级队列搜索，不断拓展最优得分的搜索节点，直至场面评分次数达到上限或者搜索完成。

详见search.py



3、整体思路



基于power.log解析不断得到当前最新场面

本地AI找到最优解：actions. 或者基于ocr 得到盒子AI推荐打法。

模拟鼠标动作，执行动作



4、AI时代如何生成自己卡组的策略？



输入卡组信息，先让ai给出 留牌思路和打法思路，生成比如 longzhan.txt

在Ai 编程软件中，或者chatgpt等ai中，问，基于本github项目（提供url地址或者代码本地文件夹），longzhan.txt策略注释，生成longzhan.py等 然后自己再不断调试参数和反馈问题，迭代。



5、运行？



管理员权限 start.sh  web上选择自己的卡组策略



更多想法：



1、原计划load carddefs.xml 这样认识所有卡，但发现xml中只有卡的静态基础信息，没真正结构化卡的效果。

留待后面有时间，真正结构化所有卡牌效果，这样才能更识别敌方卡组。

短期影响不大，因为只要认识自己卡组30张牌，经过足够调试，足以比大多数人自己打得好。注意：是调试后，初始状态还是很弱智的，各种伏笔。



2、vs Silverfish  代码框架更简洁



一直觉得Silversifh代码实在乱了些，这次search框架简洁很多

卡组策略都放ai文件夹，search文件夹是通用搜索框架，要解耦合。

场面类AiState中引入基类DeckContext，每个卡组独有的要记录的上下文信息，比如任务牧的任务完成进度等，放在自己的DeckContext继承类中，

不像silverfish，都堆在场面类里面，这样卡组多了，就爆炸了。

本项目主要新增本地AI策略，search和ai文件夹，致力于编写本地卡组策略，追求调教机器人的乐趣，仅用于ai和python学习，请勿用于商业用途或违背相关游戏公司规定。



感谢原项目大佬，依赖盒子AI项目详见

https://github.com/magicstrangelzb/HearthstoneLegendArriver

