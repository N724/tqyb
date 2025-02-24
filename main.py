# main.py
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
        self.headers = {"User-Agent": "AstroWeatherBot/1.0"}
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def _fetch_weather(self, location: str) -> Optional[str]:
        """获取原始天气数据（带重试机制）"""
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(self.api_url, params={"msg": location}) as resp:
                    if resp.status != 200:
                        logger.error(f"API异常 HTTP {resp.status}")
                        return None
                    return await resp.text(encoding="utf-8")
        except Exception as e:
            logger.error(f"天气接口异常: {str(e)}")
            return None

    def _parse_weather(self, raw_data: str) -> dict:
        """解析文本天气数据"""
        result = {"warnings": [], "rain_alerts": []}
        
        # 提取基础信息
        if match := re.search(r"^(.*?)\n温度：(\d+)℃", raw_data):
            result["location"], result["temp"] = match.groups()
        
        # 使用正则表达式提取关键数据
        patterns = {
            "feel": r"体感：([\d.]+)℃",
            "humidity": r"湿度：(\d+)%",
            "pm25": r"pm2.5：(\d+)",
            "uv": r"紫外线强度：(.*?)\n",
            "overview": r"总体感觉：(.*?)\n"
        }
        for key, pattern in patterns.items():
            if match := re.search(pattern, raw_data):
                result[key] = match.group(1)

        # 提取降雨提示
        if rain_info := re.search(r"您(.*?)正在下(.*?)，", raw_data):
            result["rain_alerts"].append(f"🌧️ {rain_info.group(0).strip('哦，')}")

        # 提取预警信息
        if warning_match := re.search(r"【预警中】(.*?（数据来源：.*?）)", raw_data):
            result["warnings"].append(f"⚠️ {warning_match.group(1)}")
        
        return result

    @filter.command("天气", "查天气")
    async def get_weather(self, event: AstrMessageEvent):
        '''查询实时天气 例：天气 上海浦东'''
        if not event.args:
            yield CommandResult().message("🌏 请告诉我您想查询哪里呢？例：天气 北京朝阳区")
            return

        location = " ".join(event.args)
        yield CommandResult().message(f"🌤️ 正在连接气象卫星查询【{location}】...")

        if raw_data := await self._fetch_weather(location):
            weather = self._parse_weather(raw_data)
            if not weather.get("temp"):
                yield CommandResult().message("🛰️ 气象卫星信号丢失，请稍后重试~")
                return

            # 构建天气报告
            report = [f"🌆【{weather['location']}天气快报】"]
            report.append(f"🌡️ 温度：{weather['temp']}℃ （体感{weather.get('feel', 'N/A')}℃）")
            report.append(f"💧 湿度：{weather.get('humidity', 'N/A')}%")
            
            if weather.get("rain_alerts"):
                report.extend(weather["rain_alerts"])
            
            if weather.get("warnings"):
                report.append("\n🔴 气象预警:")
                report.extend(weather["warnings"])
            
            # 添加生活指数
            report.append(f"\n🌞 紫外线：{weather.get('uv', '未知')}")
            report.append(f"😌 体感指数：{weather.get('overview', '未知')}")
            report.append("\n📡 数据来源：中国气象局")

            yield CommandResult().message("\n".join(report)).use_t2i(False)
        else:
            yield CommandResult().message("⛈️ 天气查询失败，可能遇到以下问题：\n1. 地名输入不准确\n2. 气象卫星连接超时\n请尝试重新发送～")
