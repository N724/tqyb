import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather_report", "nbx", "精准天气插件", "1.2.0")
class WeatherStar(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {"User-Agent": "AstrBot/WeatherPlugin"}

    async def _fetch_weather(self, location: str) -> Optional[str]:
        """获取天气数据"""
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(self.api_url, params={"msg": location}) as resp:
                    if resp.status == 200:
                        return await resp.text(encoding='utf-8')
                    logger.error(f"API响应异常 HTTP {resp.status}")
        except Exception as e:
            logger.error(f"请求失败: {str(e)}")
        return None

    def _parse_weather(self, raw_data: str) -> dict:
        """解析天气数据"""
        # 基础信息解析
        base_pattern = re.compile(
            r"(.*?)\s+"
            r"温度：([\d.-]+)℃\s+"
            r"体感：([\d.-]+)℃\s+"
            r"湿度：(\d+)%\s+"
            r"能见度：([\d.]+)千米\s+"
            r"pm2.5：(\d+)\s+"
            r"空气质量：(\d+)\s+"
            r"紫外线强度：(.+?)\s+"
            r"总体感觉：(.+?)\s+"
        )
        
        # 天气变化解析
        change_pattern = re.compile(
            r"您(.*?)正在下(.*?)哦，(.+?)，(.*)"
        )

        parsed = {"changes": []}
        
        if match := base_pattern.search(raw_data):
            parsed.update({
                "location": match.group(1).split()[-1],  # 取最后一级地名
                "temp": match.group(2),
                "feel_temp": match.group(3),
                "humidity": match.group(4),
                "visibility": match.group(5),
                "pm25": match.group(6),
                "aqi": match.group(7),
                "uv": match.group(8),
                "sensation": match.group(9)
            })

        if change_match := change_pattern.search(raw_data):
            parsed.update({
                "rain": {
                    "direction": change_match.group(1),
                    "intensity": change_match.group(2)
                },
                "current_weather": change_match.group(3),
                "forecast": self._parse_forecast(change_match.group(4))
            })

        return parsed

    def _parse_forecast(self, forecast_str: str) -> list:
        """解析天气变化预报"""
        forecast = []
        if "转" in forecast_str:
            parts = forecast_str.split("转")
            for part in parts:
                if "后" in part:
                    time, weather = part.split("后", 1)
                    forecast.append({"time": time, "weather": weather})
                else:
                    forecast.append({"time": "近期", "weather": part})
        return forecast

    def _build_message(self, data: dict) -> str:
        """构建微信格式消息"""
        msg = [
            f"🌏【{data['location']}天气速报】",
            f"🌡️ 实时温度：{data['temp']}℃（体感{data['feel_temp']}℃）",
            f"💧 空气湿度：{data['humidity']}%",
            f"👁️ 能见度：{data['visibility']}km",
            f"🛡️ PM2.5：{data['pm25']}（AQI {data['aqi']}）",
            f"☀️ 紫外线：{data['uv']}",
            f"😌 体感：{data['sensation']}"
        ]

        if 'rain' in data:
            msg.append(
                f"🌧️ 降水提醒：\n"
                f"您{data['rain']['direction']}方向"
                f"{data['rain']['intensity']}正在下水中～"
            )

        if data.get('forecast'):
            msg.append("\n🕑 天气变化：")
            for change in data['forecast']:
                msg.append(f"▸ {change['time']}后转{change['weather']}")

        return "\n".join(msg)

    @filter.command("天气", "查天气")
    async def get_weather(self, event: AstrMessageEvent):
        '''查询实时天气 例：天气 毕节'''
        if not event.args:
            yield CommandResult().error("📍 请带上地点名称，例如：天气 毕节")
            return

        location = "".join(event.args)
        yield CommandResult().message(f"⛅ 正在定位【{location}】的天气...")

        if raw_data := await self._fetch_weather(location):
            if "错误" in raw_data:  # 假设API返回错误信息包含"错误"关键词
                yield CommandResult().error(f"🚫 查询失败：{raw_data.split('，')}")
                return
                
            weather_data = self._parse_weather(raw_data)
            if not weather_data.get("temp"):
                yield CommandResult().error("⚠️ 数据解析异常，请尝试简化地址")
                return
                
            yield CommandResult().message(self._build_message(weather_data)).use_t2i(False)
        else:
            yield CommandResult().error("🌩️ 天气服务暂时不可用，请稍后重试")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """获取使用帮助"""
        help_msg = (
            "🌦️ 使用指南 🌦️\n\n"
            "1. 基础查询：\n"
            "   » 天气 毕节\n"
            "   » 查天气 贵阳\n\n"
            "2. 数据说明：\n"
            "   • AQI≤50为优\n"
            "   • 能见度＜10km可能有雾\n\n"
            "3. 故障排除：\n"
            "   • 使用区级地名更准确\n"
            "   • 避免特殊符号"
        )
        yield CommandResult().message(help_msg)
