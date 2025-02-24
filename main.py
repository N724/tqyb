import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "趣味天气插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_data(self, location: str) -> Optional[str]:
        """获取天气数据（增强错误处理）"""
        try:
            params = {"msg": location, "n": "1"}
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    # 记录原始响应文本
                    raw_text = await resp.text()
                    logger.debug(f"API原始响应: {raw_text[:200]}...")

                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None
                    return raw_text

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    def _parse_weather(self, text: str) -> dict:
        """解析天气数据（增强容错）"""
        data = {"location": text.split("\n")[0].strip() if text else "未知地区"}
        
        # 使用正则表达式提取关键信息
        patterns = {
            "temperature": (r"温度：(\d+℃)", "❄️"),
            "feels_like": (r"体感：([\d.]+℃)", "🌡️"),
            "humidity": (r"湿度：(\d+%)", "💧"),
            "rain": (r"正在下(.+?)[，。]", "🌧️"),
            "alert": (r"预警信息：([\s\S]+?）)", "⚠️")
        }

        for key, (pattern, emoji) in patterns.items():
            match = re.search(pattern, text)
            if match:
                data[key] = f"{emoji} {match.group(1).strip()}"
            else:
                data[key] = None

        # 特殊处理预警信息
        if data.get("alert"):
            data["alert"] = data["alert"].replace("（数据来源：国家预警信息发布中心）", "")
        
        return data

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''获取趣味天气信息'''
        try:
            # 解析参数
            args = event.message_str.split()
            if len(args) < 2:
                yield CommandResult().error("📍 请提供地点\n示例：/天气 北京朝阳区")
                return

            location = " ".join(args[1:])

            # 发送等待提示
            yield CommandResult().message(f"🌐 正在扫描{location}的天气雷达...")

            # 获取数据
            raw_text = await self.fetch_data(location)
            if not raw_text:
                yield CommandResult().error("🌀 天气雷达信号丢失，请稍后重试")
                return

            # 解析数据
            weather_data = self._parse_weather(raw_text)
            if not weather_data.get("temperature"):
                yield CommandResult().error("❓ 没有找到这个地点的天气数据")
                return

            # 构建消息内容
            msg = [
                f"🌈 {weather_data['location']} 实时天气",
                "━"*20
            ]

            # 添加天气信息
            fields = [
                ("temperature", "温度"),
                ("feels_like", "体感温度"),
                ("humidity", "湿度"),
                ("rain", "降水情况")
            ]
            
            for key, name in fields:
                if weather_data.get(key):
                    msg.append(f"{weather_data[key]}")

            # 添加预警信息
            if weather_data.get("alert"):
                msg.extend([
                    "━"*20,
                    weather_data["alert"],
                    "━"*20
                ])

            # 添加趣味提示
            if "雨" in str(weather_data.get("rain")):
                msg.append("\n🌂 温馨提示：出门记得带伞哦~")
            elif "晴" in str(weather_data.get("rain")):
                msg.append("\n😎 阳光明媚，适合外出活动！")

            # 添加更新时间
            if match := re.search(r"(\d+时\d+分)", raw_text):
                msg.append(f"\n⏰ 更新时间：{match.group(1)}")

            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("🌪 天气卫星信号中断，请稍后再试")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """获取帮助信息"""
        help_msg = [
            "📘 使用指南：",
            "/天气 [地点] - 查询街道级天气",
            "示例：",
            "/天气 上海外滩",
            "/天气 广州天河体育中心",
            "━"*20,
            "✨ 功能特性：",
            "• 精准到街道的天气查询",
            "• 实时天气预警提示",
            "• 趣味表情互动"
        ]
        yield CommandResult().message("\n".join(help_msg))
