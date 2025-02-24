import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "趣味天气插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[str]:
        """获取天气数据（增强错误处理）"""
        try:
            params = {"msg": location, "n": "1"}
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None
                    return await resp.text()
        except Exception as e:
            logger.error(f"请求异常: {str(e)}")
            return None

    def _parse_weather(self, text: str) -> dict:
        """解析天气数据"""
        data = {"location": text.split("\n")[0].strip()}
        
        # 基础数据解析
        patterns = {
            "temperature": r"温度：(\d+℃)",
            "feels_like": r"体感：([\d.]+℃)",
            "humidity": r"湿度：(\d+%)",
            "rain": r"正在下(.+?)，",
            "alert": r"预警信息：([\s\S]+?）)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            data[key] = match.group(1) if match else None

        # 预警信息特殊处理
        if data.get("alert"):
            data["alert"] = data["alert"].replace("（数据来源：国家预警信息发布中心）", "")

        return data

    def _add_emoji(self, data: dict) -> list:
        """添加趣味表情"""
        msg = [f"🌏 {data['location']} 天气播报", "━"*20]
        
        # 温度相关
        temp = data.get("temperature", "未知")
        feels_temp = data.get("feels_like", "未知")
        msg.append(f"🌡️ 温度：{temp} → 体感：{feels_temp}")

        # 湿度处理
        if humidity := data.get("humidity"):
            hum_emoji = "💧" if int(humidity[:-1]) > 70 else "🏜️"
            msg.append(f"{hum_emoji} 湿度：{humidity}")

        # 降雨提示
        if rain := data.get("rain"):
            rain_emoji = "🌧️" if "雨" in rain else "🌦️"
            msg.append(f"{rain_emoji} 降水情况：{rain}")

        # 预警信息
        if alert := data.get("alert"):
            msg.extend(["━"*20, "⚠️ 预警信息 ⚠️", alert])

        # 趣味尾缀
        if data.get("temperature", "0℃") > "30℃":
            msg.append("\n🔥 热到融化，记得防晒哦~")
        elif data.get("rain"):
            msg.append("\n🌂 出门记得带伞呐！")
            
        return msg

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''趣味天气查询'''
        try:
            # 解析参数
            args = event.message_str.split()
            if len(args) < 2:
                yield CommandResult().error("请告诉我地点呀～\n例如：/天气 北京朝阳公园")
                return

            location = "".join(args[1:])
            
            # 发送等待提示
            yield CommandResult().message(f"🌐 正在扫描{location}的天气雷达...")

            # 获取数据
            raw_text = await self.fetch_weather(location)
            if not raw_text:
                yield CommandResult().error("🌀 天气雷达失联，稍后再试试吧～")
                return

            # 解析数据
            weather_data = self._parse_weather(raw_text)
            if not weather_data.get("temperature"):
                yield CommandResult().error("❓ 没有找到这个地方的天气呢")
                return

            # 构建消息
            msg = self._add_emoji(weather_data)
            msg.append("\n⏱ 数据更新时间：" + re.findall(r"\d+时\d+分", raw_text)[0])
            
            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理异常: {str(e)}")
            yield CommandResult().error("🌪 天气卫星信号中断，请稍后再试")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """获取帮助信息"""
        help_msg = [
            "🌈 使用指南：",
            "/天气 [地点] - 查询详细天气",
            "例如：",
            "/天气 上海外滩",
            "/天气 广州天河体育中心",
            "━"*20,
            "📡 支持查询：",
            "✔️ 城市 ✔️ 区县",
            "✔️ 街道 ✔️ 地标景点"
        ]
        yield CommandResult().message("\n".join(help_msg))
