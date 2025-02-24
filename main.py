import aiohttp
import logging
from typing import Optional, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "彩云天气插件", "2.0.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[dict]:
        """严格遵守原始模板结构的请求方法"""
        try:
            params = {"msg": location.strip(), "n": "1"}
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None
                    
                    return self._parse_response(await resp.text())

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    def _parse_response(self, raw_text: str) -> dict:
        """完全兼容原始模板的解析方法"""
        data = {"basic": {}, "alerts": []}
        current_section = None
        
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # 预警信息处理
            if line.startswith("预警信息："):
                current_section = "alert"
                data["alerts"].append(line[5:])
                continue
                
            if current_section == "alert":
                data["alerts"][-1] += "\n" + line
                continue
                
            # 键值对解析
            if "：" in line:
                key, value = line.split("：", 1)
                data["basic"][key.strip()] = value.strip()
            elif "正在下" in line:
                data["rain_alert"] = line
                
        return data

    def _format_message(self, data: dict) -> List[str]:
        """保持原始消息构造模式"""
        msg = []
        
        # 预警信息
        if data["alerts"]:
            msg.append("🚨【天气预警】🚨")
            msg.extend(data["alerts"])
            msg.append("━" * 20)

        # 基础信息
        msg.append("🌤️ 实时天气播报")
        if basic := data.get("basic"):
            msg.extend([
                f"🌡️ 温度：{basic.get('温度', 'N/A')}",
                f"💦 体感：{basic.get('体感', 'N/A')}",
                f"💧 湿度：{basic.get('湿度', 'N/A')}"
            ])

        # 降雨提示
        if rain := data.get("rain_alert"):
            msg.append(f"🌧️ {rain}")

        return msg

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''保持原始指令处理结构'''
        try:
            args = event.message_str.split(maxsplit=1)
            if len(args) < 2:
                return CommandResult().error("❌ 请输入有效地址\n示例：/天气 北京朝阳区")
                
            location = args.strip()
            if not location:
                return CommandResult().error("⚠️ 地址不能为空")

            # 保持原始等待提示
            yield CommandResult().message(f"🔍 正在获取 {location} 的天气数据...")

            if not (data := await self.fetch_weather(location)):
                yield CommandResult().error("⚠️ 天气数据获取失败")
                return

            # 保持原始消息构建流程
            message_lines = self._format_message(data)
            yield CommandResult().message("\n".join(message_lines)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("⚠️ 服务暂时不可用")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """原始帮助信息结构"""
        help_msg = [
            "📘 使用说明：",
            "/天气 [地区] - 查询街道级天气",
            "/天气帮助 - 显示本帮助",
            "━" * 20,
            "示例：/天气 上海陆家嘴"
        ]
        yield CommandResult().message("\n".join(help_msg))
