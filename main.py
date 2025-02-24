import aiohttp
import logging
import re
from typing import Optional, Dict, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "彩云天气查询插件", "1.0.1")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[Dict[str, str]]:
        """获取天气数据"""
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
        """数据解析（修复地址解析问题）"""
        result = {}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        if len(lines) < 2:
            return {"error": "数据格式异常"}

        try:
            # 正确解析首行地址
            first_line = lines  # 获取实际字符串
            if first_line.startswith('[') and first_line.endswith(']'):
                locations = first_line[1:-1].replace("'", "").split(", ")
                result["location"] = locations if locations else "未知地区"
            else:
                result["location"] = first_line
        except Exception as e:
            logger.error(f"[Weather] 地址解析失败：{str(e)}")
            result["location"] = "未知地区"

        # 解析其他字段...
        for line in lines[1:]:
            line = re.sub(r"[，。！!]+$", "", line)
            
            if "正在下" in line and ("转" in line or "后转" in line):
                result["rain"] = line.replace("您", "📍").replace("哦，", "")
                continue
            
            if line.startswith("预警信息：") or line.startswith("【"):
                result["alert"] = line.replace("预警信息：", "")
                continue
            
            if "：" in line:
                key, value = line.split("：", 1)
                result[key.strip()] = value.strip()

        return result

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询天气'''
        try:
            # 修正后的参数解析
            cmd_parts = event.message_str.split(maxsplit=1)
            if len(cmd_parts) < 2:
                yield CommandResult().error("❌ 格式错误\n正确格式：/天气 地区\n示例：/天气 上海徐家汇")
                return

            location = cmd_parts.strip()
            logger.info(f"[Weather] 查询位置：{location}")

            yield CommandResult().message(f"🌤 正在获取【{location}】的天气数据...")

            data = await self.fetch_weather(location)
            if not data or "error" in data:
                yield CommandResult().error("⚠️ 查询失败，请检查地区是否存在")
                return

            # 消息生成...
            msg = [
                f"🌤 彩云天气 - {data['location']}",
                "▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
                f"▫️ 温度：{data.get('温度', 'N/A')}℃",
                f"▫️ 体感：{data.get('体感', 'N/A')}℃",
                f"▫️ 湿度：{data.get('湿度', 'N/A')}%"
            ]

            if rain := data.get("rain"):
                msg.extend(["", "🌧 降水提示：", f"   ⚠️ {rain}"])
                
            if alert := data.get("alert"):
                msg.extend(["", "⚠️ 气象预警：", f"   🔴 {alert}"])

            msg.append("\n⏱ 数据时间：实时更新")
            yield CommandResult().message("\n".join(msg))

        except Exception as e:
            logger.error(f"[Weather] 指令处理异常：{str(e)}", exc_info=True)
            yield CommandResult().error("💥 服务异常，请稍后重试")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        help_msg = [
            "📘 使用说明：",
            "/天气 [地区] - 查询天气（支持街道级）",
            "示例：",
            "  /天气 北京朝阳区",
            "  /天气 广州天河区体育西路",
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
            "遇到问题请联系管理员"
        ]
        yield CommandResult().message("\n".join(help_msg))
