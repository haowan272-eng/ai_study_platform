"""
Redis 客户端单例管理。

提供 init_redis / get_redis / close_redis 三个函数，管理 Redis 连接池的生命周期。
所有调用方在 Redis 不可用时自动降级，不阻断核心业务流程。

使用方式：
- 应用启动时调用 init_redis()
- 业务代码通过 get_redis() 获取客户端（可能返回 None）
- 应用关闭时调用 close_redis()
"""
import redis
from redis import ConnectionPool

from app.config import REDIS_URL

# 全局连接池和客户端（单例模式）
_pool = None
_client = None


def init_redis():
    """初始化 Redis 连接池和客户端，并执行 ping 验证连通性。"""
    global _pool, _client
    # 创建连接池，最大 20 个连接，自动解码响应为字符串
    _pool = ConnectionPool.from_url(REDIS_URL, max_connections=20, decode_responses=True)
    _client = redis.Redis(connection_pool=_pool)
    _client.ping()  # 验证连接可用


def get_redis():
    """获取 Redis 客户端实例。如果未初始化或已关闭，返回 None。"""
    return _client


def close_redis():
    """关闭 Redis 客户端和连接池，释放资源。"""
    global _client, _pool
    if _client is not None:
        _client.close()
    if _pool is not None:
        _pool.disconnect()
    _client = None
    _pool = None
