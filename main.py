import aiohttp
import logging
import re
from typing import Optional, Dict, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "彩云天气查询插件", "1.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[Dict[str, str]]:
        """获取天气数据（严格遵循原有参数结构）"""
        try:
            params = {"msg": location, "n": "1"}
            logger.debug(f"[Weather] 请求参数：{params}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"[Weather] API响应异常 HTTP {resp.status}")
                        return None

                    raw_text = await resp.text()
                    logger.debug(f"[Weather] 原始响应数据：{raw_text[:200]}...")
                    return self._parse_weather_text(raw_text)

        except aiohttp.ClientError as e:
            logger.error(f"[Weather] 网络请求失败：{str(e)}")
            return None
        except Exception as e:
            logger.error(f"[Weather] 未知异常：{str(e)}", exc_info=True)
            return None

    def _parse_weather_text(self, text: str) -> Dict[str, str]:
        """数据解析（严格保持原有返回结构）"""
        result = {}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        if len(lines) < 2:
            return {"error": "数据格式异常"}

        try:
            # 严格处理首行地址格式
            first_line = lines
            if first_line.startswith('[') and first_line.endswith(']'):
                locations = first_line[1:-1].replace("'", "").split(", ")
                result["location"] = locations if locations else "未知地区"
            else:
                result["location"] = first_line
        except Exception as e:
            logger.error(f"[Weather] 地址解析失败：{str(e)}")
            result["location"] = "未知地区"

        # 严格遵循原有键值解析逻辑
        for line in lines[1:]:
            line = re.sub(r"[，。！!]+$", "", line)
            
            # 降水提示处理
            if "正在下" in line and ("转" in line or "后转" in line):
                result["rain"] = line.replace("您", "📍").replace("哦，", "")
                continue
            
            # 预警信息处理
            if line.startswith("预警信息：") or line.startswith("【"):
                result["alert"] = line.replace("预警信息：", "")
                continue
            
            # 标准键值解析
            if "：" in line:
                key, value = line.split("：", 1)
                result[key.strip()] = value.strip()

        return result

    def _format_response(self, data: Dict[str, str]) -> List[str]:
        """完全保持原有消息模板格式"""
        msg = [
            f"🌤 彩云天气 - {data.get('location', '未知地区')}",
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        ]

        # 核心数据展示（保持原有顺序）
        core_fields = [
            ("温度", "℃"),
            ("体感", "℃"),
            ("湿度", "%"),
            ("能见度", "千米"),
            ("PM2.5", ""),
            ("空气质量", ""),
            ("紫外线强度", ""),
            ("总体感觉", "")
        ]
        
        for field, unit in core_fields:
            if value := data.get(field):
                msg.append(f"▫️ {field}：{value}{unit}")

        # 降水提示（原有排版格式）
        if rain := data.get("rain"):
            msg.extend(["", "🌧 降水提示："])
            msg.append(f"   ⚠️ {rain}")

        # 预警信息（原有排版格式）
        if alert := data.get("alert"):
            msg.extend(["", "⚠️ 气象预警："])
            msg.append(f"   🔴 {alert}")

        msg.append(f"\n⏱ 数据时间：{data.get('time', '实时更新')}")
        return msg

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询天气（严格保持原有命令格式）'''
        try:
            # 原有参数解析逻辑
            args = event.message_str.split(maxsplit=1)
            if len(args) < 2:
                yield CommandResult().error("❌ 请提供地区名称\n示例：/天气 北京朝阳区")
                return

            location = args.strip()
            logger.info(f"[Weather] 查询请求：{location}")

            # 原有等待提示
            yield CommandResult().message(f"🌤 正在获取 {location} 的天气数据...")

            # 数据获取流程
            data = await self.fetch_weather(location)
            if not data or "error" in data:
                yield CommandResult().error("⚠️ 天气数据获取失败，请检查地区名称")
                return

            # 保持原有消息生成方式
            yield CommandResult().message("\n".join(self._format_response(data)))

        except Exception as e:
            logger.error(f"[Weather] 指令处理异常：{str(e)}", exc_info=True)
            yield CommandResult().error("💥 服务暂时不可用")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """严格保持原有帮助格式"""
        help_msg = [
            "📘 使用说明：",
            "/天气 [地区] - 查询天气（支持街道级）",
            "/天气帮助 - 显示帮助信息",
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
            "示例：",
            "  /天气 上海徐家汇",
            "  /天气 广州天河区体育西路"
        ]
        yield CommandResult().message("\n".join(help_msg))
