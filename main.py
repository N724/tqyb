import aiohttp
import json
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "彩云天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/zs_tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)  # 15秒超时
        self.default_source = "cytq"  # 默认使用彩云天气

    async def fetch_weather(self, location: str) -> Optional[dict]:
        """获取天气数据（增强错误处理）"""
        try:
            params = {
                "type": self.default_source,
                "msg": location,
                "n": "1"
            }
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    raw_text = await resp.text()
                    logger.debug(f"API原始响应: {raw_text[:200]}...")

                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None

                    try:
                        return await resp.json()
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON解析失败: {str(e)}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    def _format_weather(self, data: str) -> list:
        """格式化天气数据"""
        lines = []
        for line in data.split("\n"):
            if "：" in line:
                key, value = line.split("：", 1)
                lines.append(f"▫️ {key}: {value.strip()}")
        return lines

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询天气，格式：/天气 [地区]'''
        try:
            # 解析地区参数
            args = event.message_str.split()
            if len(args) < 2:
                yield CommandResult().error("❌ 请提供地区名称\n示例：/天气 毕节")
                return

            location = args[1]

            # 发送等待提示
            yield CommandResult().message(f"🌤 正在获取 {location} 的天气数据...")

            # 获取天气数据
            data = await self.fetch_weather(location)
            if not data:
                yield CommandResult().error("⚠️ 天气数据获取失败，请稍后重试")
                return

            # 检查API响应
            if data.get("code") != 200:
                error_msg = data.get("msg", "未知错误")
                yield CommandResult().error(f"❌ 查询失败：{error_msg}")
                return

            # 构建消息内容
            msg = [
                f"🌦 彩云天气 - {data.get('name', location)}",
                "━" * 20
            ]

            # 解析天气数据
            if "data" in data:
                msg.extend(self._format_weather(data["data"]))

            # 添加更新时间
            msg.append(f"\n⏱ 数据时间：{data.get('time', '未知')}")

            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("💥 天气查询服务暂时不可用")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """获取帮助信息"""
        help_msg = [
            "📘 使用说明：",
            "/天气 [地区] - 查询指定地区的天气",
            "/天气帮助 - 显示本帮助信息",
            "━" * 20,
            "示例：",
            "/天气 毕节",
            "/天气 贵州毕节"
        ]
        yield CommandResult().message("\n".join(help_msg))
