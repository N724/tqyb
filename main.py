import aiohttp
import logging
import re
from typing import Optional, Dict, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "精准天气查询插件", "1.1.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[Dict[str, str]]:
        """获取天气数据"""
        try:
            params = {"msg": location, "n": "1"}
            logger.debug(f"请求参数：{params}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None

                    raw_text = await resp.text()
                    logger.debug(f"API原始响应:\n{raw_text}")
                    return self._parse_weather_text(raw_text)

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    def _parse_weather_text(self, text: str) -> Dict[str, str]:
        """解析天气文本数据"""
        result = {"location": "未知地区"}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        if len(lines) < 2:
            return {"error": "无效的天气数据格式"}

        # 解析地区信息（处理列表格式）
        location_line = lines.strip("[]'")
        if "', '" in location_line:  # 处理多个候选地址
            locations = location_line.split("', '")
            result["location"] = locations
        else:
            result["location"] = location_line

        # 解析详细数据
        current_key = None
        for line in lines[1:]:
            # 处理多行预警信息
            if line.startswith("预警信息："):
                result["预警信息"] = line[5:].strip()
                current_key = "预警信息"
            elif line.startswith("【") and "预警" in line:
                result["预警信息"] = line.strip()
                current_key = None
            # 处理降水提示
            elif "正在下" in line and "转" in line:
                result["降水提示"] = re.sub(r"[哦。，]$", "", line)
                current_key = None
            # 处理键值对数据
            elif "：" in line:
                key, value = line.split("：", 1)
                key = key.strip().replace("pm2.5", "PM2.5")
                result[key] = value.strip()
                current_key = key
            # 合并多行内容
            elif current_key:
                result[current_key] += "\n" + line

        return result

    def _format_message(self, data: Dict[str, str]) -> List[str]:
        """生成格式化消息"""
        msg = [
            f"🌏 地区：{data['location']}",
            "━" * 25
        ]

        # 核心天气信息
        weather_items = [
            ("🌡️ 温度", "温度"),
            ("👤 体感", "体感"),
            ("💧 湿度", "湿度"),
            ("👀 能见度", "能见度"),
            ("🛡️ PM2.5", "PM2.5"),
            ("🏭 空气质量", "空气质量"),
            ("☀️ 紫外线", "紫外线强度"),
            ("📌 体感", "总体感觉")
        ]
        
        for emoji, key in weather_items:
            if value := data.get(key):
                msg.append(f"{emoji}：{value}")

        # 降水提示
        if rain := data.get("降水提示"):
            rain = rain.replace("您", "📍").replace("哦，", "")
            msg.extend([
                "",
                "🌧️ 降水提示：",
                f"▫️ {rain}"
            ])

        # 预警信息
        if warning := data.get("预警信息"):
            msg.extend([
                "",
                "⚠️ 气象预警：",
                f"🔴 {warning}"
            ])

        # 数据来源
        msg.append("\n⏱ 数据更新：实时天气播报")
        return msg

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询天气，格式：/天气 [地址]（支持街道级查询）'''
        try:
            args = event.message_str.split()
            if len(args) < 2:
                yield CommandResult().error("❌ 请提供查询地址\n示例：/天气 贵阳观山湖区长岭南路")
                return

            location = ' '.join(args[1:])
            yield CommandResult().message(f"🛰 正在获取【{location}】的实时天气...")

            data = await self.fetch_weather(location)
            if not data or "error" in data:
                yield CommandResult().error("⚠️ 数据获取失败，请检查地址有效性")
                return

            yield CommandResult().message("\n".join(self._format_message(data)))

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("🌀 天气服务暂时不可用，请稍后重试")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """获取帮助信息"""
        help_msg = [
            "🌦 天气帮助文档",
            "━" * 25,
            "1. 精确查询：",
            "   /天气 <详细地址>",
            "   示例：",
            "   ▫️ /天气 杭州西湖区杨公堤",
            "   ▫️ /天气 重庆渝中区解放碑",
            "",
            "2. 功能特性：",
            "   🔸 街道级精准天气",
            "   🔸 实时温度/湿度/体感",
            "   🔸 降水预报预警",
            "   🔸 空气质量监测",
            "",
            "3. 数据来源：",
            "   中央气象台实时数据"
        ]
        yield CommandResult().message("\n".join(help_msg))
