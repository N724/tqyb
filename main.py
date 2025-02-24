import aiohttp
import json
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "多源天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/zs_tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.source_map = {
            "baidu": "百度天气",
            "moji": "墨迹天气",
            "zgtq": "中国天气",
            "zytq": "中央天气",
            "cytq": "彩云天气"
        }

    async def fetch_data(self, params: dict) -> Optional[dict]:
        """获取天气数据（增强错误处理）"""
        try:
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

    @filter.command("weather")
    async def weather_query(self, event: AstrMessageEvent):
        '''获取多源天气信息'''
        try:
            # 解析参数
            args = event.message_str.split()[1:]
            if len(args) < 1:
                yield CommandResult().error("❌ 参数错误\n格式：/weather [地区] [来源]\n示例：/weather 北京 moji")
                return

            location = args[0]
            source = "baidu"
            if len(args) >= 2 and args[1] in self.source_map:
                source = args[1]

            # 发送等待提示
            yield CommandResult().message(f"🌤 正在获取{self.source_map[source]}数据...")

            # 构建请求参数
            params = {
                "type": source,
                "msg": location,
                "n": "1"
            }

            # 获取数据
            data = await self.fetch_data(params)
            if not data:
                yield CommandResult().error("⚠️ 连接天气服务失败，请稍后重试")
                return

            # 检查基础结构
            if "code" not in data:
                logger.error(f"API响应结构异常: {data.keys()}")
                yield CommandResult().error("❗ 数据格式异常，请联系管理员")
                return

            # 处理错误码
            if data["code"] != 200:
                error_map = {
                    "201": "服务异常",
                    "202": "参数错误"
                }
                error_msg = error_map.get(str(data["code"]), "未知错误")
                yield CommandResult().error(f"❌ 查询失败：{error_msg}")
                return

            # 构建消息内容
            msg = [
                f"🌦 {self.source_map[source]} - {data.get('name', '未知地区')}",
                "━"*20
            ]

            # 解析天气数据
            if "data" in data:
                msg.extend(self._format_weather(data["data"]))

            # 添加生活指数
            if source == "zgtq" and "shzs" in data:
                msg.append("\n📊 生活指数：")
                msg.append(data["shzs"].replace("\n", " | "))

            # 添加更新时间
            msg.append(f"\n⏱ 数据时间：{data.get('time', '未知')}")

            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("💥 天气查询服务暂时不可用")

    @filter.command("weather_src")
    async def list_sources(self, event: AstrMessageEvent):
        """查看支持的天气源"""
        sources = ["🌐 可用天气源："]
        sources.extend([f"▫️ {name} ({code})" for code, name in self.source_map.items()])
        sources.append("\n示例：/weather 上海 cytq")
        yield CommandResult().message("\n".join(sources))
