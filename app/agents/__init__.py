"""
学习教练 Agent 节点集合。

7 个 Agent 节点，每个都是一个纯函数，接收 LearningCoachState，返回部分状态更新：
- supervisor_agent: 调度中心，基于规则决定下一步
- planner_agent: 学习路线规划
- tutor_agent: 知识点讲解与弱项补救
- opensource_mentor_agent: GitHub 开源项目搜索与分析
- reporter_agent: 综合学习报告生成
- assessment_agent: 测验生成与评分
- interview_agent: 模拟面试题生成
"""

from .assessment import assessment_agent
from .interview import interview_agent
from .opensource_mentor import opensource_mentor_agent
from .planner import planner_agent
from .reporter import reporter_agent
from .supervisor import supervisor_agent
from .tutor import tutor_agent

__all__ = [
    "assessment_agent",
    "interview_agent",
    "opensource_mentor_agent",
    "planner_agent",
    "reporter_agent",
    "supervisor_agent",
    "tutor_agent",
]
