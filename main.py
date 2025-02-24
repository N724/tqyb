import aiohttp
import logging
from typing import Optional, Dict, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "精准天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[Dict[str, str]]:
        """获取天气数据并解析为字典"""
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
    """改进后的文本解析方法"""
    result = {}
    lines = text.strip().split("\n")
    
    if len(lines) < 2:
        return {"error": "无效的天气数据格式"}
    
    # 解析地区名称（处理可能的列表格式）
    location_line = lines.strip("[]'")
    if "','" in location_line:  # 处理数组格式
        result["location"] = location_line.split("', '")
    else:
        result["location"] = location_line
    
    # 解析数据字段
    for line in lines[1:]:
        line = line.strip().strip("',")
        if not line:
            continue
        
        # 处理降水提示
        if "正在下" in line and "转" in line:
            result["降水提示"] = line.replace("您", "📍").replace("哦，", "，")
            continue
        
        # 处理预警信息
        if line.startswith("预警信息："):
            result["预警信息"] = line[5:].replace("【", "[").replace("】", "]")
            continue
        
        # 解析键值对
        if "：" in line:
            key, value = line.split("：", 1)
            key = key.strip().replace("pm2.5", "PM2.5")
            if key in result:  # 避免重复字段
                continue
            result[key] = value.strip()

    return result

def _format_message(self, data: Dict[str, str]) -> List[str]:
    """改进后的消息格式化"""
    msg = [
        f"🌦 精准天气 - {data.get('location', '未知地区')}",
        "━" * 20
    ]

    # 核心天气指标
    core_data = [
        ("温度", "🌡️"),
        ("体感", "👤"),
        ("湿度", "💧"),
        ("能见度", "👀"),
        ("PM2.5", "🛡️"),
        ("空气质量", "🏭"),
        ("紫外线强度", "☀️"),
        ("总体感觉", "📝")
    ]
    
    # 添加核心数据
    for key, emoji in core_data:
        if value := data.get(key):
            msg.append(f"{emoji} {key}: {value}")

    # 降水提示（合并处理）
    if rain := data.get("降水提示"):
        msg.extend([
            "",
            "🌧️ 降水提示：",
            f"▫️ {rain}"
        ])

    # 预警信息（增强显示）
    if warning := data.get("预警信息"):
        msg.extend([
            "",
            "⚠️ 气象预警：",
            f"🔴 {warning}"
        ])

    # 添加数据时间
    msg.append("\n⏱ 数据更新：实时播报")
    return msg

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询天气，格式：/天气 [地区]（支持街道级查询）'''
        try:
            args = event.message_str.split()
            if len(args) < 2:
                yield CommandResult().error("❌ 请提供查询地址\n示例：/天气 北京朝阳区望京街道")
                return

            location = ' '.join(args[1:])
            yield CommandResult().message(f"🌤 正在获取【{location}】的天气数据...")

            data = await self.fetch_weather(location)
            if not data or "error" in data:
                yield CommandResult().error("⚠️ 天气数据获取失败，请检查地址有效性")
                return

            if "预警信息" in data:
                data["time"] = "实时更新（含预警信息）"
            
            yield CommandResult().message("\n".join(self._format_message(data)))

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("💥 天气查询服务暂时不可用")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """获取帮助信息"""
        help_msg = [
            "📘 使用说明：",
            "/天气 <地址> - 支持街道级天气查询（例：/天气 上海徐汇区徐家汇街道）",
            "/天气帮助 - 显示本帮助信息",
            "━" * 20,
            "功能特性：",
            "🔸 精确到街道级的天气查询",
            "🔸 实时温度/湿度/体感温度",
            "🔸 降水提示及气象预警",
            "🔸 空气质量与紫外线指数"
        ]
        yield CommandResult().message("\n".join(help_msg))
