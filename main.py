import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather_report", "nbx", "实时天气查询插件", "1.0.1")
class WeatherStar(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {"User-Agent": "AstrBotWeather/1.0"}

    async def _fetch_weather(self, location: str) -> Optional[str]:
        """获取天气原始数据（严格遵循模板结构）"""
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(self.api_url, params={"msg": location}) as resp:
                    # 记录原始响应（调试用）
                    raw_text = await resp.text()
                    logger.debug(f"Weather API Response: {raw_text[:200]}...")
                    
                    if resp.status != 200:
                        logger.error(f"HTTP Error: {resp.status}")
                        return None
                    return raw_text
        except aiohttp.ClientError as e:
            logger.error(f"Network Error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected Error: {str(e)}", exc_info=True)
            return None

    def _parse_weather_data(self, raw_data: str) -> dict:
        """结构化解析天气数据"""
        parsed = {
            "location": "未知地区",
            "temperature": "N/A",
            "feel_temp": "N/A",
            "humidity": "N/A",
            "warnings": [],
            "rain_alerts": []
        }
        
        # 使用正则表达式提取关键数据
        if match := re.search(r"^(.*?)\n温度：(\d+)℃", raw_data):
            parsed["location"] = match.group(1)
            parsed["temperature"] = f"{match.group(2)}℃"

        if match := re.search(r"体感：([\d.]+)℃", raw_data):
            parsed["feel_temp"] = f"{match.group(1)}℃"
        
        if match := re.search(r"湿度：(\d+)%", raw_data):
            parsed["humidity"] = f"{match.group(1)}%"

        # 提取预警信息
        if warnings := re.findall(r"【预警中】(.*?（数据来源：.*?）)", raw_data):
            parsed["warnings"] = [f"⚠️ {w}" for w in warnings]
        
        # 提取降雨提示
        if rain := re.search(r"您(.*?)正在下(.*?)，", raw_data):
            parsed["rain_alerts"].append(f"🌧️ {rain.group(1)}{rain.group(2)}")

        return parsed

    @filter.command("天气", "查天气")
    async def get_weather(self, event: AstrMessageEvent):
        '''查询实时天气 例：天气 上海浦东'''
        try:
            # 参数检查
            if not event.args:
                yield CommandResult().error("🌍 请提供查询地点，例如：天气 北京朝阳区")
                return

            location = " ".join(event.args)
            yield CommandResult().message(f"⛅ 正在获取【{location}】天气数据...")

            # 获取原始数据
            if not (raw_data := await self._fetch_weather(location)):
                yield CommandResult().error("🌪️ 天气数据获取失败，请稍后重试")
                return

            # 解析数据
            weather = self._parse_weather_data(raw_data)
            
            # 构建响应消息
            msg = [
                f"🌏【{weather['location']}实时天气】",
                f"🌡️ 温度：{weather['temperature']}（体感{weather['feel_temp']}）",
                f"💦 湿度：{weather['humidity']}"
            ]

            # 添加预警信息
            if weather["warnings"]:
                msg.append("\n🚨 气象预警：")
                msg.extend(weather["warnings"])
            
            # 添加降雨提示
            if weather["rain_alerts"]:
                msg.append("\n🌧️ 降水提示：")
                msg.extend(weather["rain_alerts"])

            # 添加数据来源
            msg.append("\n📡 数据来源：中国气象局")

            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("🌩️ 天气查询服务暂时不可用，请稍后再试")
